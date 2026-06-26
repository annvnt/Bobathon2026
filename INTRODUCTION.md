# Regulatory Radar — Platform Introduction

**IBM Bobathon · EcoComply partner challenge · GDGoC TUM Campus Heilbronn**

---

## What it is

**Regulatory Radar** is an end-to-end compliance monitoring platform for electronics SMEs. It automates the loop EcoComply runs manually today:

1. **Find** current EU product regulations from live official sources  
2. **Understand** each rule — scope, substances, markets, deadlines  
3. **Assess** which companies in the portfolio are not compliant  
4. **Alert** each affected client with the gap, the source, the deadline, and a recommended fix  

The platform is built with **IBM Bob** (design and extraction rules) and delivers real notifications via **Twilio** (SMS / WhatsApp / email).

---

## The problem we solve

EU product rules change constantly — Battery Regulation, RoHS, REACH, RED, GPSR, WEEE, and more. A missed update can mean fines, blocked shipments, or delisting.

EcoComply keeps electronics SMEs market-ready. A large part of that work is still manual: analysts read legislation portals, map rules to clients by hand, and notify them one by one. **Regulatory Radar automates that monitor → assess → alert loop** so compliance teams can focus on judgment, not copy-paste.

---

## How the platform works

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────────┐
│  LIVE SOURCES   │ ──► │  UNDERSTAND &    │ ──► │  GAP ASSESSMENT │ ──► │   ALERTS     │
│  EUR-Lex, DIP,  │     │  ROUTE           │     │  vs. portfolio  │     │   Twilio     │
│  Open Legal,    │     │  (taxonomy +     │     │  (22 companies, │     │   SMS / WA / │
│  ECHA           │     │   vector match)  │     │   53 products)  │     │   email      │
└─────────────────┘     └──────────────────┘     └─────────────────┘     └──────────────┘
```

### Step 1 — Ingest live regulations

The platform pulls **current** requirements from official sources aligned with the organizer's source guide (`Dataset/SOURCES.md`):

| Source | What it covers |
|--------|----------------|
| **EUR-Lex** | EU regulations (Battery, RoHS, REACH, PPWR, RED, …) |
| **Bundestag DIP** | German legislative process and drafts |
| **Open Legal Data** | German federal laws and norms |
| **ECHA** | SVHC and restriction substance lists (local XLSX) |

Each fetched document is normalized into a structured update: title, summary, regulation family, scope (categories, substances, markets), deadline, and **source URL**.

### Step 2 — Route and classify

Incoming updates pass through an **MCP-style pipeline** (Model Context Protocol pattern: fetch at the API boundary, extract knowledge, then process):

- **Embed** each update with the same embedding model  
- **Route** it against a vector database of known regulation families (cosine similarity)  
- **Map** to the organizer's controlled vocabulary (`Dataset/taxonomy.json`)  
- **Queue for human review** when router confidence is below 60% (Human-in-the-Loop / HIL)

This keeps the runtime path fast and deterministic — no LLM calls in the hot path during a live scan.

### Step 3 — Assess compliance gaps

For every product in the organizer portfolio (`Dataset/partners.json`), the engine asks:

- **Does this regulation apply?** (market overlap, product category, substances, battery/radio attributes, compliance streams)  
- **Is the obligation already satisfied?** (explicit `compliance_status` where provided, plus rule-specific predicates)  

A **gap** is recorded when a current obligation applies and is not met. Each finding includes:

- Company and product  
- Regulation name and requirement text  
- **Cited source URL**  
- Gap description, deadline, severity  
- Recommended action  
- Draft alert message for the client's preferred channel  

Output shape matches `Dataset/sample_expected_output.json`.

### Step 4 — Send alerts

For each gap, the platform fires a **real notification** through Twilio on the company's `preferred_channel` (SMS, WhatsApp, or email). For demos, all alerts can be routed to a single test number via `ALERT_TO_OVERRIDE` so no fabricated portfolio contact receives a message.

---

## IBM Bob's role

IBM Bob was used **during development** to:

- Design keyword and taxonomy mapping rules  
- Validate extraction logic for ambiguous legislative text  
- Scaffold the pipeline and dashboard  

Bob is **not called at runtime** during a live scan. The production path uses deterministic rules, embeddings, and predicates — fast, auditable, and suitable for a demo under event Wi-Fi.

Example Bob prompt used to validate extraction:

```
Read Dataset/taxonomy.json and this legislative text:
<paste title + summary>

