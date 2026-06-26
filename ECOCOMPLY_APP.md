# EcoComply — Regulatory Radar Platform

> Finalised documentation for the EcoComply application (FastAPI backend + Next.js
> frontend) built for the IBM Bobathon **Regulatory Radar** challenge.
>
> **What it does:** an electronics SME describes a product → the AI labels it against
> the EU regulatory taxonomy → a sync pulls the current regulations from the team **MCP**
> → every product is assessed for compliance gaps with **line-by-line citations** of the
> real legal text → a **real alert** can be fired (Twilio). Monitor → understand → match → alert.

---

## 1. Architecture

```
                       ┌──────────────────────────── frontend/ (Next.js 14) ───────────────────────────┐
                       │  Dynamic-island nav · dark/light · cards                                       │
                       │  Login(partnerID) Dashboard Products Product[id] Alerts Analytics Settings     │
                       └──────────────────────────────┬───────────────────────────────────────────────┘
                                                       │ REST (fetch)
                       ┌───────────────────────────────▼─────────────── backend/ (FastAPI) ────────────┐
                       │  routers: products · alerts · meta(analytics/scan/labels/login)                │
                       │  services:                                                                     │
                       │    classification ── OpenRouter LLM ─────────────┐  (labels from labels.md)    │
                       │    gap_analysis ── RAG + parallel LLM ───────────┤                             │
                       │    impact (cause/effect, dates)                  │                             │
                       │    analytics (portfolio + per-product)           │                             │
                       │    mcp_client ───────► radar.mcp.contract  (REAL MCP, repo root)               │
                       │    alerts ───────────► radar.alerts.notify (REAL Twilio/SendGrid)              │
                       │  stores: SQLAlchemy (SQLite/Postgres) + ChromaDB (line-level reg text)         │
                       └───────────────────────────────┬──────────────────────────────────────────────┘
                                                        │
              ┌─────────────────────────────┬──────────┴───────────┬───────────────────────────┐
              ▼                             ▼                       ▼                           ▼
      OpenRouter (gpt-4o-mini)     radar/ MCP (EUR-Lex/GADI)   ChromaDB (.chroma)        Twilio / SendGrid
      classification + gaps        real regulation text        RAG citations             real alert delivery
```

Three external systems are **really connected** (no mocks): the LLM (OpenRouter),
the regulation MCP (`radar.mcp.contract`), and alert delivery (`radar.alerts.notify`).

---

## 2. Repository layout

```
backend/                 FastAPI app
  app/
    main.py              app + lifespan (init db, seed, scheduler) + LLM error handler
    config.py            env settings (pydantic-settings); REPO_ROOT
    database.py models.py schemas.py
    taxonomy.py          loads Dataset/taxonomy.json
    label_map.py         loads Dataset/labels.md (the only labels the system uses)
    vector_store.py      ChromaDB (offline hashed-BoW embeddings)
    scheduler.py         APScheduler daily sync
    seed.py              seeds Users/Products from Dataset/partners.json
    routers/             products.py · alerts.py · meta.py
    services/
      llm.py             OpenRouter / watsonx (no mock)
      classification.py  Workflow A — product labeling
      mcp_client.py      ► adapter to radar.mcp.contract  (REAL MCP)
      ingestion.py       chunk regulation text line-by-line → ChromaDB
      gap_analysis.py    Workflows B+C — sync, RAG, parallel LLM gap eval, alerts
      impact.py          per-line cause/effect, product/business impact, date extraction
      analytics.py       portfolio + per-product analytics
      alerts.py          ► adapter to radar.alerts.notify  (REAL Twilio/SendGrid)
frontend/                Next.js 14 (App Router, Tailwind)
  components/            dynamic-island · header(controls) · charts(orbs) · ui
  app/(app)/             dashboard · products · products/[id] · alerts · analytics · settings
  lib/                   api.ts · types.ts · theme · app-context
radar/                   TEAM MCP + alert sender (shared on main)
  mcp/contract.py        fetch_regulation/get_regulations/check
  alerts/notify.py       Twilio/SendGrid dispatch
feed/                    real regulation library (EUR-Lex CELEX + German GADI text)
Dataset/                 partners.json/.csv · taxonomy.json · labels.md · SOURCES.md
```

---

## 3. Quick start

Two terminals. Python 3.12, Node 18+.

### Backend (port 8000)
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then add your OPENROUTER_API_KEY
uvicorn app.main:app --reload
```
On first boot it creates the DB, seeds 22 companies / 53 products, connects to the MCP,
and starts the scheduler. API docs: http://localhost:8000/docs

### Frontend (port 3000)
```bash
cd frontend
npm install
npm run dev
```
Sign in with a **partner ID** (`P001`…`P022`, or `1`), or "Enter admin view" for the
whole portfolio. Press **Scan** (top-right pill) to pull regulations from the MCP and
assess every product.

> ⚠️ Never run `npm run build` while `npm run dev` is running — it corrupts `.next`.
> Use `npx tsc --noEmit` to type-check; restart dev after a production build.

---

## 4. Configuration

`backend/.env` (per-app):

| Key | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./ecocomply.db` | any Postgres URL works |
| `LLM_PROVIDER` | `openrouter` | `openrouter` \| `watsonx` |
| `OPENROUTER_API_KEY` | — | **required** for classification + gap analysis |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | any OpenRouter model |
| `ALERTS_PROVIDER` | `twilio` | `twilio` (real, via radar) \| `mock` |
| `ALERT_AUTOSEND` | `false` | if true, scans auto-send every new alert (avoid) |
| `ENABLE_SCHEDULER` | `true` | daily MCP sync at `SYNC_HOUR:SYNC_MINUTE` |

