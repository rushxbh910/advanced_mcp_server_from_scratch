# Deployment Guide

This server is a FastMCP HTTP server backed by PostgreSQL + pgvector.  
Recommended host: **Railway** — managed Postgres with pgvector, Docker deploy, free tier.

---

## 1  Create a Railway project

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
2. Point it at your fork of this repo — Railway auto-detects the Dockerfile
3. Add a **PostgreSQL** database: Railway canvas → **+ New** → **Database** → **PostgreSQL**
4. Railway auto-provisions it with pgvector already enabled

---

## 2  Set environment variables

Railway → your app service → **Variables** tab:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Copy from the Postgres plugin's Variables tab |
| `AUTH_ENABLED` | `true` (or `false` for dev/testing) |
| `BASE_URL` | Your Railway public URL — **Settings → Networking → Generate Domain** (include `https://`) |
| `STYTCH_DOMAIN` | From Stytch dashboard → API Keys (e.g. `https://xxx.customers.stytch.dev`) |
| `STYTCH_PROJECT_ID` | From Stytch dashboard → API Keys |
| `ALLOWED_ORIGINS` | Leave blank to allow all origins |
| `PORT` | `8000` |
| `SENTENCE_TRANSFORMERS_HOME` | `/app/.cache/sentence_transformers` |

---

## 3  Deploy

Railway triggers a build on every push to `main`.  
The Dockerfile:
- Installs CPU-only PyTorch (avoids 3GB CUDA libraries)
- Installs all deps from `uv.lock` (reproducible builds)
- Pre-downloads the `all-MiniLM-L6-v2` model (no cold-start delay)

First build takes ~5 minutes. Subsequent builds are faster (Docker layer cache).

---

## 4  Enable multi-user auth (Stytch)

For each user to have isolated notes, configure OAuth via Stytch:

### 4a — Create a Stytch Connected App

1. [stytch.com](https://stytch.com) → your project → **Connected Apps** → **New connected app**
2. Set **Redirect URIs** to: `http://localhost:3334/oauth/callback`
3. Save

### 4b — Invite users

Stytch dashboard → **Users** → **Invite user** → enter their email  
They receive a magic link to create their account.

### 4c — User connects

Each user adds this to their `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "notes": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://your-domain.up.railway.app/mcp"]
    }
  }
}
```

On first connect, a browser window opens for Stytch login. After login, their notes are fully isolated under their Stytch user ID.

---

## 5  Connect from Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "notes": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://your-domain.up.railway.app/mcp"]
    }
  }
}
```

Restart Claude Desktop — the notes tools appear in every conversation.

---

## Local development

```bash
cp .env.example .env        # set DATABASE_URL, AUTH_ENABLED=false
docker compose up           # starts PostgreSQL + app together
```

Or run just the app (if PostgreSQL is already running):
```bash
AUTH_ENABLED=false DATABASE_URL=postgresql://... uv run python main.py
```

MCP endpoint: `http://localhost:8000/mcp`

---

## Scaling notes

- **Single instance**: current setup works as-is. The in-memory rate limiter is correct.
- **Multiple instances**: swap the in-memory rate limiter for Redis-backed (`slowapi` + Redis). The DB and pgvector are already stateless-friendly.
- **Large note sets**: add a pgvector HNSW index for fast approximate nearest-neighbour search:
  ```sql
  CREATE INDEX ON notes USING hnsw (embedding vector_cosine_ops);
  ```