Emit JSON with: regulation_family, scope.categories, scope.substances,
scope.markets, deadline_date, source_url. Use taxonomy keys only.
```

---

## Web dashboard

A single command starts the dashboard:

```bash
python -m radar serve
```

Open **http://localhost:8000** to see:

| Section | What it shows |
|---------|----------------|
| **Run Scan** | One-click full pipeline: ingest → route → evaluate → alert |
| **Stats** | Total gaps, critical/high count, cached updates, vector DB size, HIL queue |
| **MCP routing** | Live API credential status and how each update was routed |
| **HIL review** | Low-confidence matches awaiting analyst approval |
| **Compliance gaps** | Sortable table — company, product, regulation, severity, deadline, source link |
| **Recent updates** | Latest ingested rules from live sources |

The UI follows IBM Carbon Design System styling (Plex Sans, IBM Blue accent, flat-square layout).

---

## Organizer dataset (read-only)

All portfolio and taxonomy data comes from the organizer bundle under `Dataset/`:

| Asset | Contents |
|-------|----------|
| `partners.json` | 22 fabricated SMEs, 53 products, contact channels |
| `taxonomy.json` | Controlled vocabulary for categories, substances, regulation families |
| `SOURCES.md` | Curated list of live regulatory sources |
| `sample_expected_output.json` | Canonical shape of one gap finding |

Every company and contact is **fabricated and safe** (`@example.com`, placeholder phones). Demo alerts should use your own Twilio test number.

---

## What to look for in the demo (~3 minutes)

1. **Start the dashboard** — `python -m radar serve`  
2. **Run Scan** — show live ingestion from EUR-Lex / DIP / Open Legal Data  
3. **Highlight a real gap** — e.g. RideVolt **P013-A** battery passport with a live EUR-Lex source link  
4. **Show a Twilio alert** on the test phone (`ALERT_TO_OVERRIDE`)  
5. **Explain auditability** — every gap cites a source URL; low-confidence routes go to HIL  

### Offline fallback

If Wi-Fi fails on event day:

```bash
python -m radar evaluate --fixture
python -m radar alert
```

EUR-Lex also falls back to known CELEX anchors when SOAP is unavailable.

---

## Challenge alignment

| Judging criterion | How we address it |
|-------------------|-------------------|
| **Works end-to-end** | Live sources → real gaps → real Twilio alerts |
| **Quality of insight** | Rule-specific predicates, cited sources, deadline-aware severity |
| **Use of IBM Bob** | Bob designed extraction rules and pipeline; runtime stays deterministic |
| **Alert delivery** | Twilio SMS/WhatsApp/email on preferred channel |
| **Real-world fit** | HIL queue, opt-outs, audit trail, EcoComply-style monitor loop |
| **Demo & communication** | Carbon-styled dashboard, one-click scan, sortable gap table |

---

## Stack at a glance

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+ (`radar/`) |
| Ingest | EUR-Lex SOAP, Bundestag DIP REST, Open Legal Data REST, ECHA XLSX |
| Storage | JSON files in `feed/` and `output/` |
| Dashboard | FastAPI + vanilla HTML/JS |
| Alerts | Twilio (stdlib HTTP) |

---

## Summary

Regulatory Radar is a working prototype of **continuous EU compliance monitoring** for electronics SMEs. It pulls rules from live official APIs, maps them to a real portfolio dataset, surfaces auditable gaps with source citations and deadlines, and fires actionable alerts — the same loop EcoComply runs by hand, automated end to end.

**Built with IBM Bob + Twilio · Partner challenge by EcoComply · GDGoC TUM Campus Heilbronn**
