# Project Document — MCP Memory Server

A comprehensive A–Z reference for the project. For user-facing setup, see [README.md](README.md). For deployment steps, see [DEPLOY.md](DEPLOY.md).

---

## 1. Identity

| Field | Value |
|---|---|
| **Project name** | MCP Memory Server (working title; repo: `advanced-mcp-server-from-scratch`) |
| **Tagline** | An AI-powered "second brain" for LLM agents, served over Model Context Protocol |
| **Repository** | `advanced-mcp-server-from-scratch` |
| **Hosted endpoint** | `https://mcp-proj-production.up.railway.app/mcp` |
| **Status** | Production, public, single-instance |
| **Primary owner** | Sole author / end-to-end contributor |
| **License** | (not specified — add before public release) |

---

## 2. Problem & Motivation

LLM agents (Claude Desktop, Cursor, and any MCP-compatible client) are **stateless across sessions**. They forget every rule, decision, and piece of context the moment a conversation ends. The user has to re-explain their preferences, architecture choices, and active TODOs on every new chat.

**The gap:** there is no persistent, semantically-searchable memory layer that an agent can read from and write to natively, with per-user isolation and production-grade security.

**The bet:** the **Model Context Protocol (MCP)** is the right abstraction. Build a single server that exposes memory operations as MCP tools, and any MCP-aware agent can call them without bespoke integration code.

---

## 3. Solution Overview

A self-hosted, multi-tenant MCP server that gives any LLM client a persistent, vector-searchable note store. The agent talks to it through natural language; the server translates that into tool calls, embeddings, and SQL.

**One-sentence elevator pitch:** *"Talk to your AI naturally — saving notes, recalling them by meaning (not keywords), auto-organizing them by topic, and generating standups, all through MCP tool calls."*

---

## 4. Architecture

```
                       ┌──────────────────────────────────┐
                       │ LLM Client (Claude Desktop /     │
                       │ Cursor / any MCP-aware agent)    │
                       └────────────────┬─────────────────┘
                                        │  Streamable HTTP (MCP)
                                        │  + OAuth 2.0 JWT (Stytch)
                                        ▼
                       ┌──────────────────────────────────┐
                       │ Starlette Middleware Stack       │
                       │  • CORS                          │
                       │  • RateLimit (60 req/IP/min)     │
                       └────────────────┬─────────────────┘
                                        ▼
                       ┌──────────────────────────────────┐
                       │ FastMCP Server (main.py)         │
                       │  • 8 tools                       │
                       │  • 1 resource template           │
                       │  • 1 dynamic prompt              │
                       └─────┬───────────────────────┬────┘
                             │                       │
                             ▼                       ▼
                ┌───────────────────────┐  ┌──────────────────────┐
                │ Sentence-Transformer  │  │ scikit-learn         │
                │ all-MiniLM-L6-v2      │  │ K-Means clustering   │
                │ (384-dim embeddings)  │  │                      │
                └───────────┬───────────┘  └──────────┬───────────┘
                            │                         │
                            ▼                         ▼
                       ┌──────────────────────────────────┐
                       │ PostgreSQL 16 + pgvector         │
                       │  • `notes` table                 │
                       │  • cosine-distance ANN search    │
                       │  • per-user partitioning by      │
                       │    Stytch `sub` claim            │
                       └──────────────────────────────────┘
```

**Request flow (example: `search_notes("vector databases")`):**

1. Agent sends JSON-RPC tool call over streamable HTTP to `/mcp`.
2. Rate-limit middleware admits the request (per-IP sliding window).
3. CORS middleware validates origin.
4. FastMCP verifies the Stytch-issued JWT (RS256 via JWKS).
5. Tool handler extracts the `sub` claim → user ID.
6. Query string is embedded by the in-process sentence-transformer.
7. SQLAlchemy issues a pgvector cosine-distance ORDER BY scoped to `user_id`.
8. Top-K rows are formatted and returned to the agent.

---

