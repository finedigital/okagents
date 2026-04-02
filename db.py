import sqlite3

DB_PATH = "okagents.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        telegram_id TEXT PRIMARY KEY,
        okx_key TEXT, okx_secret TEXT, okx_passphrase TEXT
    )""")
    conn.commit()
    return conn


def save_user(telegram_id, key, secret, passphrase):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?)",
                 (telegram_id, key, secret, passphrase))
    conn.commit()


def get_user(telegram_id):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT okx_key, okx_secret, okx_passphrase FROM users WHERE telegram_id=?",
        (telegram_id,)).fetchone()
    return {"key": row[0], "secret": row[1], "passphrase": row[2]} if row else None
