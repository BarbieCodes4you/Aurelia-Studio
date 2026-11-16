"""Serve uploaded images with access control: the event must be live, or the viewer must manage it."""
from __future__ import annotations

from .. import auth, db, events
from ..services.storage import storage
from ..web import HTTPError, Response, router


@router.get("/media/<path:key>")
def media(req, key):
    row = db.one("SELECT * FROM uploads WHERE storage_key = ?", (key,))
    if row is None or row["event_id"] is None:
        raise HTTPError(404)
    ev = events.by_id(row["event_id"])
    from .public_event import is_available
    draft_id, _, draft_tok = req.cookies.get(events.DRAFT_COOKIE, "").partition(".")
    shared_draft = ev is not None and draft_id == str(ev["id"]) and events.draft_token_ok(ev, draft_tok)
    if ev is None or not (is_available(ev) or auth.can_manage_event(req.user, ev) or shared_draft):
        raise HTTPError(404)
    data = storage.get(key)
    if data is None:
        raise HTTPError(404)
    r = Response(data, content_type=row["mime"])
    r.header("Cache-Control", "private, max-age=3600")
    r.header("Content-Security-Policy", "default-src 'none'; sandbox")
    return r
