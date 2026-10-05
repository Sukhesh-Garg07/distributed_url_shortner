# URL Shortener

A URL shortening service built with **Flask**, **SQLite (SQLAlchemy)** and **Redis**. It converts long URLs into compact links with unique identifiers, redirects visitors, and tracks click analytics. Redis caches the short code → long URL mapping to reduce database reads on redirects.

## Features

- `POST /api/shorten` – create a short link
- `GET /<code>` – redirect to the original URL (Redis cache first, DB fallback)
- `GET /api/stats/<code>` – analytics (original URL, created time, click count)
- Collision-free short codes: the auto-increment DB ID is base62-encoded, so every code is unique by construction
- Cache-aside pattern with TTL; if Redis is down, the app falls back to the database

## Architecture

```
Client ──> Flask API ──> Redis (cache hit) ──> 302 redirect
                │
                └──(cache miss)──> SQLite/DB ──> populate Redis ──> 302 redirect
```

## Getting started

```bash
git clone https://github.com/Sukhesh-Garg07/distributed-url-shortener.git
cd distributed-url-shortener

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

docker compose up -d      # starts Redis on :6379
python app.py             # API on http://localhost:5000
```

## API usage

```bash
# Create a short URL
curl -X POST http://localhost:5000/api/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/Sukhesh-Garg07"}'
# {"short_code":"q0U","short_url":"http://localhost:5000/q0U"}

# Follow the redirect
curl -i http://localhost:5000/q0U

# View analytics
curl http://localhost:5000/api/stats/q0U
```

## Benchmarking the cache

`benchmark.py` measures redirect latency over N requests. Run it with the cache off and on:

```bash
USE_CACHE=0 python app.py     # terminal 1, then: python benchmark.py   (terminal 2)
USE_CACHE=1 python app.py     # restart, then:    python benchmark.py
```

| Mode          | Avg latency | p95 |
|---------------|-------------|-----|
| Without Redis | _fill in_   | _fill in_ |
| With Redis    | _fill in_   | _fill in_ |

> Fill the table with your own measured numbers. Results vary by machine, and SQLite on a small table is already fast, so the gap may be smaller or larger than expected.

## Configuration

| Env var        | Default                    | Purpose                        |
|----------------|----------------------------|--------------------------------|
| `DATABASE_URL` | `sqlite:///urls.db`        | SQLAlchemy database URI        |
| `REDIS_URL`    | `redis://localhost:6379/0` | Redis connection               |
| `BASE_URL`     | `http://localhost:5000`    | Prefix for returned short URLs |
| `CACHE_TTL`    | `3600`                     | Cache expiry in seconds        |
| `USE_CACHE`    | `1`                        | Set `0` to disable Redis reads |

## Possible improvements

- Persist click counts to the DB periodically (currently stored in Redis)
- Custom aliases and link expiry
- Rate limiting, Postgres, and multiple app instances behind a load balancer
