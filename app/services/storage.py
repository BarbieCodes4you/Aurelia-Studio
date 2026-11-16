"""Image uploads behind a storage interface.

`LocalStorage` keeps files under data/uploads/. A cloud backend (S3, R2, GCS) only needs the
same three methods; set STORAGE_BACKEND once one is added. Files are validated by their
leading bytes (not the browser's claimed type), size-limited and stored under random names.
"""
from __future__ import annotations

import secrets
from typing import Optional

from .. import config, db

SIGNATURES = [
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
]


class UploadError(Exception):
    pass


def sniff(data: bytes) -> Optional[tuple[str, str]]:
    for sig, mime, ext in SIGNATURES:
        if data.startswith(sig):
            return mime, ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


class LocalStorage:
    root = config.UPLOAD_DIR

    def put(self, key: str, data: bytes) -> None:
        path = (self.root / key).resolve()
        path.relative_to(self.root.resolve())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> Optional[bytes]:
        path = (self.root / key).resolve()
        try:
            path.relative_to(self.root.resolve())
        except ValueError:
            return None
        return path.read_bytes() if path.is_file() else None

    def delete(self, key: str) -> None:
        path = (self.root / key).resolve()
        try:
            path.relative_to(self.root.resolve())
        except ValueError:
            return
        if path.is_file():
            path.unlink()


storage = LocalStorage()


def save_image(upload, event, user_id: Optional[int], kind: str, caption: str = "") -> dict:
    if upload is None or not upload.data:
        raise UploadError("Choose an image to upload.")
    if upload.size > config.MAX_UPLOAD_BYTES:
        raise UploadError(f"Images must be {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB or smaller.")
    kind_info = sniff(upload.data)
    if not kind_info:
        raise UploadError("Upload a JPG, PNG, WebP or GIF image.")
    mime, ext = kind_info
    key = f"{event['uid']}/{kind}-{secrets.token_hex(10)}.{ext}"
    storage.put(key, upload.data)
    sort = db.val("SELECT COALESCE(MAX(sort), 0) + 1 FROM uploads WHERE event_id = ? AND kind = ?",
                  (event["id"], kind), 1)
    up_id = db.insert("uploads", {"event_id": event["id"], "user_id": user_id, "kind": kind, "storage_key": key,
                                  "mime": mime, "size": upload.size, "caption": caption[:200], "sort": sort,
                                  "created_at": db.now()})
    return dict(db.one("SELECT * FROM uploads WHERE id = ?", (up_id,)))


def delete_upload(upload_id: int, event_id: int) -> bool:
    row = db.one("SELECT * FROM uploads WHERE id = ? AND event_id = ?", (upload_id, event_id))
    if not row:
        return False
    storage.delete(row["storage_key"])
    db.run("DELETE FROM uploads WHERE id = ?", (upload_id,))
    return True
