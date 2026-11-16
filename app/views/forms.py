"""Form rendering helpers and server-side validation."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable, Optional

from ..web import esc

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,24}$")
PHONE_RE = re.compile(r"^\+?[0-9 ()-]{7,20}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,58}[a-z0-9])?$")


class Form:
    """Collects cleaned values and errors. `f.text('name', required=True, max=120)` etc."""

    def __init__(self, req):
        self.req = req
        self.data: dict[str, Any] = {}
        self.errors: dict[str, str] = {}

    def _raw(self, name: str) -> str:
        return self.req.get(name)

    def text(self, name: str, label: str = "", required: bool = False, max: int = 500, min: int = 0) -> str:
        v = self._raw(name)
        label = label or name.replace("_", " ").capitalize()
        if required and not v:
            self.errors[name] = f"{label} is required."
        elif v and len(v) > max:
            self.errors[name] = f"{label} must be {max} characters or fewer."
        elif v and len(v) < min:
            self.errors[name] = f"{label} must be at least {min} characters."
        self.data[name] = v
        return v

    def email(self, name: str, label: str = "Email", required: bool = False) -> str:
        v = self._raw(name).lower()
        if required and not v:
            self.errors[name] = f"{label} is required."
        elif v and not EMAIL_RE.match(v):
            self.errors[name] = "Enter a valid email address, like name@example.com."
        self.data[name] = v
        return v

    def phone(self, name: str, label: str = "Phone", required: bool = False) -> str:
        v = self._raw(name)
        if required and not v:
            self.errors[name] = f"{label} is required."
        elif v and not PHONE_RE.match(v):
            self.errors[name] = "Enter a phone number using digits, spaces and an optional +."
        self.data[name] = v
        return v

    def integer(self, name: str, label: str = "", required: bool = False, min: int = 0, max: int = 100000,
                default: int = 0) -> int:
        raw = self._raw(name)
        label = label or name.replace("_", " ").capitalize()
        if not raw:
            if required:
                self.errors[name] = f"{label} is required."
            self.data[name] = default
            return default
        try:
            v = int(raw)
        except ValueError:
            self.errors[name] = f"{label} must be a whole number."
            self.data[name] = default
            return default
        if v < min or v > max:
            self.errors[name] = f"{label} must be between {min} and {max}."
        self.data[name] = v
        return v

    def date(self, name: str, label: str = "Date", required: bool = False, future: bool = False) -> str:
        v = self._raw(name)
        if required and not v:
            self.errors[name] = f"{label} is required."
        elif v:
            try:
                d = date.fromisoformat(v)
                if future and d < date.today():
                    self.errors[name] = f"{label} can't be in the past."
            except ValueError:
                self.errors[name] = f"{label} must be a valid date."
        self.data[name] = v
        return v

    def time(self, name: str, label: str = "Time", required: bool = False) -> str:
        v = self._raw(name)
        if required and not v:
            self.errors[name] = f"{label} is required."
        elif v and not TIME_RE.match(v):
            self.errors[name] = f"{label} must be a time like 14:30."
        self.data[name] = v
        return v

    def url(self, name: str, label: str = "Link", required: bool = False) -> str:
        v = self._raw(name)
        if v and not re.match(r"^https?://", v, re.I):
            v = "https://" + v
        if required and not v:
            self.errors[name] = f"{label} is required."
        elif v and (len(v) > 600 or not re.match(r"^https?://[^\s<>\"]+\.[^\s<>\"]+", v, re.I)):
            self.errors[name] = f"{label} must be a web address."
        self.data[name] = v
        return v

    def color(self, name: str, default: str) -> str:
        v = self._raw(name)
        if not HEX_RE.match(v or ""):
            v = default
        self.data[name] = v.upper()
        return v.upper()

    def choice(self, name: str, options: Iterable[str], label: str = "", required: bool = False, default: str = "") -> str:
        v = self._raw(name)
        opts = list(options)
        if v and v not in opts:
            self.errors[name] = f"Choose one of the listed {label.lower() or 'options'}."
            v = default
        elif required and not v:
            self.errors[name] = f"{label or 'This'} is required."
        self.data[name] = v or default
        return v or default

    def flag(self, name: str) -> bool:
        v = self.req.get(name) in ("1", "on", "true", "yes")
        self.data[name] = v
        return v

    def error(self, name: str, message: str) -> None:
        self.errors[name] = message

    @property
    def ok(self) -> bool:
        return not self.errors


# --- rendering -----------------------------------------------------------------------------
def csrf(req) -> str:
    return f'<input type="hidden" name="_csrf" value="{esc(req.csrf)}">'


def honeypot() -> str:
    return ('<div class="hp" aria-hidden="true"><label>Leave this empty <input name="website" tabindex="-1" '
            'autocomplete="off"></label></div>')


def errors_summary(errors: dict) -> str:
    if not errors:
        return ""
    items = "".join(f"<li>{esc(m)}</li>" for m in errors.values())
    return (f'<div class="form-errors" role="alert" tabindex="-1" data-focus><b>Please fix '
            f'{"this" if len(errors) == 1 else "these " + str(len(errors))} '
            f'{"item" if len(errors) == 1 else "items"}:</b><ul>{items}</ul></div>')


def _attrs(attrs: Optional[dict]) -> str:
    if not attrs:
        return ""
    out = []
    for k, v in attrs.items():
        if v is True:
            out.append(f" {k}")
        elif v not in (False, None):
            out.append(f' {k}="{esc(v)}"')
    return "".join(out)


def field(name: str, label: str, value: Any = "", type: str = "text", required: bool = False, hint: str = "",
          errors: Optional[dict] = None, attrs: Optional[dict] = None, wrap_class: str = "") -> str:
    err = (errors or {}).get(name)
    fid = "f-" + name.replace("_", "-")
    described = f' aria-describedby="{fid}-hint"' if hint else ""
    if err:
        described = f' aria-describedby="{fid}-err"' + (f' aria-errormessage="{fid}-err"' if True else "")
    a = _attrs(attrs)
    req_attr = " required" if required else ""
    inv = ' aria-invalid="true"' if err else ""
    if type == "textarea":
        control = (f'<textarea class="textarea" id="{fid}" name="{esc(name)}"{req_attr}{inv}{described}{a}>'
                   f'{esc(value)}</textarea>')
    else:
        control = (f'<input class="input" id="{fid}" name="{esc(name)}" type="{type}" value="{esc(value)}"'
                   f'{req_attr}{inv}{described}{a}>')
    req_mark = ' <span class="req" aria-hidden="true">*</span>' if required else ""
    hint_html = f'<span class="hint" id="{fid}-hint">{hint}</span>' if hint else ""
    err_html = f'<span class="field-error" id="{fid}-err">{esc(err)}</span>' if err else ""
    cls = "field" + (" has-error" if err else "") + (f" {wrap_class}" if wrap_class else "")
    return f'<div class="{cls}"><label for="{fid}">{esc(label)}{req_mark}</label>{control}{hint_html}{err_html}</div>'


def select(name: str, label: str, options: Iterable, value: Any = "", required: bool = False, hint: str = "",
           errors: Optional[dict] = None, blank: str = "", attrs: Optional[dict] = None) -> str:
    err = (errors or {}).get(name)
    fid = "f-" + name.replace("_", "-")
    opts = [f'<option value="">{esc(blank)}</option>'] if blank else []
    for o in options:
        v, t = (o if isinstance(o, (tuple, list)) else (o, o))[:2]
        sel = " selected" if str(v) == str(value) else ""
        opts.append(f'<option value="{esc(v)}"{sel}>{esc(t)}</option>')
    req_mark = ' <span class="req" aria-hidden="true">*</span>' if required else ""
    hint_html = f'<span class="hint">{hint}</span>' if hint else ""
    err_html = f'<span class="field-error">{esc(err)}</span>' if err else ""
    return (f'<div class="field{" has-error" if err else ""}"><label for="{fid}">{esc(label)}{req_mark}</label>'
            f'<select class="select" id="{fid}" name="{esc(name)}"{" required" if required else ""}{_attrs(attrs)}>'
            f'{"".join(opts)}</select>{hint_html}{err_html}</div>')


def check(name: str, label: str, checked: bool = False, value: str = "1", hint: str = "", attrs: Optional[dict] = None,
          type: str = "checkbox") -> str:
    c = " checked" if checked else ""
    hint_html = f'<span class="hint" style="display:block">{hint}</span>' if hint else ""
    return (f'<label class="check"><input type="{type}" name="{esc(name)}" value="{esc(value)}"{c}{_attrs(attrs)}>'
            f'<span>{label}{hint_html}</span></label>')


def switch(name: str, label: str, checked: bool = False, attrs: Optional[dict] = None) -> str:
    c = " checked" if checked else ""
    return (f'<label class="switch"><input type="checkbox" name="{esc(name)}" value="1"{c}{_attrs(attrs)}>'
            f'<span>{esc(label)}</span></label>')


def color(name: str, label: str, value: str) -> str:
    fid = "f-" + name
    return (f'<div class="field"><label for="{fid}">{esc(label)}</label><div class="color-field">'
            f'<input type="color" id="{fid}" value="{esc(value)}" data-sync="{esc(name)}" aria-label="{esc(label)}">'
            f'<input type="text" name="{esc(name)}" value="{esc(value)}" maxlength="7" pattern="#[0-9A-Fa-f]{{6}}" '
            f'aria-label="{esc(label)} hex value"></div></div>')


def fmt_date(iso: Optional[str], long: bool = True) -> str:
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return iso
    return d.strftime("%A, %-d %B %Y") if long else d.strftime("%-d %b %Y")


def fmt_time(hhmm: Optional[str]) -> str:
    if not hhmm:
        return ""
    try:
        t = datetime.strptime(hhmm, "%H:%M")
    except ValueError:
        return hhmm
    return t.strftime("%H:%M")


def fmt_dt(iso: Optional[str]) -> str:
    """UTC ISO timestamp → '16 Nov 2026, 14:05' in SAST (UTC+2, no DST)."""
    if not iso:
        return ""
    try:
        from datetime import timedelta
        d = datetime.fromisoformat(iso) + timedelta(hours=2)
        return d.strftime("%-d %b %Y, %H:%M")
    except ValueError:
        return iso


def days_until(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        return (date.fromisoformat(iso[:10]) - date.today()).days
    except ValueError:
        return None


def slugify(text: str, max_len: int = 60) -> str:
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_len].strip("-") or "event"
