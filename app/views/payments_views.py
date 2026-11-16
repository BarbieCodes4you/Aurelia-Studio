"""Checkout, the sandbox test checkout, gateway webhooks, payment status, billing and receipts."""
from __future__ import annotations

from .. import auth, catalog, config, db, events
from ..icons import i
from ..services import payments
from ..web import HTTPError, Response, download, esc, json_response, redirect, router
from .forms import csrf, fmt_dt
from .layout import page
from .shell import account_page, organiser_page, page_head


def _own_order(req, order_uid: str):
    user = auth.require_user(req)
    order = db.one("SELECT * FROM orders WHERE uid = ?", (order_uid,))
    if order is None or (order["user_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPError(404)
    return order


@router.post("/dashboard/events/<uid>/checkout")
def checkout(req, uid):
    ev = events.parse(auth.event_for(req, uid))
    if ev["owner_id"] != req.user["id"]:
        raise HTTPError(403, "Only the event owner can make payments.")
    if not req.get("accept"):
        req.flash("error", "Please accept the terms and refund policy to continue.")
        return redirect(f"/dashboard/events/{uid}/setup/8")
    if ev["status"] == "suspended":
        req.flash("error", "This event is suspended. Contact support.")
        return redirect(f"/dashboard/events/{uid}/setup/8")
    try:
        order = payments.create_order(ev, req.user, req.get("package"))
        target = payments.gateway().checkout(order)
    except payments.PaymentError as e:
        req.flash("error", str(e))
        return redirect(f"/dashboard/events/{uid}/setup/8")
    if "redirect" in target:
        return redirect(target["redirect"])
    inputs = "".join(f'<input type="hidden" name="{esc(k)}" value="{esc(v)}">' for k, v in target["fields"])
    body = f"""<section class="page-hero" style="min-height:70vh;display:grid;align-content:center"><div class="container container--narrow">
<h1>Taking you to secure payment…</h1><p class="lead">You're paying {catalog.money(order["amount_cents"], True)} for {esc(order["description"])}.</p>
<form method="post" action="{esc(target['post_to'])}" id="pf">{inputs}<button class="btn btn--primary btn--lg" type="submit" style="margin-top:24px">Continue to {esc(payments.gateway().label)}</button></form>
<script>document.getElementById('pf').submit();</script></div></section>"""
    return page(req, "Secure payment", body, noindex=True)


# --- built-in sandbox checkout --------------------------------------------------------------------
@router.route("/pay/sandbox/<order_uid>", methods=("GET", "POST"))
def sandbox_checkout(req, order_uid):
    if config.PAYMENT_GATEWAY != "sandbox" or not payments.sandbox_allowed():
        raise HTTPError(404)
    order = _own_order(req, order_uid)
    ev = events.by_id(order["event_id"])
    gw = payments.SandboxGateway()
    if req.method == "POST":
        decision = req.get("decision")
        if decision not in ("approve", "decline", "cancel"):
            raise HTTPError(400)
        if order["status"] == "pending":
            body, sig = gw.build_notification(order, decision)
            # Same path as an incoming webhook: signature, freshness and amount are verified.
            payments.apply(gw.verify(body, sig), "sandbox")
        return redirect(f"/dashboard/events/{ev['uid']}/payment/{order['uid']}")
    excl, vat = payments.vat_breakdown(order["amount_cents"])
    body = f"""<section class="page-hero" style="padding-bottom:var(--section-y)"><div class="grid-texture"></div><div class="container container--narrow">
<span class="demo-flag">Sandbox · test payment, no money moves</span>
<h1 style="margin-top:16px">Test checkout</h1><p class="lead">This page stands in for the payment gateway while {esc(config.BRAND_NAME)} runs in development. Choose an outcome to send a signed test notification to the server.</p>
<div class="glass glass--strong panel" style="margin-top:28px;display:grid;gap:14px">
<dl class="dl"><dt>Order</dt><dd class="mono">{esc(order['uid'])}</dd><dt>Item</dt><dd>{esc(order['description'])}</dd>
<dt>Amount excl. VAT</dt><dd class="mono">{catalog.money(excl, True)}</dd><dt>VAT ({int(config.VAT_RATE * 100)}%)</dt><dd class="mono">{catalog.money(vat, True)}</dd>
<dt><b>Total</b></dt><dd class="mono"><b>{catalog.money(order['amount_cents'], True)}</b></dd><dt>Status</dt><dd><span class="pill pill--{esc(order['status'])}">{esc(order['status'])}</span></dd></dl>
{'' if order['status'] != 'pending' else f'''<form method="post" class="btn-row">{csrf(req)}
<button class="btn btn--primary" name="decision" value="approve" type="submit">{i("check")} Approve test payment</button>
<button class="btn btn--secondary" name="decision" value="decline" type="submit">Decline</button>
<button class="btn btn--ghost" name="decision" value="cancel" type="submit">Cancel</button></form>'''}
</div></div></section>"""
    return page(req, "Sandbox checkout", body, noindex=True)


@router.get("/pay/cancel/<order_uid>")
def pay_cancel(req, order_uid):
    order = _own_order(req, order_uid)
    ev = events.by_id(order["event_id"])
    if order["status"] == "pending" and not db.val("SELECT COUNT(*) FROM payments WHERE order_id = ?", (order["id"],), 0):
        db.run("UPDATE orders SET status = 'cancelled', updated_at = ? WHERE id = ?", (db.now(), order["id"]))
    req.flash("info", "Payment cancelled. Nothing was charged.")
    return redirect(f"/dashboard/events/{ev['uid']}/setup/8")


# --- webhooks (no CSRF: authenticated by signature) ---------------------------------------------------
@router.post("/webhooks/payments/sandbox", csrf=False)
def webhook_sandbox(req):
    if config.PAYMENT_GATEWAY != "sandbox" or not payments.sandbox_allowed():
        raise HTTPError(404)
    notif = payments.SandboxGateway().verify(req.body, req.headers.get("x-aurelia-signature", ""))
    ok, msg = payments.apply(notif, "sandbox")
    return json_response({"ok": notif.valid, "message": msg}, status=200 if notif.valid else 400)


@router.post("/webhooks/payments/payfast", csrf=False)
def webhook_payfast(req):
    if config.PAYMENT_GATEWAY != "payfast":
        raise HTTPError(404)
    gw = payments.PayFastGateway()
    notif = gw.verify_itn(req.body, req.ip)
    payments.apply(notif, "payfast")
    return Response("OK", content_type="text/plain")   # PayFast expects 200 regardless


# --- status / return page ---------------------------------------------------------------------------
@router.get("/api/orders/<order_uid>/status")
def order_status(req, order_uid):
    order = _own_order(req, order_uid)
    ev = events.by_id(order["event_id"])
    return {"status": order["status"], "live": events.is_live(ev), "public_url": events.public_path(ev)}


@router.get("/dashboard/events/<uid>/payment/<order_uid>")
def payment_return(req, uid, order_uid):
    ev = events.parse(auth.event_for(req, uid))
    order = _own_order(req, order_uid)
    if order["event_id"] != ev["id"]:
        raise HTTPError(404)
    st = order["status"]
    if st == "paid":
        live = events.is_live(ev)
        inner = f"""<div class="empty" style="border-style:solid"><span class="icon-tile icon-tile--soft">{i("check")}</span>
<h2>Payment confirmed{' and your website is live' if live else ''}</h2>
<p>Receipt {esc(order['invoice_no'])} is in your email. {'Share your link with guests now.' if live else 'Publish your website from Settings when you are ready.'}</p>
<div class="btn-row">{f'<a class="btn btn--primary" href="/dashboard/events/{uid}/share">{i("chat")} Share your link</a>' if live else ''}
<a class="btn btn--secondary" href="{events.public_path(ev)}" target="_blank" rel="noopener">{i("external")} Open website</a>
<a class="btn btn--ghost" href="/dashboard/orders/{order['uid']}/receipt">View receipt</a></div></div>"""
    elif st == "pending":
        inner = f"""<div class="empty" style="border-style:solid" data-poll="/api/orders/{order['uid']}/status"><span class="spinner" aria-hidden="true"></span>
<h2>Waiting for the payment gateway</h2><p>We publish your website as soon as the gateway confirms payment. This page updates by itself; it usually takes a few seconds.</p>
<a class="btn btn--ghost" href="/dashboard/events/{uid}/setup/8">Back to packages</a></div>
<script>(function(){{var box=document.querySelector('[data-poll]'),n=0;function tick(){{fetch(box.getAttribute('data-poll'),{{headers:{{Accept:'application/json'}},credentials:'same-origin'}}).then(function(r){{return r.json();}}).then(function(j){{if(j.status!=='pending'){{location.reload();}}else if(++n<45){{setTimeout(tick,2000);}}else{{box.querySelector('p').textContent='Still waiting. If you completed the payment, it will appear here shortly; you can safely leave this page.';}}}});}}setTimeout(tick,1500);}})();</script>"""
    else:
        inner = f"""<div class="empty" style="border-style:solid"><span class="icon-tile">{i("alert")}</span><h2>Payment {esc(st)}</h2>
<p>Nothing was charged{f": {esc(order['failure_reason'])}" if order['failure_reason'] and order['failure_reason'] != st else ""}. Your event is saved; you can try again.</p>
<a class="btn btn--primary" href="/dashboard/events/{uid}/setup/8">Try again</a></div>"""
    body = page_head("Payment", f"Order {esc(order['uid'])} · {catalog.money(order['amount_cents'], True)}"
                     + (' · <span class="pill pill--sandbox">sandbox</span>' if order["mode"] == "sandbox" else "")) + inner
    return organiser_page(req, ev, "Payment", body, "/setup/8")


# --- billing & receipts ----------------------------------------------------------------------------------
@router.get("/dashboard/billing")
def billing(req):
    user = auth.require_user(req)
    rows = db.q("""SELECT o.*, e.name AS event_name, e.uid AS event_uid FROM orders o JOIN events e ON e.id = o.event_id
                   WHERE o.user_id = ? ORDER BY o.created_at DESC""", (user["id"],))
    if rows:
        trs = "".join(f"""<tr><td><span class="mono">{esc(o['uid'])}</span><span class="table__sub">{esc(fmt_dt(o['created_at']))}</span></td>
<td><a href="/dashboard/events/{o['event_uid']}">{esc(o['event_name'])}</a><span class="table__sub">{esc(o['description'])}</span></td>
<td class="num mono">{catalog.money(o['amount_cents'], True)}</td><td><span class="pill pill--{esc(o['status'])}">{esc(o['status'])}</span>{' <span class="pill pill--sandbox">sandbox</span>' if o['mode'] == 'sandbox' else ''}</td>
<td>{f'<a href="/dashboard/orders/{o["uid"]}/receipt">Receipt</a>' if o['status'] == 'paid' else ''}</td></tr>""" for o in rows)
        table = f'<div class="table-wrap"><table class="table"><thead><tr><th>Order</th><th>Event</th><th class="num">Amount</th><th>Status</th><th></th></tr></thead><tbody>{trs}</tbody></table></div>'
    else:
        table = f'<div class="empty"><span class="icon-tile">{i("card")}</span><h2 style="font-size:1.2rem">No orders yet</h2><p>When you choose a package for an event, your orders and receipts appear here.</p></div>'
    return account_page(req, "Orders and receipts", page_head("Orders and receipts", "Every payment and its VAT receipt.") + table, "/dashboard/billing")


@router.get("/dashboard/orders/<order_uid>/receipt")
def receipt(req, order_uid):
    order = _own_order(req, order_uid)
    if order["status"] not in ("paid", "refunded"):
        raise HTTPError(404)
    user = db.one("SELECT * FROM users WHERE id = ?", (order["user_id"],))
    ev = events.by_id(order["event_id"])
    excl, vat = payments.vat_breakdown(order["amount_cents"])
    sandbox_note = "SANDBOX TEST PAYMENT. NOT A TAX INVOICE." if order["mode"] == "sandbox" else ""
    if req.arg("format") == "pdf":
        try:
            from ..services.pdf import PDF
        except ImportError:
            raise HTTPError(404)
        doc = PDF(f"{config.BRAND_NAME} receipt", sandbox_note or "Tax invoice")
        doc.kv([("Invoice", order["invoice_no"] or ""), ("Order", order["uid"]), ("Paid", fmt_dt(order["paid_at"])),
                ("Billed to", f"{user['name']} <{user['email']}>"), ("Event", ev["name"]),
                ("VAT number", config.VAT_NUMBER or "To be confirmed")])
        doc.spacer(10)
        doc.table(["Description", "Excl. VAT", "VAT", "Total"],
                  [[order["description"], catalog.money(excl, True), catalog.money(vat, True), catalog.money(order["amount_cents"], True)]],
                  widths=[0.52, 0.16, 0.14, 0.18])
        doc.spacer(10)
        doc.text(f"{config.BRAND_NAME} · {config.COMPANY_ADDRESS} · {config.SUPPORT_EMAIL}", size=8, muted=True)
        return download(doc.output(), f"{order['invoice_no'] or order['uid']}.pdf", "application/pdf")
    body = f"""{page_head("Receipt", "", f'<a class="btn btn--secondary btn--sm" href="?format=pdf">{i("download")} PDF</a><button class="btn btn--ghost btn--sm no-print" type="button" onclick="window.print()">{i("print")} Print</button>')}
<article class="box" style="max-width:760px">{f'<p class="demo-flag" style="margin-bottom:16px">{esc(sandbox_note)}</p>' if sandbox_note else ''}
<div class="row row--between" style="align-items:flex-start"><div><h2 style="font-size:1.4rem">{"Tax invoice" if not sandbox_note else "Receipt"}</h2><p class="muted small">{esc(config.BRAND_NAME)} · {esc(config.COMPANY_ADDRESS)}<br>VAT no. {esc(config.VAT_NUMBER or "to be confirmed")}</p></div>
<div class="small" style="text-align:right"><b class="mono">{esc(order['invoice_no'] or '')}</b><br><span class="muted">{esc(fmt_dt(order['paid_at']))}</span></div></div><hr>
<dl class="dl"><dt>Billed to</dt><dd>{esc(user['name'])}<br><span class="muted">{esc(user['email'])}</span></dd><dt>Event</dt><dd>{esc(ev['name'])}</dd><dt>Order</dt><dd class="mono">{esc(order['uid'])}</dd>
<dt>Description</dt><dd>{esc(order['description'])}</dd><dt>Amount excl. VAT</dt><dd class="mono">{catalog.money(excl, True)}</dd><dt>VAT ({int(config.VAT_RATE * 100)}%)</dt><dd class="mono">{catalog.money(vat, True)}</dd>
<dt><b>Total paid</b></dt><dd class="mono"><b>{catalog.money(order['amount_cents'], True)}</b></dd><dt>Status</dt><dd><span class="pill pill--{esc(order['status'])}">{esc(order['status'])}</span></dd></dl></article>"""
    return account_page(req, "Receipt", body, "/dashboard/billing")
