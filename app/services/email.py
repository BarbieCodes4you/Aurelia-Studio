"""Email delivery behind a provider interface, with editable templates and a delivery log.

Providers (EMAIL_PROVIDER):
  outbox  - development default. Writes each message to data/outbox/ as HTML; nothing leaves the machine.
  resend  - Resend HTTPS API (RESEND_API_KEY).
  smtp    - any SMTP server (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD).

Template bodies use light markup: blank-line paragraphs, {{variables}} (escaped), {{{raw}}}
(trusted HTML built by the app, e.g. report tables) and lines like `[button: Label | {{url}}]`.
"""
from __future__ import annotations

import base64
import json
import re
import secrets
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Optional

from .. import config, db
from ..web import esc

# key: (audience, name, subject, body)
DEFAULT_TEMPLATES = {
    # --- organiser ---------------------------------------------------------------------------
    "welcome": ("organiser", "Account registration",
                "Welcome to {{brand}}, {{first_name}}",
                "Hi {{first_name}},\n\nYour {{brand}} account is ready. You can start an event, save it as you go and come back to it any time.\n\n[button: Create your event | {{create_url}}]\n\nOne event. One platform. One link."),
    "verify_email": ("organiser", "Email verification",
                     "Confirm your email address",
                     "Hi {{first_name}},\n\nPlease confirm this is your email address so we can send you RSVP updates and reports.\n\n[button: Confirm my email | {{verify_url}}]\n\nThis link expires in 48 hours. If you didn't create an account, you can ignore this email."),
    "login_link": ("organiser", "Sign-in link",
                   "Your {{brand}} sign-in link",
                   "Hi {{first_name}},\n\nUse this link to sign in and carry on with your event. You don't need a password.\n\n[button: Sign in | {{login_url}}]\n\nThe link works once and expires in 2 hours. If you didn't ask for it, you can ignore this email."),
    "setup_help_received": ("organiser", "Set-up help request received",
                            "We'll set up your event website",
                            "Hi {{first_name}},\n\nThank you for asking us to set up your event website. We'll contact you within one working day to go through the details and send you a quote.\n\nIt helps to have these ready: your date and venue, the names to show on the website, and any photos you'd like to use. Reply to this email or send them to {{support_email}}.\n\nYour reference: {{reference}}"),
    "password_reset": ("organiser", "Password reset",
                       "Reset your {{brand}} password",
                       "Hi {{first_name}},\n\nSomeone asked to reset the password for this account. If it was you, choose a new password here:\n\n[button: Choose a new password | {{reset_url}}]\n\nThe link works once and expires in one hour. If it wasn't you, ignore this email: your password stays the same."),
    "payment_confirmation": ("organiser", "Payment confirmation",
                             "Payment received: {{package}} for {{event_name}}",
                             "Hi {{first_name}},\n\nThank you. We've received your payment of {{amount}} for the {{package}}.\n\nInvoice: {{invoice_no}}\nReference: {{order_ref}}\n\n[button: View your receipt | {{receipt_url}}]"),
    "website_published": ("organiser", "Website publication",
                          "{{event_name}} is live",
                          "Hi {{first_name}},\n\nYour website for {{event_name}} is live. Guests open it on their phones, without an app or an account:\n\n{{public_url}}\n\n[button: Send your invitations | {{share_url}}]\n\nReplies, meal choices and seating all come together on your dashboard: {{dashboard_url}}\n\nFor printed signage, download your QR code from the Share page."),
    "event_link": ("organiser", "Event website link (sent when you tap \"Email me this link\")",
                   "Your link for {{event_name}}",
                   "Hi {{first_name}},\n\nHere is the one link for everything about {{event_name}}:\n\n{{public_url}}\n\nCopy it into WhatsApp, email or a text message. Every guest sees the same page; personal links for each guest are in your guest list.\n\n[button: Share options | {{share_url}}]"),
    "setup_instructions": ("organiser", "Next steps (the day after publishing, only if something is left to do)",
                           "Next steps for {{event_name}}",
                           "Hi {{first_name}},\n\n{{event_name}} is live. Here's what's left to do:\n\n{{{steps}}}\n\n[button: Open your dashboard | {{dashboard_url}}]\n\nYour dashboard always shows the next thing to do."),
    "new_rsvp": ("organiser", "New RSVP notification",
                 "New RSVP: {{guest_name}} {{status_text}}",
                 "Hi {{first_name}},\n\n{{guest_name}} {{status_text}} for {{event_name}}.\n\n{{{details}}}\n\nResponses so far: {{attending}} attending, {{declined}} declined, {{pending}} still to reply.\n\n[button: View all RSVPs | {{rsvp_url}}]"),
    "rsvp_summary": ("organiser", "RSVP summary (daily or weekly)",
                     "RSVP summary for {{event_name}}: {{completion}}% replied",
                     "Hi {{first_name}},\n\nHere's where {{event_name}} stands, {{days_to_go}}.\n\n{{{summary_table}}}\n\nNew since the last summary: {{new_count}}.\n\n[button: Open your dashboard | {{dashboard_url}}]"),
    "outstanding_reminder": ("organiser", "Outstanding RSVP reminder",
                             "{{pending}} guests haven't replied to {{event_name}}",
                             "Hi {{first_name}},\n\nYour RSVP deadline is {{deadline}} and {{pending}} guests haven't replied yet.\n\nYou can send them a reminder from your dashboard. We'll show you a preview before anything is sent.\n\n[button: Remind pending guests | {{remind_url}}]"),
    "seating_complete": ("organiser", "Seating chart completion",
                         "Seating chart complete for {{event_name}}",
                         "Hi {{first_name}},\n\nEvery attending guest now has a table. {{tables}} tables are in use for {{seated}} people.\n\n[button: Download the seating chart | {{seating_url}}]"),
    "final_report": ("organiser", "Final guest report",
                     "Final event report: {{event_name}}",
                     "Hi {{first_name}},\n\nYour final event administration report for {{event_name}} is attached as PDF and CSV.\n\n{{{summary_table}}}\n\n[button: Open reports | {{reports_url}}]"),
    "event_reminder": ("organiser", "Event reminder (organiser)",
                       "{{days_text}}: {{event_name}}",
                       "Hi {{first_name}},\n\n{{event_name}} is {{days_text_lower}}. A quick checklist:\n\n- Download the final guest report for your venue and caterer.\n- Print the seating chart.\n- Send guests the final event information.\n\n[button: Open your dashboard | {{dashboard_url}}]"),
    "post_event": ("organiser", "Post-event report",
                   "Thank you for celebrating with {{brand}}",
                   "Hi {{first_name}},\n\nWe hope {{event_name}} was everything you planned. Your final numbers:\n\n{{{summary_table}}}\n\nYou can send guests a thank-you note from your dashboard. Your website stays online until {{hosting_until}}.\n\n[button: Send a thank-you | {{comms_url}}]"),
    "co_admin_invite": ("organiser", "Administrator access",
                        "You've been added to {{event_name}}",
                        "Hi,\n\n{{inviter}} added you as an administrator for {{event_name}} on {{brand}}.\n\n[button: Open the event | {{dashboard_url}}]\n\nIf you don't have an account yet, register with this email address first."),
    "support_received": ("organiser", "Support request received",
                         "We've received your message",
                         "Hi {{name}},\n\nThanks for getting in touch. Your reference is {{ref}}. We reply within one working day{{priority_note}}.\n\nYour message:\n\n{{message}}"),
    # --- guests -------------------------------------------------------------------------------
    "guest_invitation": ("guest", "Initial invitation",
                         "You're invited: {{event_name}}",
                         "Dear {{guest_first}},\n\n{{hosts}} would love you to join them for {{event_name}} on {{event_date}}.\n\n{{{message_html}}}\n\n[button: View your invitation and RSVP | {{invite_url}}]\n\nPlease reply by {{deadline}}."),
    "rsvp_confirmation": ("guest", "RSVP confirmation",
                          "Your RSVP for {{event_name}}",
                          "Dear {{guest_first}},\n\nThank you for your reply. We've recorded: {{status_text}}.\n\n{{{details}}}\n\nYou can change your answer until {{deadline}} using your personal link.\n\n[button: View or change my RSVP | {{invite_url}}]"),
    "guest_reminder": ("guest", "RSVP reminder",
                       "Reminder: please RSVP for {{event_name}}",
                       "Dear {{guest_first}},\n\nA gentle reminder from {{hosts}}: please let them know if you can join them on {{event_date}}. Replies close on {{deadline}}.\n\n[button: Reply now | {{invite_url}}]"),
    "guest_event_reminder": ("guest", "Event reminder",
                             "See you soon: {{event_name}}",
                             "Dear {{guest_first}},\n\n{{event_name}} is on {{event_date}} at {{start_time}}.\n\nVenue: {{venue_name}}, {{venue_address}}\n\n{{{message_html}}}\n\n[button: Directions and details | {{invite_url}}]"),
    "venue_update": ("guest", "Venue update",
                     "Venue update for {{event_name}}",
                     "Dear {{guest_first}},\n\nPlease note an update to the venue details for {{event_name}}.\n\n{{{message_html}}}\n\nVenue: {{venue_name}}, {{venue_address}}\n\n[button: See the latest details | {{invite_url}}]"),
    "programme_update": ("guest", "Programme update",
                         "Programme update for {{event_name}}",
                         "Dear {{guest_first}},\n\nThe programme for {{event_name}} has been updated.\n\n{{{message_html}}}\n\n[button: View the programme | {{invite_url}}]"),
    "final_info": ("guest", "Final event information",
                   "Everything you need for {{event_name}}",
                   "Dear {{guest_first}},\n\nHere are the final details for {{event_name}} on {{event_date}}.\n\n{{{message_html}}}\n\n[button: Open the event page | {{invite_url}}]"),
    "thank_you": ("guest", "Thank-you message",
                  "Thank you from {{hosts}}",
                  "Dear {{guest_first}},\n\n{{{message_html}}}\n\nWith love,\n{{hosts}}"),
    "custom_message": ("guest", "Custom message",
                       "{{subject}}",
                       "Dear {{guest_first}},\n\n{{{message_html}}}\n\n[button: Open the event page | {{invite_url}}]"),
}


