# ----------------------------
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 pinkabels
# ----------------------------
# services/db.py
# ----------------------------
import sqlite3

db = sqlite3.connect("data/social.db")

def init():
    db.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        username TEXT PRIMARY KEY,
        last_post_id TEXT,
        last_seen INTEGER
    )
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS seen_posts (
        username TEXT,
        post_id TEXT,
        PRIMARY KEY (username, post_id)
    )
    """)

    db.commit()

def add_account(username):
    db.execute(
        """
        INSERT OR IGNORE INTO accounts
        VALUES (?, NULL, NULL)
        """,
        (username,),
    )
    db.commit()

def get_accounts():
    return db.execute(
        """
        SELECT username,last_post_id,last_seen
        FROM accounts
        """
    ).fetchall()

def get_last_post(username):
    row = db.execute(
        """
        SELECT last_post_id
        FROM accounts
        WHERE username = ?
        """,
        (username,),
    ).fetchone()

    return row[0] if row else None

def set_last_post(username, post_id):
    db.execute(
        """
        UPDATE accounts
        SET last_post_id = ?
        WHERE username = ?
        """,
        (post_id, username),
    )
    db.commit()

def has_seen_post(username, post_id):
    row = db.execute(
        """
        SELECT 1
        FROM seen_posts
        WHERE username = ?
        AND post_id = ?
        """,
        (username, post_id),
    ).fetchone()

    return row is not None


def mark_seen_post(username, post_id):
    db.execute(
        """
        INSERT OR IGNORE INTO seen_posts
        VALUES (?, ?)
        """,
        (username, post_id),
    )

    db.execute(
        """
        DELETE FROM seen_posts
        WHERE rowid NOT IN (
            SELECT rowid
            FROM seen_posts
            WHERE username = ?
            ORDER BY rowid DESC
            LIMIT 5
        )
        AND username = ?
        """,
        (username, username),
    )

    db.commit()
