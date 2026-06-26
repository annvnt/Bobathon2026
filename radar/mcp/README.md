# MCP Transplant Guide

Use this document when extracting **only the MCP package** into another project.  
Dashboard gaps/alerts, free-text chat, and the evaluate pipeline are **out of scope** — do not transplant them.

---

## 1. Package layout

```
radar/mcp/
├── README.md           ← this guide
├── contract.py         ← public Python API (import from here)
├── routes.py           ← FastAPI router (/api/mcp/*)
├── regulation_ops.py   ← fetch_regulation(), check_label()
├── label_regs.py       ← CELEX/GADI lookup, regulation library
├── catalog.py          ← bulk fetch for all partners.csv streams
├── present.py          ← product_id → regulation cards (optional)
├── run.py              ← [optional] API ingest → embed → route pipeline
├── embed.py            ← [optional]
├── router.py           ← [optional]
└── vectordb.py         ← [optional]
```

### Layers

| Layer | Files | Required | Description |
|--------|------|----------|-------------|
| **Contract** | `contract.py`, `regulation_ops.py`, `label_regs.py` | **Yes** | `fetchregulation()` + `check(label)` |
| **Catalog** | `catalog.py` | Recommended | Preload all 15 `compliance_streams` from `partners.csv` |
| **Present** | `present.py` | Optional | Portfolio product → regulation list (UI helper) |
| **Pipeline** | `run.py`, `embed.py`, `router.py`, `vectordb.py` | Optional | API-key ingest / vector routing |

Copy list: [`TRANSPLANT.txt`](TRANSPLANT.txt)

---

## 2. Peer modules (copy with MCP)

`radar/mcp/` does not run in isolation. Copy the modules below under the same import path (`radar.*`), or adjust imports in `contract.py` for your host project.

### Required (regulation contract)

```
radar/config.py                    # FEED, REGULATION_LIBRARY_FILE, GADI_BASE, ensure_dirs
radar/compliance/jurisdictions.py  # EU/DE jurisdiction expansion
radar/compliance/taxonomy.py       # check(label) keyword / family matching
radar/ingest/gadi.py               # German federal laws JSON (gadi.netlify.app)
radar/ingest/regcache.py           # EUR-Lex / GADI text cache
radar/ingest/translate.py          # EUR-Lex metadata
radar/ingest/oj_rss.py             # check(label) OJ RSS
radar/ingest/fetch.py              # load_cache() for check_label
```

### Optional (present / catalog)

```
Dataset/partners.json              # present.py, catalog.py
Dataset/partners.csv               # catalog.py (compliance_streams column)
```

### Optional (ingest pipeline)

```
radar/ingest/sources.py, echa.py
radar/review/hil.py
radar/config.py  → VECTORDB_FILE, ROUTER_INDEX_FILE, HIL_QUEUE_FILE
```

### Do not copy (other team areas)

```
radar/api/chat.py                  # free-text EUR-Lex search
radar/compliance/evaluate.py       # gap assessment
radar/compliance/findings.py
radar/alerts/*
radar/orchestration/pipeline.py
radar/api/static/*                 # dashboard UI (present tab is optional)
```

---

## 3. Data / feed directory

| Path | Purpose |
|------|---------|
| `feed/label_regulations.json` | Regulation index |
| `feed/label_regulations/*.json` | Full text per regulation |
| `feed/regulations/*` | regcache (EUR-Lex / GADI bodies) |
| `feed/cache.json` | Optional cache for `check(label)` matching |

Initial preload:

```bash
python -m radar fetch-catalog
```

---

## 4. FastAPI integration

```python
from fastapi import FastAPI
from radar.mcp.routes import router as mcp_router

app = FastAPI()
app.include_router(mcp_router)   # mounts /api/mcp/*
```

If the host app needs cached full text in the UI, keep something like `GET /api/regulations/{cache_key}` wired to `radar.ingest.regcache`.

---

## 5. Python contract (tech-lead interface)

```python
from radar.mcp.contract import fetch_regulation, check_label, fetch_by_code

# 1) labels × countries → fetch EU (CELEX) + DE (GADI) and save
fetch_regulation(["Battery", "REACH"], ["DE", "EU"], product_id="P013-A")

# 2) recent OJ / cache hits for a compliance label
check_label("Battery", since="2026-01-01")

# 3) direct lookup by regulation code
fetch_by_code("32023R1542")   # EU CELEX
fetch_by_code("BattDG")       # DE GADI abbreviation
```

Aliases: `fetchregulation = fetch_regulation`, `check = check_label`

### Code ↔ compliance stream mapping

`STREAM_REG_CODES` in `label_regs.py`, exposed at `GET /api/mcp/codes`:

```json
{
  "Battery": { "eu_celex": "32023R1542", "de_code": "BattDG", "eu_title": "..." },
  "EMC":     { "eu_celex": "32014L0030", "de_code": "EMVG",  "eu_title": "..." }
}
```

Stored records use the **raw code** as `reference` (`32023R1542`, `BattDG`, not synthetic keys).

---

## 6. HTTP API summary

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/mcp/fetch-regulation` | **fetchregulation()** |
| `GET` | `/api/mcp/check/{label}` | **check(label)** |
| `GET` | `/api/mcp/code/{code}` | Single fetch by CELEX or GADI code |
| `GET` | `/api/mcp/codes` | Stream → code mapping table |
| `GET` | `/api/mcp/label-regulations` | Saved library (`?code=`, `?category=`, `?country=`) |
| `POST` | `/api/mcp/fetch-catalog` | Bulk fetch all portfolio streams |
| `GET` | `/api/mcp/catalog` | Per-stream coverage status |
| `POST` | `/api/mcp/present` | product_id → regulation cards (optional) |

### Example curls

```bash
curl -X POST http://localhost:8000/api/mcp/fetch-regulation \
  -H "Content-Type: application/json" \
  -d '{"labels":["Battery","REACH"],"countries":["DE","EU"],"product_id":"P013-A"}'

curl "http://localhost:8000/api/mcp/check/Battery?since=2026-01-01"
```

---

## 7. Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `EURLEX_USER`, `EURLEX_PASSWORD` | Recommended | EUR-Lex full-text fetch (on failure, CELEX link fallback is still returned) |
| — | — | GADI and OJ RSS are public; no keys needed |

---

## 8. Minimal transplant checklist

- [ ] Copy `radar/mcp/` + required peer modules from `TRANSPLANT.txt`
- [ ] Ensure writable `feed/label_regulations/`
- [ ] Register `app.include_router(mcp_router)`
- [ ] Smoke test: `python -c "from radar.mcp.contract import fetch_regulation; ..."`
- [ ] `POST /api/mcp/fetch-regulation` returns regulations
- [ ] `GET /api/mcp/check/Battery` returns OJ/cache hits

---

## 9. Renaming the package

If the host project is not named `radar`:

1. Copy `radar/mcp/` → `{your_pkg}/mcp/`
2. Copy peer modules under the same prefix, or search-replace imports
3. Point `config.py` paths (`FEED`, `REGULATION_LIBRARY_FILE`) at your layout

**Recommendation:** keep the `radar` package name during the first transplant; rename after it is stable.