def ensure_templates() -> None:
    have = {r["key"] for r in db.q("SELECT key FROM email_templates")}
    for key, (aud, name, subject, body) in DEFAULT_TEMPLATES.items():
        if key not in have:
            db.insert("email_templates", {"key": key, "audience": aud, "name": name, "subject": subject,
                                          "body": body, "updated_at": db.now()})


def template(key: str):
    row = db.one("SELECT * FROM email_templates WHERE key = ?", (key,))
    if row is None and key in DEFAULT_TEMPLATES:
        ensure_templates()
        row = db.one("SELECT * FROM email_templates WHERE key = ?", (key,))
    return row


# --- rendering -------------------------------------------------------------------------------
_VAR = re.compile(r"\{\{\{\s*(\w+)\s*\}\}\}|\{\{\s*(\w+)\s*\}\}")


def fill(text: str, vars: dict, html: bool) -> str:
    def rep(m):
        if m.group(1):
            return str(vars.get(m.group(1), "")) if html else re.sub(r"<[^>]+>", " ", str(vars.get(m.group(1), "")))
        v = vars.get(m.group(2), "")
        return esc(v) if html else str(v)
    return _VAR.sub(rep, text)


def render_body(body: str, vars: dict) -> tuple[str, str]:
    """Returns (inner_html, plain_text)."""
    blocks = re.split(r"\n\s*\n", body.strip())
    html_parts, text_parts = [], []
    for block in blocks:
        m = re.match(r"^\[button:\s*(.+?)\s*\|\s*(.+?)\s*\]$", block.strip())
        if m:
            label, href = fill(m.group(1), vars, True), fill(m.group(2), vars, False).strip()
            html_parts.append(
                f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 22px"><tr><td style="border-radius:999px;background:#EDCF86;background-image:linear-gradient(180deg,#F8E7B9,#EDCF86 48%,#DDB563)">'
                f'<a href="{esc(href)}" style="display:inline-block;padding:14px 26px;color:#2A1F0A;font:600 15px/1 Helvetica,Arial,sans-serif;text-decoration:none;border-radius:999px">{label}</a></td></tr></table>')
            text_parts.append(f"{fill(m.group(1), vars, False)}: {href}")
            continue
        filled_html = fill(block, vars, True)
        if filled_html.lstrip().startswith(("<table", "<div", "<ul")):
            html_parts.append(filled_html)
        else:
            lines = filled_html.split("\n")
            if all(l.strip().startswith("- ") for l in lines if l.strip()):
                items = "".join(f"<li style='margin:0 0 6px'>{l.strip()[2:]}</li>" for l in lines if l.strip())
                html_parts.append(f"<ul style='margin:0 0 18px;padding-left:20px'>{items}</ul>")
            else:
                html_parts.append(f"<p style='margin:0 0 18px'>{'<br>'.join(lines)}</p>")
        text_parts.append(fill(block, vars, False))
    return "".join(html_parts), "\n\n".join(text_parts)


