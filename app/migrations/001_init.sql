-- Aurelia core schema. Money is stored in cents (ZAR). Timestamps are ISO 8601 UTC text.
-- JSON columns hold flexible per-event settings; relational data (guests, tables, menus,
-- orders, payments, emails) lives in proper tables with foreign keys.

CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name TEXT NOT NULL,
  phone TEXT,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer','admin')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended')),
  email_verified_at TEXT,
  marketing_consent INTEGER NOT NULL DEFAULT 0,
  is_demo INTEGER NOT NULL DEFAULT 0,
  last_login_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE sessions (
  id TEXT PRIMARY KEY,                      -- sha256 of the cookie token
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  csrf TEXT NOT NULL,
  data TEXT NOT NULL DEFAULT '{}',
  ip TEXT,
  user_agent TEXT,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE INDEX idx_sessions_user ON sessions(user_id);

CREATE TABLE user_tokens (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('verify','reset')),
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE categories (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  group_slug TEXT NOT NULL,                 -- weddings | baby | parties | other
  description TEXT NOT NULL DEFAULT '',
  features TEXT NOT NULL DEFAULT '[]',      -- JSON list of hints (e.g. "family_sides", "multi_function")
  sort INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE templates (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  design TEXT NOT NULL,                     -- renderer key in app/eventsite/designs.py
  direction TEXT NOT NULL,                  -- design direction label
  description TEXT NOT NULL DEFAULT '',
  groups TEXT NOT NULL DEFAULT '[]',        -- JSON list of category group slugs
  tags TEXT NOT NULL DEFAULT '[]',
  sort INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT
);

CREATE TABLE packages (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,                -- essential | premium | signature
  name TEXT NOT NULL,
  tagline TEXT NOT NULL DEFAULT '',
  price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
  features TEXT NOT NULL DEFAULT '[]',      -- JSON list of feature keys (gates functionality)
  bullets TEXT NOT NULL DEFAULT '[]',       -- JSON list of display lines
  limits TEXT NOT NULL DEFAULT '{}',        -- JSON {email_sends, hosting_months, functions, admins, gallery_photos}
  rank INTEGER NOT NULL DEFAULT 0,          -- upgrade order
  highlight INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT
);

CREATE TABLE events (
  id INTEGER PRIMARY KEY,
  uid TEXT NOT NULL UNIQUE,                 -- private identifier used in dashboard URLs
  owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  slug TEXT NOT NULL UNIQUE,                -- public URL /events/<slug>
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','published','unpublished','suspended','archived')),
  category TEXT NOT NULL,
  template TEXT NOT NULL,
  name TEXT NOT NULL,
  hosts TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  event_date TEXT,                          -- YYYY-MM-DD
  start_time TEXT,                          -- HH:MM
  end_time TEXT,
  venue TEXT NOT NULL DEFAULT '{}',         -- JSON {name,address,map_url,parking,directions,accommodation}
  design TEXT NOT NULL DEFAULT '{}',        -- JSON {palette,colors,fonts,background,images,wording,monogram,logo}
  guest_settings TEXT NOT NULL DEFAULT '{}',-- JSON {estimated,categories,family_groups,vip_note,children_allowed,...}
  info TEXT NOT NULL DEFAULT '{}',          -- JSON {dress_code,registry,gifts,contacts,accommodation,instructions,catering_notes,drinks,dietary_options,seating_notes}
  sections TEXT NOT NULL DEFAULT '{}',      -- JSON visibility map
  report_prefs TEXT NOT NULL DEFAULT '{}',  -- JSON {summary: none|daily|weekly, new_rsvp: bool, auto_reminders: bool}
  selected_package TEXT,                    -- chosen in step 10, before payment
  paid_package TEXT,                        -- set only by a verified payment
  hosting_until TEXT,
  wizard_step INTEGER NOT NULL DEFAULT 1,
  wizard_done TEXT NOT NULL DEFAULT '[]',   -- JSON list of completed step numbers
  rsvp_open INTEGER NOT NULL DEFAULT 1,
  suspended_reason TEXT,
  is_demo INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  published_at TEXT
);
CREATE INDEX idx_events_owner ON events(owner_id);

CREATE TABLE event_admins (
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'editor',
  created_at TEXT NOT NULL,
  PRIMARY KEY (event_id, user_id)
);

CREATE TABLE event_functions (               -- ceremonies / receptions / multi-day parts
  id INTEGER PRIMARY KEY,
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  func_date TEXT,
  start_time TEXT,
  end_time TEXT,
  venue_name TEXT NOT NULL DEFAULT '',
  address TEXT NOT NULL DEFAULT '',
  map_url TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  dress_code TEXT NOT NULL DEFAULT '',
  sort INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_functions_event ON event_functions(event_id);

CREATE TABLE schedule_items (
  id INTEGER PRIMARY KEY,
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  function_id INTEGER REFERENCES event_functions(id) ON DELETE SET NULL,
  item_time TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL DEFAULT 'other',      -- ceremony | reception | speech | entertainment | activity | other
  sort INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_schedule_event ON schedule_items(event_id);

CREATE TABLE menus (
  id INTEGER PRIMARY KEY,
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  sort INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE menu_items (
  id INTEGER PRIMARY KEY,
  menu_id INTEGER NOT NULL REFERENCES menus(id) ON DELETE CASCADE,
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  course TEXT NOT NULL DEFAULT 'Main',
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '[]',          -- JSON: vegetarian, vegan, halal, gluten-free...
  selectable INTEGER NOT NULL DEFAULT 0,   -- 1 = guests choose this as their meal
  sort INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_menu_items_event ON menu_items(event_id);

CREATE TABLE guests (
  id INTEGER PRIMARY KEY,
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  token TEXT NOT NULL UNIQUE,               -- personal invitation link token
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL DEFAULT '' COLLATE NOCASE,
  phone TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',        -- e.g. Family, Friends, Colleagues
  family_group TEXT NOT NULL DEFAULT '',    -- e.g. "Mokoena family"
  side TEXT NOT NULL DEFAULT '',            -- e.g. Bride's family / Groom's family
  is_vip INTEGER NOT NULL DEFAULT 0,
  is_child INTEGER NOT NULL DEFAULT 0,
  plus_ones_allowed INTEGER NOT NULL DEFAULT 0,
  children_allowed INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','attending','declined')),
  plus_ones INTEGER NOT NULL DEFAULT 0,
  plus_one_names TEXT NOT NULL DEFAULT '',
  children INTEGER NOT NULL DEFAULT 0,
  meal_item_id INTEGER REFERENCES menu_items(id) ON DELETE SET NULL,
  dietary TEXT NOT NULL DEFAULT '',
  allergies TEXT NOT NULL DEFAULT '',
  special_requests TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',           -- organiser-only
  source TEXT NOT NULL DEFAULT 'organiser', -- organiser | import | general_link
  email_consent INTEGER NOT NULL DEFAULT 1,
  unsubscribed_at TEXT,
  invited_at TEXT,
  responded_at TEXT,
  checked_in_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX idx_guests_event ON guests(event_id, status);

CREATE TABLE guest_functions (               -- per-function attendance for multi-function events
  guest_id INTEGER NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
  function_id INTEGER NOT NULL REFERENCES event_functions(id) ON DELETE CASCADE,
  attending INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (guest_id, function_id)
);

CREATE TABLE rsvp_responses (                -- history of every RSVP submission
  id INTEGER PRIMARY KEY,
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  guest_id INTEGER REFERENCES guests(id) ON DELETE SET NULL,
  payload TEXT NOT NULL,
  via TEXT NOT NULL,                        -- personal | general
  created_at TEXT NOT NULL
);
CREATE INDEX idx_rsvp_event ON rsvp_responses(event_id, created_at);

CREATE TABLE seating_tables (
  id INTEGER PRIMARY KEY,
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  capacity INTEGER NOT NULL DEFAULT 10 CHECK (capacity > 0),
  shape TEXT NOT NULL DEFAULT 'round',      -- round | long
  pos_x REAL NOT NULL DEFAULT 0,            -- percent of the floor plan
  pos_y REAL NOT NULL DEFAULT 0,
  notes TEXT NOT NULL DEFAULT '',
  sort INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_tables_event ON seating_tables(event_id);

CREATE TABLE seat_assignments (
  guest_id INTEGER PRIMARY KEY REFERENCES guests(id) ON DELETE CASCADE,
  table_id INTEGER NOT NULL REFERENCES seating_tables(id) ON DELETE CASCADE,
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  assigned_at TEXT NOT NULL
);
CREATE INDEX idx_seats_table ON seat_assignments(table_id);

CREATE TABLE uploads (
  id INTEGER PRIMARY KEY,
  event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  kind TEXT NOT NULL,                       -- hero | gallery | logo | background
  storage_key TEXT NOT NULL UNIQUE,         -- path relative to the storage root
  mime TEXT NOT NULL,
  size INTEGER NOT NULL,
  caption TEXT NOT NULL DEFAULT '',
  sort INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_uploads_event ON uploads(event_id, kind);

CREATE TABLE orders (
  id INTEGER PRIMARY KEY,
  uid TEXT NOT NULL UNIQUE,                 -- merchant reference sent to the gateway
  user_id INTEGER NOT NULL REFERENCES users(id),
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  package_code TEXT NOT NULL,
  description TEXT NOT NULL,
  amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
  currency TEXT NOT NULL DEFAULT 'ZAR',
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','paid','failed','cancelled','refunded')),
  gateway TEXT NOT NULL,
  mode TEXT NOT NULL,                       -- sandbox | live
  gateway_ref TEXT,
  invoice_no TEXT UNIQUE,
  failure_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  paid_at TEXT
);
CREATE INDEX idx_orders_event ON orders(event_id);

CREATE TABLE payments (                      -- every verified gateway notification
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  gateway TEXT NOT NULL,
  gateway_payment_id TEXT,
  status TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  verified INTEGER NOT NULL DEFAULT 0,
  raw TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE email_templates (
  id INTEGER PRIMARY KEY,
  key TEXT NOT NULL UNIQUE,
  audience TEXT NOT NULL CHECK (audience IN ('organiser','guest','system')),
  name TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,                       -- light markup: paragraphs, {{variables}}, [button: Label | {{url}}]
  active INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);

CREATE TABLE email_logs (
  id INTEGER PRIMARY KEY,
  event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  guest_id INTEGER REFERENCES guests(id) ON DELETE SET NULL,
  to_email TEXT NOT NULL,
  template_key TEXT NOT NULL,
  subject TEXT NOT NULL,
  audience TEXT NOT NULL,
  status TEXT NOT NULL,                     -- sent | failed | skipped
  provider TEXT NOT NULL,
  provider_id TEXT,
  error TEXT,
  outbox_file TEXT,
  batch_id TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_email_logs_event ON email_logs(event_id, created_at);

CREATE TABLE sent_markers (                  -- de-duplicates scheduled emails
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  marker TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (event_id, marker)
);

CREATE TABLE support_requests (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  topic TEXT NOT NULL DEFAULT 'general',
  message TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','resolved')),
  priority INTEGER NOT NULL DEFAULT 0,
  admin_notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE report_runs (                   -- log of generated reports
  id INTEGER PRIMARY KEY,
  event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  kind TEXT NOT NULL,
  format TEXT NOT NULL,
  delivered TEXT NOT NULL DEFAULT 'download', -- download | email | scheduled
  created_at TEXT NOT NULL
);

CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY,
  actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  target TEXT NOT NULL DEFAULT '',
  meta TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
