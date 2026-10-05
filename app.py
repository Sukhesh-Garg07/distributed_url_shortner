import os
import string
from datetime import datetime, timezone
from urllib.parse import urlparse

import redis
from flask import Flask, jsonify, redirect, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///urls.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Config
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
USE_CACHE = os.getenv("USE_CACHE", "1") == "1"  # set USE_CACHE=0 to benchmark without Redis
CACHE_TTL = int(os.getenv("CACHE_TTL", 3600))   # seconds
ID_OFFSET = 100000                              # keeps short codes at a reasonable minimum length
ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase  # base62

cache = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True
)


class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    short_code = db.Column(db.String(12), unique=True, index=True)
    long_url = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


def encode_base62(num: int) -> str:
    """Convert an integer ID to a base62 string. Unique ID -> unique code, no collisions."""
    if num == 0:
        return ALPHABET[0]
    chars = []
    while num:
        num, rem = divmod(num, 62)
        chars.append(ALPHABET[rem])
    return "".join(reversed(chars))


def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


# cache helpers (fail open: if Redis is down, fall back to the DB)
def cache_get(key):
    if not USE_CACHE:
        return None
    try:
        return cache.get(key)
    except redis.RedisError:
        return None


def cache_set(key, value):
    if not USE_CACHE:
        return
    try:
        cache.set(key, value, ex=CACHE_TTL)
    except redis.RedisError:
        pass


def incr_clicks(code):
    try:
        cache.incr(f"clicks:{code}")
    except redis.RedisError:
        pass


#  routes 
@app.post("/api/shorten")
def shorten():
    data = request.get_json(silent=True) or {}
    long_url = data.get("url", "").strip()
    if not is_valid_url(long_url):
        return jsonify(error="Provide a valid http(s) URL in 'url'"), 400

    entry = URL(long_url=long_url)
    db.session.add(entry)
    db.session.flush()  # assigns entry.id without committing
    entry.short_code = encode_base62(entry.id + ID_OFFSET)
    db.session.commit()

    cache_set(f"url:{entry.short_code}", long_url)
    return jsonify(short_code=entry.short_code, short_url=f"{BASE_URL}/{entry.short_code}"), 201


@app.get("/<code>")
def redirect_to_long(code):
    long_url = cache_get(f"url:{code}")  # 1) try Redis
    if long_url is None:
        entry = URL.query.filter_by(short_code=code).first()  # 2) fall back to DB
        if entry is None:
            return jsonify(error="Short URL not found"), 404
        long_url = entry.long_url
        cache_set(f"url:{code}", long_url)  # 3) populate cache for next time

    incr_clicks(code)
    return redirect(long_url, code=302)  # 302 so every visit hits us and gets counted


@app.get("/api/stats/<code>")
def stats(code):
    entry = URL.query.filter_by(short_code=code).first()
    if entry is None:
        return jsonify(error="Short URL not found"), 404
    try:
        clicks = int(cache.get(f"clicks:{code}") or 0)
    except redis.RedisError:
        clicks = None
    return jsonify(
        short_code=code,
        long_url=entry.long_url,
        created_at=entry.created_at.isoformat(),
        clicks=clicks,
    )


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
