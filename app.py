import sqlite3
from flask import Flask, request, render_template, url_for, session, redirect, flash, jsonify
from hashlib import sha256
from functools import wraps
import datetime
import os
import dotenv

dotenv.load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")


"""
convention for json payload

{
    "username": "username",
    "tag": "tags",
    "notes": "notes"
}
"""


def connect(path="database.db") -> tuple[sqlite3.Connection, sqlite3.Cursor]:
    # creates db if it doesn't exist
    con = sqlite3.connect(path)
    cursor = con.cursor()
    return con, cursor


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/", methods=['GET'])
@login_required
def home():
    data, status = get_user(user=None, all=True)
    data.reverse()
    recent_players = 0
    tag_counts = {}
    for player in data:
        if datetime.datetime.strptime(player[4], "%Y-%m-%d %H:%M:%S") > (datetime.datetime.now() - datetime.timedelta(days=7)):
            recent_players += 1
        if player[2] in tag_counts:
            tag_counts[player[2]] += 1
        else:
            tag_counts[player[2]] = 1
        
    return render_template("index.html", players=data, total_players=len(data), recent_players=recent_players, tag_counts=tag_counts)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))
    if request.method == 'GET':
        return render_template('login.html')
    if request.method == 'POST':
        username = request.form.get("username")
        password_hash = sha256(request.form.get("password").encode()).hexdigest()

        con, cur = connect()
        cur.execute("SELECT username, password FROM user WHERE username = ?", (username,))
        data = cur.fetchone()

        if data is not None and password_hash == data[1]:
            session["username"] = username
            return redirect(url_for("home"))
        flash("Incorrect username or password", "error")
        return render_template("login.html")


@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/query/<user>", methods=['GET'])
def query(user):
    if user is not None:
        data, status = get_user(user)
        if type(data) != str:
            data = {"username": data[0], "added_by": data[1], "tag": data[2], "notes": data[3]}
        return jsonify(data), 200
    return "query must include username"


@app.route("/query-all", methods=['GET'])
@login_required
def query_all():
    data, status = get_user(user=None, all=True)
    return data, status


@app.route("/add", methods=['POST'])
@login_required
def add_player():
    data = request.get_json()
    if data.get("username") is not None:
        response = add_user(data.get("username"), added_by=data.get("added_by"), tag=data.get("tag"), notes=data.get("notes"))
        if response[1] == 200:
            return jsonify({"success": True, "message": f"Added user {request.form.get("username")}"}), 200
        else:
            return jsonify({"success": False, "message": f"Error adding user {request.form.get("username")}"}), 400
    return jsonify({"success": False, "message": "Query must include username"}), 200


@app.route("/whitelist_user", methods=['POST'])
@login_required
def whitelist_user():

    con, cur = connect()
    cur.execute("SELECT * FROM user WHERE username = ?", (session.get("username"),))
    data = cur.fetchone()

    # admin check
    if data[2] == 1:
        username = request.json["username"]
        password_hash = sha256(request.json["password"].encode()).hexdigest()
        cur.execute("""
            INSERT INTO user (username, password) VALUES (?, ?)
            ON CONFLICT(username) DO UPDATE SET password = excluded.password
        """, (username, password_hash))
        
        con.commit()
        con.close()

        return jsonify({"success": True, "message": f"Whitelisted user {request.form.get("username")}"}), 200
    else:
        return jsonify({"success": False, "message": "You are not an admin"}), 400


# should maybe make default 0 for stats
def init_db(path="database.db") -> None:
    con, cur = connect()
    cur.execute("""
            CREATE TABLE IF NOT EXISTS user (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                admin BOOLEAN NOT NULL DEFAULT 0,
                api_key TEXT UNIQUE
            )
        """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS player (
            username TEXT PRIMARY KEY COLLATE NOCASE,
            added_by TEXT,
            tag TEXT NOT NULL CHECK (tag IN ('blatant', 'closet', 'booster', 'sniper', 'toggler', 'alt')),
            notes TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            stats TEXT,
            FOREIGN KEY (stats) REFERENCES stats(username) ON DELETE SET NULL
        )
    """)

    cur.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                username TEXT PRIMARY KEY COLLATE NOCASE,
                star INT,
                fkdr REAL,
                wins INT,
                finals INT,
                beds INT,
                wlr REAL,
                bblr REAL,
                fps REAL,
                fpw REAL
            )
        """)


    cur.execute("""
        CREATE TABLE IF NOT EXISTS game (
            id TEXT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            player TEXT NOT NULL,
            mode TEXT NOT NULL CHECK (mode IN ('solos', 'doubles', 'threes', 'fours', '4v4', 'dreams')),
            bw_map TEXT NOT NULL,
            finals INTEGER,
            kills INTEGER,
            beds INTEGER,
            deaths INTEGER,
            fd BOOLEAN,
            won BOOLEAN
        )
    """)

    # join table for players and games
    cur.execute("""
        CREATE TABLE IF NOT EXISTS game_player (
            player TEXT REFERENCES player(username),
            game TEXT REFERENCES game(id),
            PRIMARY KEY (player, game)
        )
    """)

    # create main admin user
    cur.execute("""
        INSERT INTO user (username, password, admin) VALUES (?, ?, ?)
        ON CONFLICT DO NOTHING
    """, (os.getenv("ADMIN_USERNAME"), sha256(os.getenv("ADMIN_PASSWORD").encode()).hexdigest(), True))
    
    con.commit()
    con.close()


# overwrite if already exists
def add_user(username, added_by, tag, notes, stats=None) -> tuple[str, int]:
    try:
        con, cur = connect()
        cur.execute(
            "INSERT INTO player (username, added_by, tag, notes) VALUES (?, ?, ?, ?)"
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
                "SELECT * FROM player"
            )
            data = cur.fetchall()
            cur.close()
            if data is None:
                return "", 400
            return data, 200
        else:
            cur.execute(
                "SELECT * FROM player WHERE username = ?", (user,)
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
    app.run(port=os.getenv("PORT"))