import sqlite3

DB_NAME = "black_reserve.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def add_user(user_id, username):
    conn = sqlite3.connect(DB_NAME)

    conn.execute(
        """
        def change_balance(user_id, amount):
    conn = sqlite3.connect(DB_NAME)

    conn.execute(
        """
        UPDATE users
        SET balance = balance + ?
        WHERE user_id = ?
        """,
        (amount, user_id)
    )

    conn.commit()
    conn.close()
        INSERT OR IGNORE INTO users (user_id, username, balance)
        VALUES (?, ?, 0)
        """,
        (user_id, username)
    )

    conn.commit()
    conn.close()


def get_balance(user_id):
    conn = sqlite3.connect(DB_NAME)

    result = conn.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    return result[0] if result else 0


def get_users_count():
    conn = sqlite3.connect(DB_NAME)

    result = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()

    conn.close()

    return result[0]
