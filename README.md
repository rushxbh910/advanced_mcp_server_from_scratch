# Notes MCP Server

An AI-powered "second brain" built as a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server. Connect it to Claude Desktop, Cursor, or any MCP-compatible client and start saving, searching, and organizing notes through natural conversation.

**Live demo:** `https://mcp-proj-production.up.railway.app/mcp`

---

## What it does

You talk to your AI assistant naturally. It calls the right tool behind the scenes.

| You say | What happens |
|---|---|
| *"Save a note: always use pgvector cosine distance"* | Note saved + embedded for semantic search |
| *"Find my notes about databases"* | Vector similarity search across all your notes |
| *"What are my TODOs?"* | Extracts notes flagged as tasks/todos |
| *"Generate my standup for today"* | Report of notes created in the last 24 hours |
| *"Organize my notes into topics"* | K-Means clustering groups notes by theme |
| *"Use my project wisdom to review this code"* | Loads all your notes as AI context |

---

## Tech stack

| Layer | Technology |
|---|---|
| MCP framework | [FastMCP](https://gofastmcp.com) |
| Database | PostgreSQL + [pgvector](https://github.com/pgvector/pgvector) |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) |
| Clustering | scikit-learn K-Means |
| Auth | [Stytch](https://stytch.com) JWT (OAuth 2.0) |
| Deploy | Docker + [Railway](https://railway.app) |

---

## Tools

| Tool | Description |
|---|---|
| `add_note` | Save a note. URLs are auto-scraped. TODOs auto-detected. Embeds for search. |
| `get_my_notes` | List all your notes with categories. |
| `search_notes` | Semantic vector search using pgvector cosine distance. |
| `update_note` | Edit a note and re-embed it automatically. |
| `delete_note` | Delete a note by ID. |
| `extract_todos` | List all notes flagged as tasks/action items. |
| `generate_standup_report` | Notes from the last 24 hours, formatted as a standup. |
| `organize_my_notes` | K-Means clustering to auto-categorize notes by topic. |

**Resource:** `note://{id}` — read a specific note directly into AI context.  
**Prompt:** `project_onboarding` — injects all your notes as AI system context.

---

## Use the hosted instance

Don't want to deploy your own? Connect directly to the live server:

1. Add this to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "notes": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp-proj-production.up.railway.app/mcp"]
    }
  }
}
```

2. Restart Claude Desktop — that's it. No signup, no deployment.

> **Note:** The hosted instance requires an invite to get an isolated workspace. Without auth, all users share the same notes pool. To request access, open an issue on this repo.

---

## Deploy your own instance

See [DEPLOY.md](DEPLOY.md) for the full guide. Short version:

1. Fork this repo
2. Create a [Railway](https://railway.app) project → deploy from GitHub → add PostgreSQL plugin
3. Set environment variables (see `.env.example`)
4. Railway builds the Docker image and deploys automatically

The Dockerfile pre-downloads the embedding model at build time — no cold-start delay.

---

## Run locally

**Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/), Docker

```bash
git clone https://github.com/your-username/advanced-mcp-server-from-scratch
cd advanced-mcp-server-from-scratch

cp .env.example .env
# Edit .env: set DATABASE_URL and AUTH_ENABLED=false for local dev

docker compose up db -d          # Start PostgreSQL only
uv run python main.py            # Start the MCP server
```

Server runs at `http://localhost:8000/mcp`.

---

## Connect to Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "notes": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://your-railway-domain.up.railway.app/mcp"]
    }
  }
}
```

Restart Claude Desktop. The notes tools will be available in every conversation.

**Cursor / other MCP clients:** use the same URL in your MCP settings.

---

## Multi-user isolation

With `AUTH_ENABLED=true` and Stytch configured, each user authenticates via OAuth before connecting. Their notes are fully isolated — stored under their Stytch user ID. No user can see another's notes.

See [DEPLOY.md](DEPLOY.md) for the Stytch setup steps.

---

## Environment variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `AUTH_ENABLED` | `true` to require Stytch auth, `false` for dev |
| `BASE_URL` | Public URL of this server (used for OAuth metadata) |
| `STYTCH_DOMAIN` | Your Stytch project domain |
| `STYTCH_PROJECT_ID` | Your Stytch project ID |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins (blank = allow all) |
| `PORT` | Server port (default `8000`) |

See `.env.example` for a template.
