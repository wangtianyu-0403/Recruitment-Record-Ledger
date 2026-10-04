CREATE TABLE applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    position_name TEXT NOT NULL,
    job_description TEXT NOT NULL DEFAULT '',
    application_date TEXT NOT NULL,
    status TEXT NOT NULL,
    company_url TEXT NOT NULL DEFAULT '',
    recruitment_url TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    salary TEXT NOT NULL DEFAULT '',
    contact_name TEXT NOT NULL DEFAULT '',
    contact_info TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    follow_up_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    manual_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    old_status TEXT,
    new_status TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);
PRAGMA user_version = 2;
