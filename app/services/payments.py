"""Payments behind a gateway interface.

Rules:
- Only a verified server-to-server notification (webhook / PayFast ITN) can mark an order paid.
  The browser coming back to a "return" URL proves nothing and changes nothing.
- Notifications are idempotent: replays are recorded but applied once.
- The amount in the notification must equal the order amount.

Gateways (PAYMENT_GATEWAY):
  sandbox - built-in test checkout for development. No money moves. Its notification is signed with
            HMAC-SHA256 using SECRET_KEY and goes through the same verification path as a real webhook.
  payfast - PayFast (South Africa). PAYFAST_SANDBOX=1 uses sandbox.payfast.co.za.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from .. import auth, catalog, config, db, events, notify
from . import email as mail


@dataclass
class Notification:
    order_uid: str
    status: str                 # paid | failed | cancelled
    amount_cents: int
    gateway_payment_id: str = ""
    raw: dict = field(default_factory=dict)
    valid: bool = False
    reason: str = ""


class PaymentError(Exception):
    pass


# --- gateways ------------------------------------------------------------------------------------
class SandboxGateway:
    name = "sandbox"
    mode = "sandbox"
    label = "built-in sandbox checkout"

    def checkout(self, order) -> dict:
        return {"redirect": f"/pay/sandbox/{order['uid']}"}

    @staticmethod
    def sign(body: bytes) -> str:
        return hmac.new(config.SECRET_KEY.encode(), b"sandbox-webhook:" + body, hashlib.sha256).hexdigest()

    def build_notification(self, order, decision: str) -> tuple[bytes, str]:
        payload = {"order": order["uid"], "status": "paid" if decision == "approve" else "failed" if decision == "decline" else "cancelled",
                   "amount_cents": order["amount_cents"], "payment_id": "SBX-" + secrets.token_hex(6),
                   "ts": int(time.time()), "nonce": secrets.token_hex(8)}
        body = json.dumps(payload, separators=(",", ":")).encode()
        return body, self.sign(body)

    def verify(self, body: bytes, signature: str) -> Notification:
        try:
            data = json.loads(body.decode())
        except ValueError:
            return Notification("", "failed", 0, valid=False, reason="Malformed body")
        n = Notification(str(data.get("order", "")), str(data.get("status", "")), int(data.get("amount_cents", -1)),
                         str(data.get("payment_id", "")), data)
        if not signature or not hmac.compare_digest(signature, self.sign(body)):
            n.reason = "Bad signature"
            return n
        if abs(time.time() - int(data.get("ts", 0))) > 600:
            n.reason = "Notification expired"
            return n
        if n.status not in ("paid", "failed", "cancelled"):
            n.reason = "Unknown status"
            return n
        n.valid = True
        return n


class PayFastGateway:
    name = "payfast"
    label = "PayFast"

    @property
    def mode(self) -> str:
        return "sandbox" if config.PAYFAST_SANDBOX else "live"

    @property
    def host(self) -> str:
        return "sandbox.payfast.co.za" if config.PAYFAST_SANDBOX else "www.payfast.co.za"

    @staticmethod
    def signature(pairs: list[tuple[str, str]], passphrase: str = "") -> str:
        """MD5 of the URL-encoded, non-empty fields in order, plus the passphrase when set."""
        parts = [f"{k}={urllib.parse.quote_plus(str(v).strip())}" for k, v in pairs if str(v).strip() != ""]
        s = "&".join(parts)
        if passphrase:
            s += "&passphrase=" + urllib.parse.quote_plus(passphrase.strip())
        return hashlib.md5(s.encode()).hexdigest()

    def checkout(self, order) -> dict:
        if not (config.PAYFAST_MERCHANT_ID and config.PAYFAST_MERCHANT_KEY):
            raise PaymentError("PayFast is not configured (PAYFAST_MERCHANT_ID / PAYFAST_MERCHANT_KEY).")
        user = db.one("SELECT * FROM users WHERE id = ?", (order["user_id"],))
        ev = db.one("SELECT uid FROM events WHERE id = ?", (order["event_id"],))
        first, _, last = (user["name"] or "").partition(" ")
        fields = [
            ("merchant_id", config.PAYFAST_MERCHANT_ID), ("merchant_key", config.PAYFAST_MERCHANT_KEY),
            ("return_url", f"{config.BASE_URL}/dashboard/events/{ev['uid']}/payment/{order['uid']}"),
            ("cancel_url", f"{config.BASE_URL}/pay/cancel/{order['uid']}"),
            ("notify_url", f"{config.BASE_URL}/webhooks/payments/payfast"),
            ("name_first", first[:100]), ("name_last", last[:100]), ("email_address", user["email"]),
            ("m_payment_id", order["uid"]), ("amount", f"{order['amount_cents'] / 100:.2f}"),
            ("item_name", order["description"][:100]),
        ]
        fields.append(("signature", self.signature(fields, config.PAYFAST_PASSPHRASE)))
        return {"post_to": f"https://{self.host}/eng/process", "fields": fields}

    def _valid_source(self, ip: str) -> bool:
        if not config.env_bool("PAYFAST_CHECK_IP", True):
            return True
        allowed = set()
        for host in ("www.payfast.co.za", "sandbox.payfast.co.za", "w1w.payfast.co.za", "w2w.payfast.co.za"):
            try:
                allowed.update(socket.gethostbyname_ex(host)[2])
            except OSError:
                pass
        return ip in allowed

    def _server_confirms(self, pairs: list[tuple[str, str]]) -> bool:
        body = urllib.parse.urlencode(pairs).encode()
        req = urllib.request.Request(f"https://{self.host}/eng/query/validate", data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "aurelia/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode().strip() == "VALID"
        except urllib.error.URLError:
            return False

    def verify_itn(self, raw_body: bytes, ip: str) -> Notification:
        pairs = urllib.parse.parse_qsl(raw_body.decode("utf-8", "replace"), keep_blank_values=True)
        data = dict(pairs)
        amount = data.get("amount_gross", "0")
        try:
            cents = round(float(amount) * 100)
        except ValueError:
            cents = -1
        status = {"COMPLETE": "paid", "FAILED": "failed", "CANCELLED": "cancelled"}.get(data.get("payment_status", ""), "")
        n = Notification(data.get("m_payment_id", ""), status, cents, data.get("pf_payment_id", ""), data)
        sig_pairs = [(k, v) for k, v in pairs if k != "signature"]
        if not hmac.compare_digest(data.get("signature", ""), self.signature(sig_pairs, config.PAYFAST_PASSPHRASE)):
            n.reason = "Bad signature"
            return n
        if not status:
            n.reason = "Unknown payment status"
            return n
        if not self._valid_source(ip):
            n.reason = f"Notification from unexpected IP {ip}"
            return n
        if not self._server_confirms(sig_pairs):
            n.reason = "PayFast did not confirm the notification"
            return n
        n.valid = True
        return n


def gateway():
    return PayFastGateway() if config.PAYMENT_GATEWAY == "payfast" else SandboxGateway()


# --- orders --------------------------------------------------------------------------------------
def quote(ev, package_code: str) -> tuple[Optional[dict], int, str]:
    """(package, amount_cents, error). Upgrades pay the difference."""
    pkg = catalog.package(package_code)
    if not pkg or not pkg["active"]:
        return None, 0, "Choose a package."
    paid = catalog.package(ev["paid_package"])
    if paid:
        if pkg["rank"] <= paid["rank"]:
            return None, 0, "That package is already covered by your payment."
        return dict(pkg), pkg["price_cents"] - paid["price_cents"], ""
    return dict(pkg), pkg["price_cents"], ""


def sandbox_allowed() -> bool:
    return config.PAYMENT_GATEWAY != "sandbox" or config.ALLOW_SANDBOX_PAYMENTS


def create_order(ev, user, package_code: str) -> dict:
    pkg, amount, err = quote(ev, package_code)
    if err:
        raise PaymentError(err)
    if not sandbox_allowed():
        raise PaymentError("Online payments aren't switched on yet. Please contact us to complete your booking.")
    gw = gateway()
    uid = "AUR-" + secrets.token_hex(5).upper()
    upgrade = bool(ev["paid_package"])
    desc = f"{pkg['name']}{' upgrade' if upgrade else ''}: {ev['name']}"
    now = db.now()
    # cancel older unpaid attempts for this event so only one pending order exists
    db.run("UPDATE orders SET status = 'cancelled', updated_at = ? WHERE event_id = ? AND status = 'pending'", (now, ev["id"]))
    oid = db.insert("orders", {"uid": uid, "user_id": user["id"], "event_id": ev["id"], "package_code": pkg["code"],
                               "description": desc[:200], "amount_cents": amount, "currency": "ZAR", "status": "pending",
                               "gateway": gw.name, "mode": gw.mode, "created_at": now, "updated_at": now})
    events.touch(ev["id"], selected_package=pkg["code"])
    auth.audit(user["id"], "order.create", uid, package=pkg["code"], amount=amount, gateway=gw.name)
    return dict(db.one("SELECT * FROM orders WHERE id = ?", (oid,)))


def _next_invoice_no() -> str:
    year = db.now()[:4]
    n = db.val("SELECT COUNT(*) FROM orders WHERE invoice_no LIKE ?", (f"INV-{year}-%",), 0) + 1
    return f"INV-{year}-{n:05d}"


def apply(notif: Notification, gateway_name: str) -> tuple[bool, str]:
    """Record a notification; apply it once if valid. Returns (applied, message)."""
    order = db.one("SELECT * FROM orders WHERE uid = ?", (notif.order_uid,))
    if order is None:
        return False, "Unknown order"
    db.insert("payments", {"order_id": order["id"], "gateway": gateway_name, "gateway_payment_id": notif.gateway_payment_id,
                           "status": notif.status or "unknown", "amount_cents": max(notif.amount_cents, 0),
                           "verified": 1 if notif.valid else 0, "raw": db.dumps(notif.raw), "created_at": db.now()})
    if not notif.valid:
        auth.audit(None, "payment.rejected", order["uid"], reason=notif.reason)
        return False, notif.reason
    if order["gateway"] != gateway_name:
        return False, "Gateway mismatch"
    if notif.amount_cents != order["amount_cents"]:
        auth.audit(None, "payment.amount_mismatch", order["uid"], got=notif.amount_cents, expected=order["amount_cents"])
        return False, "Amount mismatch"
    if order["status"] == "paid":
        return False, "Already paid"
    now = db.now()
    if notif.status == "paid":
        with db.transaction():
            fresh = db.one("SELECT status FROM orders WHERE id = ?", (order["id"],))
            if fresh["status"] == "paid":
                return False, "Already paid"
            db.run("""UPDATE orders SET status = 'paid', paid_at = ?, updated_at = ?, gateway_ref = ?, invoice_no = ?
                      WHERE id = ?""", (now, now, notif.gateway_payment_id, _next_invoice_no(), order["id"]))
            ev = events.by_id(order["event_id"])
            prev = catalog.package(ev["paid_package"])
            fields = {"paid_package": order["package_code"], "selected_package": order["package_code"]}
            if prev and ev["hosting_until"]:
                # upgrade: extend hosting by the difference in included months
                from datetime import date, timedelta
                extra = catalog.package_limits(order["package_code"]).get("hosting_months", 0) - catalog.package_limits(prev["code"]).get("hosting_months", 0)
                if extra > 0:
                    fields["hosting_until"] = (date.fromisoformat(ev["hosting_until"]) + timedelta(days=int(extra * 30.5))).isoformat()
            events.touch(ev["id"], **fields)
        auth.audit(order["user_id"], "payment.paid", order["uid"], amount=order["amount_cents"], mode=order["mode"])
        order = db.one("SELECT * FROM orders WHERE id = ?", (order["id"],))
        ev = events.by_id(order["event_id"])
        user = db.one("SELECT * FROM users WHERE id = ?", (order["user_id"],))
        pkg = catalog.package(order["package_code"])
        mail.send(user["email"], "payment_confirmation", {
            "first_name": mail.first_name(user["name"]), "event_name": ev["name"], "package": pkg["name"] if pkg else order["package_code"],
            "amount": catalog.money(order["amount_cents"], True), "invoice_no": order["invoice_no"], "order_ref": order["uid"],
            "receipt_url": f"{config.BASE_URL}/dashboard/orders/{order['uid']}/receipt"},
            event_id=ev["id"], user_id=user["id"])
        if ev["status"] in ("draft", "unpublished") or not ev["published_at"]:
            notify.publish(ev, order["user_id"])
        return True, "Paid"
    db.run("UPDATE orders SET status = ?, failure_reason = ?, updated_at = ? WHERE id = ? AND status = 'pending'",
           (notif.status, notif.raw.get("reason", "") or notif.status, now, order["id"]))
    auth.audit(order["user_id"], f"payment.{notif.status}", order["uid"])
    return True, notif.status


def vat_breakdown(amount_cents: int) -> tuple[int, int]:
    """Prices include VAT. Returns (excl, vat)."""
    excl = round(amount_cents / (1 + config.VAT_RATE))
    return excl, amount_cents - excl