## 5. Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Language | Python 3.12+ | Mature ML ecosystem; FastMCP is Python-native |
| Package manager | [uv](https://docs.astral.sh/uv/) | Fast, reproducible builds via `uv.lock` |
| MCP framework | [FastMCP](https://gofastmcp.com) ≥ 3.0.1 | Idiomatic decorator-based tool registration |
| Web transport | Starlette (via FastMCP) | Async, middleware-friendly |
| Database | PostgreSQL 16 | ACID, mature, free managed offerings |
| Vector store | [pgvector](https://github.com/pgvector/pgvector) | Same DB, no extra service to operate |
| ORM | SQLAlchemy 2.0 | Battle-tested, supports pgvector via `pgvector.sqlalchemy` |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | 384 dims, CPU-friendly, MIT-licensed |
| Clustering | scikit-learn `KMeans` | Lightweight, deterministic with `random_state=42` |
| Auth | [Stytch](https://stytch.com) (OAuth 2.0 + JWT RS256) | Hosted IdP, magic-link onboarding |
| HTTP client | httpx | Async, used for URL enrichment scraping |
| HTML parsing | BeautifulSoup4 | URL-enrichment cleanup |
| Container | Docker (python:3.12-slim) | Reproducible deploy artifact |
| Local stack | docker-compose | One-command Postgres + app |
| Hosting | Railway | Managed Postgres-with-pgvector, GitHub-triggered builds |

---

## 6. Core Features

### 6.1 Persistent semantic memory
Every note is embedded into a 384-dim vector at write time, stored alongside the raw text in PostgreSQL. Retrieval is by **meaning**, not keywords, via pgvector cosine distance.

### 6.2 URL auto-enrichment
If a note contains an HTTP(S) URL, the server fetches it with httpx, strips `<script>`/`<style>`, extracts text up to 2,000 chars, and appends it to the embedding input. The agent's note becomes the agent's bookmark.

### 6.3 TODO auto-detection
A regex (`\b(todo|fixme|meeting|task|action item)\b`, case-insensitive) flags any note containing task language. `extract_todos` surfaces these without the user needing to tag anything.

### 6.4 Standup generation
`generate_standup_report` returns all notes from the last 24 hours formatted as a markdown standup. Useful for daily syncs without lifting a finger.

### 6.5 Unsupervised topic organization
`organize_my_notes` runs K-Means (k = min(4, n_notes)) over stored embeddings, then derives a 2-word topic label per cluster from the top non-stopword tokens, and writes the label back to each note's `category` column. Zero LLM cost — pure embedding-space clustering.

### 6.6 Code-context awareness
Notes can carry `file_path`, `line_number`, and `code_snippet` fields, so an agent can save "this auth bug is at `auth.py:42`" and retrieve it with the snippet attached.

### 6.7 Project onboarding prompt
The `project_onboarding` MCP prompt assembles every stored note for the current user into a system-prompt block — turning accumulated wisdom into ambient AI context on demand.

### 6.8 Multi-tenant workspace isolation
Every database query is filtered by the JWT `sub` claim. No user can see, mutate, or delete another's notes.

---

## 7. MCP Surface

### 7.1 Tools (8 total)

| Tool | Inputs | Behavior |
|---|---|---|
| `add_note` | `content`, optional `file_path`, `line_number`, `code_snippet` | Scrapes URLs in content, detects TODOs, embeds, persists |
| `get_my_notes` | — | Lists all notes for the current user with category labels |
| `search_notes` | `query`, `top_k` (default 5) | Embeds query, returns nearest neighbors by cosine distance |
| `update_note` | `note_id`, `new_content` | Updates content and re-embeds |
| `delete_note` | `note_id` | User-scoped delete |
| `extract_todos` | — | Returns notes where `is_task = 1` |
| `generate_standup_report` | — | Markdown report of last-24-hour notes |
| `organize_my_notes` | — | K-Means clusters up to 1,000 notes, writes back category labels |

### 7.2 Resources (1 template)

| URI | Output |
|---|---|
| `note://{note_id}` | Markdown blob: ID, timestamp, content, file path, code block |

### 7.3 Prompts (1 dynamic)

| Name | Output |
|---|---|
| `project_onboarding` | A system prompt that injects every stored note as "developer wisdom" |

---

## 8. Data Model

Single table, single source of truth.

```python
class Note(Base):
    id            Integer PK
    user_id       String  (Stytch sub claim, indexed)
    content       Text
    created_at    DateTime (UTC, default now)
    file_path     String?
    line_number   Integer?
    code_snippet  Text?
    web_context   Text?      # from URL enrichment
    category      String?    # written by organize_my_notes
    is_task       Integer    # 0 or 1 (TODO detection)
    embedding     Vector(384)  # pgvector
```

**Schema bootstrap:** `init_db()` (in `database.py:31`) runs `CREATE EXTENSION IF NOT EXISTS vector` and `Base.metadata.create_all()` on every server start — idempotent, no migration tool needed yet.

**Index strategy today:**
- `user_id` is B-tree indexed.
- `embedding` has no ANN index — sequential cosine-distance scan is fine at small N.

**Index strategy at scale (documented for future):**
```sql
CREATE INDEX ON notes USING hnsw (embedding vector_cosine_ops);
```

---

## 9. Authentication & Authorization

### 9.1 Flow
1. User authenticates against **Stytch** via OAuth 2.0 (magic link or social).
2. Stytch issues an RS256-signed JWT.
3. MCP client (`mcp-remote`) attaches it to every `/mcp` request.
4. FastMCP's `JWTVerifier` fetches Stytch's JWKS, validates `iss`, `aud`, signature.
5. The `sub` claim is extracted in `_get_user_id()` (`main.py:86`) and used as the partitioning key.

### 9.2 Dev mode
`AUTH_ENABLED=false` short-circuits to a `dev_user` identity — used by `test_e2e.py` and local development. Never deploy this way.

### 9.3 Authorization
Every tool handler calls `_get_user_id()` and scopes its SQL by `user_id`. There is no admin escalation path.

---

## 10. Multi-Tenant Isolation

| Concern | Mechanism |
|---|---|
| Read isolation | `WHERE user_id = :sub` on every SELECT |
| Write isolation | `user_id` is set from JWT, never from request body |
| Delete isolation | `WHERE id = :id AND user_id = :sub` |
| Embedding isolation | Embedding storage is rows-of-vectors per user — search is filtered before ranking |
| Prompt isolation | `project_onboarding` reads only the caller's notes |

No cross-tenant leakage path exists in code today.

---

## 11. AI / ML Pipeline

### 11.1 Embedding model
- **Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Output dim:** 384
- **Loaded once** at module import (`main.py:37`) — held in process memory, no per-request load
- **Pre-baked** into the Docker image at build time (`Dockerfile:19`) — eliminates first-request latency

### 11.2 Inference posture
- CPU-only — `torch` is installed from PyTorch's CPU wheel index, **avoiding ~3 GB of CUDA libraries** that `sentence-transformers` would otherwise pull in.
- Synchronous (`encoder.encode(...)`) — fine at single-instance scale; would move to a worker queue under load.

### 11.3 Retrieval
- Cosine distance via pgvector's `<=>` operator, exposed by `pgvector.sqlalchemy`'s `Vector.cosine_distance(...)`.
- No re-ranker — embedding similarity is the only signal. Adequate for personal-knowledge scale (≤ 10k notes per user).

### 11.4 Clustering
- K-Means with `k = min(4, n)`, `n_init="auto"`, `random_state=42`.
- Label derivation: top-2 non-stopword tokens by frequency across each cluster's notes — keeps labels human-readable without an LLM call.
- Capped at 1,000 notes per call to bound compute.

---

## 12. Middleware Stack

Applied in `main.py:361` at server start:

| Middleware | Configuration | Purpose |
|---|---|---|
| `RateLimitMiddleware` | 60 req / IP / 60 s sliding window | Cheap abuse protection |
| `CORSMiddleware` | Origins from `ALLOWED_ORIGINS` env (default `*`) | Browser-based MCP clients |

The rate limiter holds state in a per-process `defaultdict[str, list[float]]`. **Correct for single-instance** deployments; replace with Redis if horizontally scaled.

---

## 13. Deployment

### 13.1 Production target
**Railway** — chosen for:
- Managed Postgres **with pgvector pre-installed**.
- GitHub-push-to-deploy with zero config.
- Free tier suitable for personal use.
- Single environment variable to wire Postgres into the app.

### 13.2 Build
The Dockerfile is a 3-stage logical pipeline inside a single image:

```
1. Install uv + base Python deps
2. Install CPU-only torch (avoid 3GB CUDA)
3. uv sync --frozen --no-dev --no-install-package torch
4. Pre-download all-MiniLM-L6-v2 into /app/.cache
5. EXPOSE 8000; CMD uv run python main.py
```

### 13.3 Image characteristics
| Metric | Value |
|---|---|
| Base image | `python:3.12-slim` |
| Final image size | ~900 MB (vs ~3 GB if CUDA torch were included) |
| Cold start | ~0 seconds for model load (pre-baked) |
| Build time (cached) | < 1 minute |
| Build time (cold) | ~5 minutes |

### 13.4 Portability
Nothing in the stack is Railway-specific. Same image runs on:
- AWS ECS / Fargate (push to ECR, point Postgres at RDS with pgvector enabled)
- Google Cloud Run (with Cloud SQL Postgres)
- Fly.io
- Any Kubernetes cluster (would need a `Deployment` + `Service` manifest)

---

## 14. Local Development

```bash
# 1. Clone and configure
cp .env.example .env
# Edit: set AUTH_ENABLED=false, set POSTGRES_PASSWORD

# 2. Start the database
docker compose up db -d

# 3. Run the app
uv run python main.py
# → http://localhost:8000/mcp
```

Or run the whole stack containerized:
```bash
docker compose up
```

---

## 15. Testing

### 15.1 Suite
`test_e2e.py` is a black-box end-to-end suite. It:
1. Spawns the server as a subprocess (`AUTH_ENABLED=false`).
2. Waits for `/mcp` to become reachable.
3. Connects via the FastMCP `Client`.
4. Walks all 8 tools, the resource template, and the prompt.

### 15.2 Coverage matrix

| # | Scenario | Tool |
|---|---|---|
| 1 | Tool discovery | `list_tools` |
| 2 | Plain note add | `add_note` |
| 3 | TODO regex detection | `add_note` |
| 4 | Code-context note | `add_note` |
| 5 | ML-topic note for clustering | `add_note` |
| 6 | Note listing | `get_my_notes` |
| 7 | Semantic search top-k | `search_notes` |
| 8 | Note edit + re-embed | `update_note` |
| 9 | TODO extraction | `extract_todos` |
| 10 | Standup generation | `generate_standup_report` |
| 11 | K-Means clustering | `organize_my_notes` |
| 12 | Category persistence | `get_my_notes` |
| 13 | Delete + idempotent delete | `delete_note` |
| 14 | Resource template registration | `list_resource_templates` |
| 15 | Prompt registration | `list_prompts` |

### 15.3 Running
```bash
DATABASE_URL=postgresql://notesuser:testpass123@localhost:5433/notesdb \
  uv run python test_e2e.py
```

---

## 16. Performance Characteristics

Numbers below are observed on Railway's free tier with a small note set (< 100 notes per user). They are honest order-of-magnitude estimates, not benchmarked SLAs.

| Operation | Latency (p50) | Notes |
|---|---|---|
| `add_note` (no URL) | 50–150 ms | Dominated by `encoder.encode` |
| `add_note` (with URL) | 300–800 ms | Adds httpx fetch + parse |
| `search_notes` (top-5) | 80–200 ms | Embed query + cosine ORDER BY |
| `get_my_notes` | 20–80 ms | Pure SELECT |
| `organize_my_notes` (50 notes) | 200–500 ms | K-Means is O(n·k·iter) |
| Cold start | ~0 s for model | Pre-baked in image |

**At what point things break:**
- Single-instance rate limit ceiling: 60 req/min/IP (configurable).
- Sequential cosine scan: degrades past ~10–20k notes per user. Mitigation: HNSW index.
- In-process embedding: blocks the event loop. Mitigation: thread pool or dedicated inference service.

---

## 17. Scaling Notes

Documented but not yet implemented — captured here so the next contributor (or future me) doesn't have to rediscover them.

| Bottleneck | Mitigation |
|---|---|
| Sequential vector scan | `CREATE INDEX ON notes USING hnsw (embedding vector_cosine_ops);` |
| In-memory rate limiter under HA | Swap for Redis-backed (`slowapi` + Redis) |
| Synchronous CPU inference | Move embedding to a worker (Celery / RQ) or dedicated inference container |
| URL scraping blocking the request | Push to a background task, return note ID immediately, enrich asynchronously |
| Single Postgres | Read replicas for `search_notes`; primary for writes |

---

## 18. Configuration Reference

All configuration is via environment variables. No config files.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | Postgres connection string |
| `AUTH_ENABLED` | No | `true` | Toggle Stytch JWT verification |
| `BASE_URL` | If auth | `http://0.0.0.0:8000` | Public URL for OAuth metadata |
| `STYTCH_DOMAIN` | If auth | — | Stytch tenant URL (also JWT issuer) |
| `STYTCH_PROJECT_ID` | If auth | — | JWT audience claim |
| `ALLOWED_ORIGINS` | No | `*` | Comma-separated CORS allow-list |
| `PORT` | No | `8000` | HTTP listener port |
| `SENTENCE_TRANSFORMERS_HOME` | No | — | Cache dir for the embedding model (set to `/app/.cache/...` in Docker) |
| `POSTGRES_PASSWORD` | docker-compose only | — | Used by the `db` service |

See [`.env.example`](.env.example) for a template.

---

## 19. Repository Structure

```
.
├── main.py                # FastMCP server, tools, middleware
├── database.py            # SQLAlchemy model + pgvector bootstrap
├── test_e2e.py            # Black-box MCP client test suite
├── Dockerfile             # Production image build
├── docker-compose.yml     # Local dev: db + app
├── pyproject.toml         # Dependencies (uv-managed)
├── uv.lock                # Pinned dep graph
├── requirements.txt       # Legacy pip export (kept for reference)
├── .env.example           # Env var template
├── README.md              # User-facing setup guide
├── DEPLOY.md              # Railway + Stytch deployment guide
└── PROJECT.md             # This document
```

---

## 20. Roadmap / Future Work

Concrete, prioritized — not aspirational hand-waving.

**Near-term (next iteration):**
- Add HNSW index migration for users crossing ~5k notes.
- Move URL scraping behind a background task so `add_note` returns immediately.
- Structured logging (JSON) for Railway log filtering.

**Medium-term:**
- Redis-backed rate limiter to allow horizontal scale.
- Async embedding worker (separate container).
- Per-tool metrics: count, latency, error rate (Prometheus or Railway-native).

**Longer-term:**
- Hybrid search (BM25 + cosine) for keyword-precise queries.
- Optional re-ranker (cross-encoder) for top-K refinement.
- Token-budget-aware `project_onboarding` (summarize when over context limits).
- Web UI for non-MCP-client browsing.

---

## 21. Glossary

| Term | Meaning |
|---|---|
| **MCP** | Model Context Protocol — Anthropic's open standard for connecting LLM clients to tools and data sources. |
| **FastMCP** | Python framework for building MCP servers via decorators. |
| **pgvector** | PostgreSQL extension adding vector columns and similarity operators (`<=>`, `<#>`, `<->`). |
| **Embedding** | A fixed-length numeric vector representing the meaning of a piece of text. |
| **Cosine distance** | A similarity metric where `distance = 1 - cos(θ)` between two vectors. Smaller = more similar. |
| **K-Means** | Unsupervised algorithm that partitions vectors into K groups minimizing intra-cluster variance. |
| **JWKS** | JSON Web Key Set — the public-key endpoint used to verify JWT signatures. |
| **RS256** | RSA + SHA-256 — asymmetric JWT signing algorithm used by Stytch. |
| **`sub` claim** | The "subject" field of a JWT — uniquely identifies the user. Used here as the multi-tenant partition key. |
| **HNSW** | Hierarchical Navigable Small World — approximate-nearest-neighbor index supported by pgvector. |
| **Sliding window rate limit** | Per-IP counter that drops entries older than `window_seconds` on every request, rather than resetting on the minute. |

---

## 22. Quick Facts (for resume / interview prep)

- **8** MCP tools, **1** resource template, **1** dynamic prompt
- **15** end-to-end test scenarios covering every public surface
- **384-dim** sentence-transformer embeddings, CPU-only inference
- **~70%** Docker image size reduction by excluding CUDA libraries (~3 GB → ~900 MB)
- **0-second** model cold-start (pre-baked at image build time)
- **60 req/IP/min** sliding-window rate limit
- **OAuth 2.0 / JWT RS256** auth via Stytch with JWKS verification
- **100%** per-tenant isolation enforced at the SQL filter layer
- **Single Postgres instance** with pgvector — no separate vector database
- **Push-to-deploy** via Railway, ~5-minute cold build, sub-minute warm rebuild
