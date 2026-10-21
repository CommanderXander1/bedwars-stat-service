import sqlite3
from flask import Flask, request


app = Flask(__name__)


"""
convention for json payload

{
    "username": "username",
    "tag": "tags",
    "notes": "notes"
}
""" 


@app.route("/query/<user>", methods=['GET'])
def query(user):
    if user is not None:
        data, status = get_user(user)
        if type(data) != str:
            data = {"username": data[0], "added_by": data[1], "tag": data[2], "notes": data[3]}
        return data, status
    return "query must include username"


@app.route("/query-all", methods=['GET'])
def query_all():
    data, status = get_user(user=None, all=True)
    return data, status


@app.route("/add", methods=['POST'])
def add_player():
    data = request.get_json()
    if data.get("username") is not None:
        return add_user(data.get("username"), added_by=data.get("added_by"), tag=data.get("tag"), notes=data.get("notes"))
    return "query must include username", 400


def connect(path="database.db") -> tuple[sqlite3.Connection, sqlite3.Cursor]:
    # creates db if it doesn't exist
    con = sqlite3.connect(path)
    cursor = con.cursor()
    return con, cursor


def init_db(path="database.db") -> None:
    con, cur = connect()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS players (
            username TEXT PRIMARY KEY COLLATE NOCASE,
            added_by TEXT,
            tag TEXT NOT NULL CHECK (tag IN ('blatant', 'closet', 'boosted', 'toggles')),
            notes TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
    """)
    con.commit()
    con.close()
    

# overwrite if already exists
def add_user(username, added_by, tag, notes) -> tuple[str, int]:
    try:
        con, cur = connect()
        cur.execute(
            "INSERT INTO players (username, added_by, tag, notes) VALUES (?, ?, ?, ?)"
            "ON CONFLICT(username) DO UPDATE SET tag = excluded.tag, added_by = excluded.added_by, notes = excluded.notes",
            (username, added_by, tag, notes)
        )
        con.commit()
        con.close()
        return "ok", 200
    except Exception as e:
        return repr(e), 400


def get_user(user, all=False) -> tuple[str, int]:
    try:
        con, cur = connect()
        if all:
            cur.execute(
                "SELECT * FROM players"
            )
            data = cur.fetchall()
            cur.close()
            if data is None:
                return "", 400
            return data, 200
        else:
            cur.execute(
                "SELECT * FROM players WHERE username = ?", (user,)
            )
            data = cur.fetchone()
            cur.close()
            if data is None:
                return "", 400
            return data, 200
    except Exception as e:
        cur.close()
        return repr(e), 400



if __name__ == "__main__":
    init_db()
    app.run(port=5000)