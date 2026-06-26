# Regulatory Radar Platform

Python pipeline + web dashboard for the IBM Bobathon / EcoComply challenge.

**Organizer data** (read-only): everything under [`Dataset/`](Dataset/) — portfolio, taxonomy, example updates, and [`Dataset/SOURCES.md`](Dataset/SOURCES.md) source guide.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+ (`radar/`) |
| Ingest | stdlib HTTP/XML — EUR-Lex SOAP, Bundestag DIP, Open Legal Data, local ECHA XLSX |
| Storage | JSON files in `feed/` and `output/` |
| Dashboard | FastAPI + vanilla HTML/JS |
| Alerts | Twilio (stdlib HTTP) |

## Live sources (Core tier)

Aligned with [`Dataset/SOURCES.md`](Dataset/SOURCES.md):

| Source | Connector | Use for |
|---|---|---|
| **EUR-Lex** | SOAP `doQuery` | EU regulations (Battery, RoHS, REACH, PPWR, RED…) |
| **ECHA** | Local `ECHA/*.xlsx` | SVHC / restriction substance lists |
| **Bundestag DIP** | REST API | German legislative process |
| **Open Legal Data** | REST API ([docs](https://de.openlegaldata.io/pages/api/)) | German federal laws and norms |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in API keys and ALERT_TO_OVERRIDE (your Twilio test number)
```

### Environment variables

| Variable | Purpose |
|---|---|
| `EURLEX_USER`, `EURLEX_PASSWORD` | EUR-Lex webservice |
| `BUNDESTAG_DIP_KEY` | Bundestag DIP |
| `OPENLEGALDATA_API_KEY` | Open Legal Data (`Authorization: Token …`, optional for reads) |
| `TWILIO_*` | SMS/WhatsApp alerts |
| `ALERT_TO_OVERRIDE` | **Recommended** — routes all alerts to your test number |

## Pipeline architecture (tech lead whiteboard)

MCP is **API-key-driven**: it calls your live credentials, extracts knowledge at the API boundary, then embeds and routes.

```
YOUR API KEYS (.env)
  EURLEX_USER/PASSWORD · BUNDESTAG_DIP_KEY · OPENLEGALDATA_API_KEY (optional)
        ↓
      MCP fetch_from_apis()            radar/mcp.py  (live HTTP calls)
        ↓ knowledge extract
  Embed with same model                radar/embed.py
        ↓
  Vector DB + Router (cosine sim)      radar/vectordb.py, radar/router.py
        ↓
  Taxonomy + Text (HIL)                radar/hil.py + Dataset/taxonomy.json
        ↓
  Evaluate gaps → Present (dashboard)
```

```bash
python -m radar mcp          # full MCP: API fetch (keys) → embed → route → HIL
python -m radar run          # mcp → evaluate → alert
python -m radar ingest       # MCP fetch only (same as mcp fetch stage)
```

Sources without API keys are **skipped** (EUR-Lex falls back to known CELEX anchors only when keys are missing). Check credential status on the dashboard or via `/api/status`.

## CLI

```bash
python -m radar ingest      # pull updates → feed/cache.json
python -m radar mcp          # MCP: embed + route + cluster + HIL
python -m radar evaluate    # assess Dataset/partners.json → output/gaps.json
python -m radar evaluate --fixture   # offline demo using Dataset/regulatory_updates.json
python -m radar alert       # send Twilio alerts
python -m radar run         # ingest → mcp → evaluate → alert
python -m radar check       # self-check (fixture + seeded gaps)
python -m radar serve       # dashboard at http://localhost:8000
```

## Web dashboard

```bash
python -m radar serve
```

Open http://localhost:8000 — click **Run Scan** to execute the full pipeline.

## Demo script (3 min)

1. `python -m radar serve` — open dashboard
2. Click **Run Scan** — show ingested updates from EUR-Lex / DIP / Open Legal Data
3. Highlight **RideVolt P013-A** battery passport gap with live EUR-Lex source link
4. Show Twilio SMS on your test phone (`ALERT_TO_OVERRIDE`)
5. Explain IBM Bob role (below)

## IBM Bob prompt template

Use in Bob IDE to validate extraction rules for ambiguous documents:

```
Read Dataset/taxonomy.json and this legislative text:
<paste title + summary>

Emit JSON with: regulation_family, scope.categories, scope.substances,
scope.markets, deadline_date, source_url. Use taxonomy keys only.
```

Bob helped design keyword rules in `radar/taxonomy.py` and `radar/translate.py` — not called at runtime (pony_rule: no LLM in hot path).

## Output shape

Findings in `output/gaps.json` match [`Dataset/sample_expected_output.json`](Dataset/sample_expected_output.json).

## Offline fallback

If Wi-Fi fails on event day:

```bash
python -m radar evaluate --fixture
python -m radar alert
```

EUR-Lex also falls back to known CELEX anchors (2023/1542, 2011/65/EU) when SOAP is unavailable.
