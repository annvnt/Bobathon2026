# EcoComply — AI Regulatory Compliance Platform

Full-stack implementation of the **Regulatory Radar** challenge: monitor → understand →
match → alert. Manufacturers describe a product, the AI **labels** it against the
regulatory taxonomy, a daily sync **fetches** updated regulations, and the system
**assesses** every product for compliance gaps and fires alerts — each with the gap,
the deadline, the recommended action, and a cited source.

```
backend/    FastAPI · SQLAlchemy · ChromaDB · APScheduler · LangChain (watsonx-ready)
frontend/   Next.js 14 (App Router) · TypeScript · Tailwind · dark + light themes
```

## Quick start

Two terminals.

### 1 · Backend (port 8000)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional — sensible offline defaults already work
uvicorn app.main:app --reload
```

On first boot it creates the DB, seeds the 22-company / 53-product portfolio from
`Dataset/partners.json`, and starts the daily scheduler. API docs at
`http://localhost:8000/docs`.

### 2 · Frontend (port 3000)

```bash
cd frontend
npm install
npm run dev      # http://localhost:3000
```

Open `http://localhost:3000`, sign in (any credentials), then **Run daily scan** in the
header to populate alerts.

## What runs where

| Workflow | Where | Notes |
|---|---|---|
| **A · Classify / label a product** | `services/classification.py` | Free-text → category, substances, battery/radio attributes, markets, **compliance streams**. Validated against `taxonomy.json`. |
| **B · Daily sync** | `scheduler.py` → `services/gap_analysis.run_sync` | `check_updates()` → `fetch_regulation()` → chunk + embed into ChromaDB. |
| **C · Gap analysis (RAG)** | `services/gap_analysis.py` | Structured scope match (catches look-alikes) → RAG retrieval → LLM/heuristic gap verdict → `Alert` + Twilio send. |

## The MCP boundary — connected to the real team MCP

The pipeline depends on `check_updates()` and `fetch_regulation(label, country)`, now
served by the **real team MCP** (`radar/mcp/` at the repo root) via an adapter,
[mcp_client.py](backend/app/services/mcp_client.py):

```python
from radar.mcp import contract
contract.get_regulations(category=label, country="EU", include_text=True)
contract.fetch_regulation([label], [country])   # live EUR-Lex / GADI + cache
```

`gap_analysis.py` imports `mcp_client` (real MCP) and only falls back to the bundled
`mock_mcp.py` if `radar` can't be imported. The MCP returns **real regulation text**
(EUR-Lex CELEX / German GADI), ingested into ChromaDB **line by line**, so gap citations
quote the actual legal text with real source URLs. radar's only third-party deps
(fastapi, pydantic) are already in the backend venv; the repo root is added to `sys.path`
so `radar` imports regardless of working directory.

## LLM: OpenRouter (no mocks)

Classification and gap analysis run on a **real LLM via OpenRouter** — there is no mock
LLM fallback. Set your key in `backend/.env`:

```
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...        # required
OPENROUTER_MODEL=openai/gpt-4o-mini # any OpenRouter model
```

If the key is missing, LLM-backed endpoints return a clean `503 LLM unavailable` (the rest
of the app — dashboards, analytics, product pages — keeps working on existing data). The LLM
also produces the per-line **cause → effect** analysis and product/business impacts.

## Pluggable providers (config only, no code changes)

| Setting | Default | Options |
|---|---|---|
| `LLM_PROVIDER` | `openrouter` | `watsonx` (IBM Bob via LangChain) |
| `ALERTS_PROVIDER` | `mock` (logs alerts) | `twilio` (real SMS/WhatsApp) |
| `DATABASE_URL` | `sqlite:///./ecocomply.db` | any Postgres URL |

## Navigation & per-product analytics

- **Dynamic island** — navigation is a floating, morphing pill (`components/dynamic-island.tsx`)
  that shows icons collapsed and expands the active section's label; a separate floating
  controls pill holds the company selector, scan trigger and theme toggle. No sidebar.
- **Per-product analytics** — each product card links to `/products/[id]`: product risk /
  compliance health / fine-exposure orbs, regulation coverage, deadlines and its gaps
  (`GET /api/analytics/product/{id}`).

## Key API endpoints

```
POST /api/login                 # resolve partner ID (P001 / 1) -> company user
POST /api/products/classify     # Workflow A — draft labels from a description
GET  /api/products              # list (optional ?user_id=)
POST /api/products              # save a verified product
POST /api/scan                  # run Workflows B+C now (manual daily-sync trigger)
GET  /api/alerts                # findings incl. line-by-line citations + impacts
POST /api/alerts/{id}/read      # mark read
GET  /api/dashboard/metrics     # totals
GET  /api/analytics             # orbs, distributions, company risk, timeline
GET  /api/labels                # the labels.md map (only labels the system uses)
```

## Labeling: `Dataset/labels.md` (single source of truth)

Automated labels are emitted **only** from `Dataset/labels.md`, a parseable table derived
from `SOURCES.md`. Each row maps a label → regulation reference, source URL, and trigger
tokens (`eee`, `battery`, `radio`, `consumer`, `substance:…`, `category:…`). The classifier
re-derives `compliance_streams` from these triggers regardless of what the LLM proposes, and
gap citations use each label's source URL. Edit the table to change behaviour — no code change.

## Login

Each partner has its own login = its **partner ID** (`P001`…`P022`, or just `1`). Signing in
scopes every page to that company; "Enter admin view" shows the whole portfolio.

## Analytics & line-by-line citations

- **Analytics** (`/analytics`) — impact orbs (portfolio risk, compliance health, fine
  exposure, deadline pressure), severity donut, gaps-by-regulation / by-category bars,
  company risk ranking, deadline timeline, and a regulation-coverage table.
- **Citations** — every regulation is stored in ChromaDB **line by line**. Each alert cites
  the specific lines with a **cause → effect** analysis, plus **product impact**, **business
  impact**, and **extracted key dates** (`services/impact.py`).

## Design notes

- **Offline embeddings** — ChromaDB uses a deterministic hashed bag-of-words embedder so
  the demo needs no model download or network. Swap `_OfflineEmbeddingFunction` in
  `vector_store.py` for sentence-transformers / watsonx embeddings for production recall.
- **Scope-exclusion reasoning** — `_applies()` skips products that are the right category
  but wrong market / wrong substance (the look-alike cases), and logs *why*. This is the
  false-positive avoidance the challenge rewards.
- **Every alert cites its source** (`source_url`) and carries a confidence score.
