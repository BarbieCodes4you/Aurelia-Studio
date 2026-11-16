-- Sign-in links by email (no password needed): allow a third token kind, 'login'.
-- SQLite can't change a CHECK constraint in place, so the table is rebuilt.
CREATE TABLE user_tokens_new (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('verify','reset','login')),
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL
);
INSERT INTO user_tokens_new (id, user_id, kind, token_hash, expires_at, used_at, created_at)
  SELECT id, user_id, kind, token_hash, expires_at, used_at, created_at FROM user_tokens;
DROP TABLE user_tokens;
ALTER TABLE user_tokens_new RENAME TO user_tokens;