`.env` at the **repo root** (read by `radar`, gitignored): `TWILIO_ACCOUNT_SID`,
`TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `TWILIO_WHATSAPP_FROM`, `SENDGRID_*`, and
`ALERT_TO_OVERRIDE` (route every alert to one verified test recipient).

---

## 5. The three real integrations

### 5.1 LLM — OpenRouter (no mocks)
`services/llm.py` calls OpenRouter's chat-completions API (`openai/gpt-4o-mini`).
Classification predicts category/substances/attributes; gap analysis decides
`has_gap` and writes the per-line cause/effect + product/business impact. Missing key →
clean `503 LLM unavailable`; the rest of the app keeps working on existing data.

### 5.2 Regulation MCP — `radar.mcp.contract`
`services/mcp_client.py` puts the repo root on `sys.path` and wraps the team MCP:
`get_regulations(category, country, include_text=True)` and `fetch_regulation(labels,
countries)`. It maps the MCP's records (EUR-Lex CELEX + German GADI, with full legal
`text` and real `source_url`) into the pipeline's `check_updates()` /
`fetch_regulation(label, country)`. `gap_analysis.py` imports it, falling back to the
bundled `mock_mcp.py` only if `radar` can't import. The legal text is ingested into
ChromaDB **line by line**, so every gap cites the actual regulation text.

### 5.3 Alerts — `radar.alerts.notify`
`services/alerts.py` wraps the team's Twilio/SendGrid sender. Scans create alerts as
`pending` (never mass-blast); a user fires one with **Send alert** (`POST
/api/alerts/{id}/send`), routed to `ALERT_TO_OVERRIDE`. With no recipient set it safely
returns `skipped`.

---

## 6. Workflows

- **A · Classify (`POST /api/products/classify`)** — free text → labels (only from
  `labels.md`), shown in an editable form before saving.
- **B · Sync (`POST /api/scan` or daily scheduler)** — `check_updates()` →
  `fetch_regulation()` from the MCP → chunk + embed regulation text into ChromaDB.
- **C · Gap analysis** — for each in-scope product (market match + label triggers), RAG
  retrieves the most relevant regulation lines, the LLM (parallelised, 12 workers)
  decides the gap and writes cause/effect + impacts + dates → `Alert`.

---

## 7. API reference

```
POST /api/login                  partner ID (P001 / 1) → company user
GET  /api/products               list (?user_id=)
POST /api/products/classify      Workflow A
POST /api/products               save product
GET  /api/products/{id}
DELETE /api/products/{id}
GET  /api/alerts                 (?is_read=&user_id=&product_id=) incl. citations + impacts
POST /api/alerts/{id}/read
POST /api/alerts/{id}/send       fire real message (?to=&channel=sms|whatsapp|email)
GET  /api/dashboard/metrics
GET  /api/analytics              portfolio orbs/charts/timeline/company-risk
GET  /api/analytics/product/{id} per-product risk/health/exposure + coverage
POST /api/scan                   run Workflows B+C now
GET  /api/labels                 the labels.md map
GET  /api/taxonomy   GET /api/users   GET /api/health
```

---

## 8. Frontend pages

- **/login** — partner-ID sign-in (or admin view).
- **/dashboard** — risk + compliance-health orbs, metrics, recent alerts.
- **/products** — product cards (risk badge, attributes, label chips) → click for detail.
- **/products/[id]** — per-product analytics: risk/health/fine orbs, regulation coverage,
  deadlines, the product's gaps.
- **/alerts** — every finding: requirement, gap, recommended action, product & business
  impact, key dates, **line-by-line cited regulation text** (cause → effect), source link,
  Send alert / Mark read.
- **/analytics** — portfolio impact orbs, severity donut, gaps by regulation/category,
  company risk ranking, deadline timeline, regulation-coverage table.
- **/settings** — theme, provider status, monitored regulation families.

UI: minimal aesthetic, dark + light themes, floating **dynamic-island** navigation.

---

## 9. Demo script (3 min)

1. **Sign in** as `P013` (RideVolt Mobility — has LMT batteries) — or admin view.
2. **Products** → open a product → show per-product risk orbs + coverage.
3. **Add product** → paste a description → AI labels it live (OpenRouter) → save.
4. **Scan** → pulls current regulations from the MCP, re-assesses the portfolio.
5. **Alerts** → open a Battery gap → show the **real EU Battery Regulation lines** cited
   with cause→effect + business impact + source URL.
6. **Send alert** → fires a real Twilio SMS to your verified test number (the wow moment).
7. **Analytics** → portfolio risk, fine exposure, company ranking, deadline pressure.

---

## 10. Security & data notes

- Portfolio contacts are **synthetic** (`@example.com`, placeholder phones). Real sends
  go to your own `ALERT_TO_OVERRIDE` test recipient.
- `Twilio Bash ENV SET UP.txt` contains **live credentials committed to the repo** — these
  should be rotated and kept only in the gitignored root `.env`.
- Secrets are never committed: `.env` (both) and the `.venv`/`node_modules`/`.next`/
  `.chroma`/`*.db` artifacts are gitignored.

## 11. Limitations / next

- The MCP doesn't supply structured deadlines; key dates are extracted from the cited
  text by the LLM/regex (so some alerts show no deadline).
- A full scan makes ~one LLM call per in-scope product-label pair (parallelised). To make
  the daily sync lighter, switch `check_updates()` to the MCP's `check(label)`
  recently-changed signal instead of the full library.
- Candidate follow-ups: compliance chatbot, admin review queue, per-company alert routing.