def wrap(inner: str, preheader: str = "", footer_note: str = "") -> str:
    brand = esc(config.BRAND_NAME)
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="color-scheme" content="light"><title>{brand}</title></head>
<body style="margin:0;padding:0;background:#FBF8F2">
<span style="display:none;max-height:0;overflow:hidden;opacity:0">{esc(preheader)}</span>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FBF8F2"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px">
<tr><td style="padding:0 8px 18px;font:italic 400 26px/1 Georgia,'Times New Roman',serif;color:#1F1A12">
<span style="color:#C99A3C">&#10022;</span>&nbsp;{brand}</td></tr>
<tr><td style="background:#ffffff;border:1px solid #EDE4D2;border-radius:20px;padding:32px 30px;font:400 16px/1.6 Helvetica,Arial,sans-serif;color:#1F1A12">
<div style="height:2px;width:48px;margin:0 0 24px;background:linear-gradient(96deg,#C99A3C,#EBCB7E,#C99A3C);border-radius:2px"></div>
{inner}</td></tr>
<tr><td style="padding:20px 10px;font:400 12px/1.6 Helvetica,Arial,sans-serif;color:#6A6152;text-align:center">
{footer_note}{brand} · {esc(config.COMPANY_ADDRESS)} · <a href="mailto:{esc(config.SUPPORT_EMAIL)}" style="color:#87651C">{esc(config.SUPPORT_EMAIL)}</a></td></tr>
</table></td></tr></table></body></html>"""


def base_vars() -> dict:
    return {"brand": config.BRAND_NAME, "base_url": config.BASE_URL, "create_url": config.BASE_URL + "/create",
            "support_email": config.SUPPORT_EMAIL}


def compose(key: str, vars: dict, subject_override: str = "", body_override: str = "") -> dict:
    t = template(key)
    if t is None:
        raise KeyError(f"Unknown email template {key}")
    v = {**base_vars(), **vars}
    subject = fill(subject_override or t["subject"], v, False)
    inner, text = render_body(body_override or t["body"], v)
    note = ""
    if t["audience"] == "guest" and v.get("unsubscribe_url"):
        note = (f'You received this because {esc(v.get("hosts", "the host"))} invited you. '
                f'<a href="{esc(v["unsubscribe_url"])}" style="color:#87651C">Stop event emails</a>.<br>')
        text += f"\n\nStop event emails: {v['unsubscribe_url']}"
    return {"subject": subject, "html": wrap(inner, preheader=subject, footer_note=note), "text": text,
            "audience": t["audience"], "key": key}


# --- providers -------------------------------------------------------------------------------
class EmailError(Exception):
    pass


class OutboxProvider:
    name = "outbox"

    def send(self, to: str, msg: dict, attachments: list) -> str:
        ref = db.now().replace(":", "").replace("-", "")[:15] + "-" + secrets.token_hex(3)
        folder = config.OUTBOX_DIR
        (folder / f"{ref}.html").write_text(msg["html"], encoding="utf-8")
        meta = {"to": to, "subject": msg["subject"], "text": msg["text"], "attachments": []}
        for name, data, _ in attachments:
            safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
            (folder / f"{ref}-{safe}").write_bytes(data)
            meta["attachments"].append(f"{ref}-{safe}")
        (folder / f"{ref}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return ref


class ResendProvider:
    name = "resend"

    def send(self, to: str, msg: dict, attachments: list) -> str:
        if not config.RESEND_API_KEY:
            raise EmailError("RESEND_API_KEY is not set.")
        payload = {"from": config.EMAIL_FROM, "to": [to], "subject": msg["subject"], "html": msg["html"],
                   "text": msg["text"], "reply_to": config.EMAIL_REPLY_TO}
        if attachments:
            payload["attachments"] = [{"filename": n, "content": base64.b64encode(d).decode()} for n, d, _ in attachments]
        req = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(payload).encode(),
                                     headers={"Authorization": f"Bearer {config.RESEND_API_KEY}",
                                              "Content-Type": "application/json", "User-Agent": "aurelia-mailer/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode()).get("id", "")
        except urllib.error.HTTPError as e:
            raise EmailError(f"Resend {e.code}: {e.read().decode()[:300]}")
        except urllib.error.URLError as e:
            raise EmailError(f"Resend unreachable: {e.reason}")


class SMTPProvider:
    name = "smtp"

    def send(self, to: str, msg: dict, attachments: list) -> str:
        if not config.SMTP_HOST:
            raise EmailError("SMTP_HOST is not set.")
        m = EmailMessage()
        m["From"] = config.EMAIL_FROM
        m["To"] = to
        m["Subject"] = msg["subject"]
        m["Reply-To"] = config.EMAIL_REPLY_TO
        mid = make_msgid(domain=(config.EMAIL_FROM.split("@")[-1].rstrip(">") or "localhost"))
        m["Message-ID"] = mid
        m.set_content(msg["text"])
        m.add_alternative(msg["html"], subtype="html")
        for name, data, ctype in attachments:
            maintype, _, subtype = ctype.partition("/")
            m.add_attachment(data, maintype=maintype, subtype=subtype or "octet-stream", filename=name)
        try:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
                if config.SMTP_STARTTLS:
                    s.starttls(context=ssl.create_default_context())
                if config.SMTP_USER:
                    s.login(config.SMTP_USER, config.SMTP_PASSWORD)
                s.send_message(m)
        except (smtplib.SMTPException, OSError) as e:
            raise EmailError(f"SMTP: {e}")
        return mid


def provider():
    return {"resend": ResendProvider, "smtp": SMTPProvider}.get(config.EMAIL_PROVIDER, OutboxProvider)()


def send(to: str, key: str, vars: dict, *, event_id: Optional[int] = None, user_id: Optional[int] = None,
         guest_id: Optional[int] = None, attachments: Optional[list] = None, batch_id: Optional[str] = None,
         subject_override: str = "", body_override: str = "") -> dict:
    """Render and deliver one email; always writes an email_logs row. Never raises for delivery errors.

    attachments: list of (filename, bytes, content_type).
    """
    msg = compose(key, vars, subject_override, body_override)
    p = provider()
    status, ref, error = "sent", None, None
    t = template(key)
    if t is not None and not t["active"]:
        status, error = "skipped", "Template switched off by an administrator."
    else:
        try:
            ref = p.send(to, msg, attachments or [])
        except Exception as e:  # provider failures are logged, not fatal
            status, error = "failed", str(e)[:500]
            print(f"[email] {key} to {to} failed: {e}", file=sys.stderr)
    log_id = db.insert("email_logs", {
        "event_id": event_id, "user_id": user_id, "guest_id": guest_id, "to_email": to, "template_key": key,
        "subject": msg["subject"], "audience": msg["audience"], "status": status, "provider": p.name,
        "provider_id": ref, "error": error, "outbox_file": ref if p.name == "outbox" and status == "sent" else None,
        "batch_id": batch_id, "created_at": db.now()})
    return {"id": log_id, "status": status, "error": error, "subject": msg["subject"]}


def first_name(name: str) -> str:
    return (name or "").split(" ")[0] or "there"
