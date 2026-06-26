# Regulatory Radar — Architecture & Implementation Plan

## Top-Level Overview

Build an end-to-end compliance monitoring pipeline ("Regulatory Radar") that:

1. **Ingests** live regulatory updates from three primary sources: EUR-Lex (SOAP), German Bundestag DIP (REST), and Austrian RIS v2.6 (REST).
2. **Resolves** substance and product entity synonyms against `taxonomy.json` and CAS number mappings.
3. **Evaluates** each of the 53 products across 22 partners in `partners.json` for compliance gaps using mathematical predicate logic.
4. **Dispatches** alerts via Twilio SMS/WhatsApp to each company's `preferred_channel`, with a webhook receiver for two-way reply handling.

**Scope constraint (pony_rule):** Plan only what is needed; reuse `partners.json`, `taxonomy.json`, `regulatory_updates.json`, and `sample_expected_output.json` as-is — no new data model invented without justification.

**Output shape:** Findings matching the schema in `sample_expected_output.json` per product per regulation gap.

---

## Sub-Task 1 — System Architecture and Ingestion Flow

**Status:** `[ ] pending`

### Intent
Define the physical topology of components and the data flow from raw API responses through to cached, deduplicated regulatory update records. This prevents upstream rate-limiting, avoids redundant evaluation, and gives every downstream component a single source of truth.

### Expected Outcomes
- A documented component map with clear boundaries: Ingestion Layer → Local Cache → Semantic Translation Layer → Evaluation Engine → Notification Router.
- A polling schedule for each source that respects their update cadences.
- A deduplication key schema that prevents the same regulatory update from triggering repeated evaluation cycles.

### Architecture Components

```
┌─────────────────────────────────────────────────────────────────┐
│                       INGESTION LAYER                           │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐│
│  │  EUR-Lex     │  │  Bundestag DIP   │  │  Austrian RIS v2.6 ││
│  │  SOAP Client │  │  REST Client     │  │  REST Client       ││
│  └──────┬───────┘  └────────┬─────────┘  └─────────┬──────────┘│
│         └──────────────────┬┘                       │           │
│                            ▼                         │           │
│                    ┌───────────────┐                 │           │
│                    │ Dedup + Cache │◄────────────────┘           │
│                    │  (JSON store) │                             │
│                    └───────┬───────┘                             │
└────────────────────────────┼────────────────────────────────────┘
                             ▼
┌────────────────────────────────────────────────────────────────┐
│               SEMANTIC TRANSLATION LAYER                        │
│  XML/JSON parse → Extract: categories, substances, deadlines,  │
│  thresholds, markets → Normalise to taxonomy.json vocabulary   │
└───────────────────────────┬────────────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────────────┐
│               ALGORITHMIC EVALUATION ENGINE                     │
│  Applies(P, Reg) predicate → Satisfied(P, Reg) predicate →     │
│  Gap payload with severity, deadline, recommended_action        │
└───────────────────────────┬────────────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                   NOTIFICATION ROUTER                           │
│  Format → Queue → Twilio SMS/WhatsApp dispatch                  │
│  /twilio/callback webhook receiver (inbound reply handler)      │
└────────────────────────────────────────────────────────────────┘
```

### Polling Schedule

| Source | Cadence | Rationale |
|---|---|---|
| EUR-Lex SOAP | Once daily at 06:00 UTC | OJ publishes on business days; EUR-Lex indexes within hours |
| Bundestag DIP | Every 4 hours during weekdays | Parliamentary sessions are intermittent; new Drucksachen appear multiple times per day |
| Austrian RIS v2.6 | Every 6 hours | Federal Gazette (BGBl) publishes consolidations several times per week |

### Deduplication Schema

Each ingested update is fingerprinted by a composite key:

```
dedup_key = SHA-256( source + "|" + document_reference + "|" + effective_date )
```

- `source`: "EUR-Lex" | "Bundestag" | "AustrianRIS"
- `document_reference`: CELEX number / Vorgangsnummer / Norm URL segment
- `effective_date`: ISO-8601 date string

The local cache (`feed/cache.json`) stores `{ dedup_key: update_record }`. Before evaluation, each incoming update is checked against this map. Matching keys are skipped; new keys are appended and queued for evaluation. The `regulatory_updates.json` file already demonstrates this schema — reuse it as the cache format.

### State Synchronisation

- **Incremental queries:** All three APIs support date-range filtering. Store `last_fetched` timestamps per source in `feed/state.json`.
- **Full re-sync trigger:** If the local cache is older than 7 days or explicitly cleared, a full re-sync is performed with a wider date window.
- **Correction handling:** Updates with `change_type: "correction"` or `change_type: "amendment"` invalidate the matching dedup key and re-queue the document for re-evaluation. The `regulatory_updates.json` sample includes examples of `change_type` values.

### Todo List
- [ ] Define `feed/state.json` schema: `{ "EUR-Lex": { "last_fetched": ISO }, "Bundestag": {...}, "AustrianRIS": {...} }`
- [ ] Define `feed/cache.json` schema matching `regulatory_updates.json` structure, with added `dedup_key` field
- [ ] Document component boundary: Ingestion Layer writes only to `feed/cache.json`; Evaluation Engine reads only from `feed/cache.json`
- [ ] Document polling cron expressions for each source
- [ ] Define correction/amendment invalidation rule in cache

### Relevant Context
- `regulatory_updates.json` — existing update record schema; reuse as cache record format
- `feed/` directory — designated cache storage location
- `SOURCES.md` — authoritative list of live sources and their update cadences
- `dataset_stats.json` — confirms 50 sample updates, 6 noise, 6 duplicates as test data

---

## Sub-Task 2 — API Integration Protocol and Authentication Mapping

**Status:** `[ ] pending`

### Intent
Specify how each of the three API connectors authenticates, constructs requests, parses responses, and handles errors — without writing executable code. This gives the implementation agent a precise contract for each connector module.

### Expected Outcomes
- Authentication payload format for each source.
- Request/response schemas for the target queries.
- Exception handling strategy for rate limits, parse failures, and empty results.

### EUR-Lex SOAP Connector

**Authentication:** HTTP Basic Auth over HTTPS. Credentials injected from environment variables:
- `EURLEX_USER` → `<Username>` element in SOAP header
- `EURLEX_PASSWORD` → `<Password>` element in SOAP header

**Endpoint:** `https://eur-lex.europa.eu/EurLexWebService?WSDL`  
**Operation:** `doQuery` with expert search language (ELS)

**Query template (REACH/RoHS chemical sector):**
```xml
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Header>
    <auth:credentials xmlns:auth="...">
      <auth:username>{{EURLEX_USER}}</auth:username>
      <auth:password>{{EURLEX_PASSWORD}}</auth:password>
    </auth:credentials>
  </soap:Header>
  <soap:Body>
    <search:searchRequest xmlns:search="...">
      <search:expertQuery>
        DC_TYPE = "Regulation" AND
        SUBJECT = "REACH" OR SUBJECT = "RoHS" AND
        PD >= {{last_fetched_date}}
      </search:expertQuery>
      <search:page>1</search:page>
      <search:pageSize>50</search:pageSize>
      <search:searchLanguage>en</search:searchLanguage>
    </search:searchRequest>
  </soap:Body>
</soap:Envelope>
```

**Response schema (extract):**
- `result/hits/hit/metadata/reference/CELEX` — unique legal document identifier
- `result/hits/hit/metadata/dates/APPLICABLE_DATE` — entry into force
- `result/hits/hit/metadata/title` — document title
- `result/totalHits` — pagination control

**Parse target fields:** CELEX number, document title, applicable date, subject code.

### Bundestag DIP REST Connector

**Authentication:** API key sent as query parameter `apikey` or header `Authorization: ApiKey {{BUNDESTAG_DIP_KEY}}`  
**Env var:** `BUNDESTAG_DIP_KEY`

**Endpoint for draft laws:**
```
GET https://search.dip.bundestag.de/api/v1/vorgang
  ?apikey={{BUNDESTAG_DIP_KEY}}
  &f.vorgangstyp=Gesetzgebung
  &f.wahlperiode=20
  &f.datum.start={{last_fetched_date}}
  &term=Elektrogesetz
  &format=json
  &rows=50
  &cursor={{pagination_cursor}}
```

**Response schema:**
```json
{
  "numFound": 12,
  "cursor": "AoE=...",
  "documents": [
    {
      "id": "...",
      "typ": "Vorgang",
      "vorgangstyp": "Gesetzgebung",
      "titel": "...",
      "datum": "2026-04-01",
      "drucksache": [{ "drucksachetyp": "Gesetzentwurf", "dokumentnummer": "20/XXXXX" }]
    }
  ]
}
```

**Parse target fields:** `id`, `titel`, `datum`, `drucksache[].dokumentnummer`, `drucksache[].drucksachetyp`.

**Concurrent request limit:** Max 25 simultaneous requests. Enforce with a semaphore of size 25 in the dispatcher. Retry with exponential back-off (base 2s, max 60s) on HTTP 429.

### Austrian RIS v2.6 REST Connector

**Authentication:** None (public API). Optional `X-RIS-App-Key` header if a key is obtained.

**Endpoint for consolidated federal law:**
```
GET https://data.bka.gv.at/ris/api/v2.6/Bundesrecht
  ?Applikation=BrKons
  &Suchworte=Batterie+Abfall
  &VonDatum={{last_fetched_date}}
  &Kundmachungsorgan=BGBl
  &ImRisSeit=Undefined
  &ResultPageSize=50
  &Seitennummer=1
  &format=json
```

**Response schema:**
```json
{
  "OgdSearchResult": {
    "hits": {
      "Hits": 8,
      "Hit": [
        {
          "Dokumentnummer": "NOR40258123",
          "Kurztitel": "Batteriegesetz-Novelle 2025",
          "Kundmachungsdatum": "2025-12-01",
          "ArtikelParagraph": "§ 4",
          "DokumentUrl": "https://www.ris.bka.gv.at/..."
        }
      ]
    }
  }
}
```

**Parse target fields:** `Dokumentnummer`, `Kurztitel`, `Kundmachungsdatum`, `DokumentUrl`.

**Pagination:** Increment `Seitennummer` until `Hit` array is shorter than `ResultPageSize`.

### Exception Handling Strategy

| Error Condition | Detection | Response |
|---|---|---|
| EUR-Lex SOAP envelope parse failure | XML parser exception on response body | Log raw response, skip update, emit `parse_error` event |
| EUR-Lex HTTP 401 | SOAP Fault / HTTP status | Halt ingestion, alert operator, do not retry without credential refresh |
| Bundestag HTTP 429 (rate limit) | HTTP status 429 | Back off exponentially; semaphore prevents exceeding 25 concurrent |
| Bundestag empty result set | `numFound == 0` | Log as `no_new_updates`, update `last_fetched`, continue |
| RIS v2.6 pagination end | `Hit` array length < `ResultPageSize` | Stop pagination, mark source as fully fetched |
| Network timeout (any source) | Connection/read timeout after 30s | Retry up to 3 times, then log and skip to next scheduled run |
| Dedup key collision (duplicate update) | Key present in `feed/cache.json` | Discard silently; no re-evaluation triggered |

### Todo List
- [ ] Document SOAP envelope template for EUR-Lex `doQuery` with ELS syntax for RoHS/REACH/Battery scopes
- [ ] Document DIP REST query string parameters and cursor-based pagination logic
- [ ] Document RIS v2.6 query parameters and page-number pagination logic
- [ ] Define environment variable names: `EURLEX_USER`, `EURLEX_PASSWORD`, `BUNDESTAG_DIP_KEY`
- [ ] Define retry/back-off rules and timeout values per connector
- [ ] Define `parse_error` event structure for error logging

### Relevant Context
- `SOURCES.md` — official API endpoint references
- `feed/` — output directory for cached raw responses
- `regulatory_updates.json` — target record schema after parsing

---

## Sub-Task 3 — Taxonomy Matching and Substance Entity Resolution

**Status:** `[ ] pending`

### Intent
Map raw legislative text (variable substance names, CAS numbers, product terms) to the canonical identifiers in `taxonomy.json`. This prevents false negatives (missed matches) and false positives (wrong substance matched to wrong product).

### Expected Outcomes
- A synonym resolution strategy that maps "lead", "Pb", "Blei", "7439-92-1" all to the canonical key `lead` in `taxonomy.json`.
- A parsing schema to extract structured facts from unstructured regulatory text.
- A battery categorisation logic aligned with EU Battery Regulation 2023/1542.

### Substance Synonym Resolution

**Canonical authority:** `taxonomy.json` → `substances` object. Keys are canonical identifiers (e.g., `lead`, `DEHP`, `MCCP`).

**Resolution hierarchy (first match wins):**
1. **CAS number match:** If the text contains a CAS number (pattern `\d{1,7}-\d{2}-\d`), look up a static CAS-to-canonical mapping table:
   - `7439-92-1` → `lead`
   - `7440-43-9` → `cadmium`
   - `7439-97-6` → `mercury`
   - `117-81-7` → `DEHP`
   - `84-74-2` → `DBP`
   - `85-68-7` → `BBP`
   - `80-05-7` → `BPA`
   - _(full table to be completed at implementation)_
2. **IUPAC / common name normalisation:** Lower-case the text, strip punctuation, check against a synonym list keyed to canonical identifiers (e.g., `["lead", "pb", "blei", "plomb", "plomo"]` → `lead`).
3. **Family match:** If an individual substance is not matched but belongs to a regulated family (e.g., "phthalates"), flag for manual review rather than silently failing.

**Disambiguation rule for "lead":** The synonym resolver must check context. If the text contains "lead solder", "lead alloy", "lead content", or a CAS number beginning with `7439-92`, resolve to the metal (`lead`). If the text contains "lead acid battery", apply to `lead` with product category context `battery_pack`. This prevents confusing the verb "lead" or "lead time" with the metal.

### Legislative Text Parsing Schema

For each ingested regulatory document, extract the following structural facts:

| Field | Extraction Method | Example |
|---|---|---|
| `affected_categories` | Pattern match against `taxonomy.json` `product_categories` keys and their descriptions | "LED luminaires" → `led_lighting` |
| `substances` | CAS + synonym resolution (above) | "lead (Pb)" → `lead` |
| `concentration_threshold` | Regex for `\d+(\.\d+)?\s*%\s*(w/w)?` near substance name | "0.1% w/w" → `{ value: 0.1, unit: "% w/w" }` |
| `enforcement_date` | ISO date regex or "DD Month YYYY" → ISO-8601 | "18 February 2027" → `2027-02-18` |
| `markets` | Country/region name lookup against ISO codes + "EU" expansion | "European Union" → `["EU"]` |
| `exemption_ids` | Pattern for "Annex III exemption X(a)" or "Annex IV" | "exemption 6(c)" → `"6(c)"` |
| `exemption_expiry` | Date adjacent to exemption reference | "June 30, 2027" → `2027-06-30` |

### Battery Categorisation Logic (EU 2023/1542)

Given a `battery_info` object from `partners.json` (fields: `type`, `capacity_wh`, `portable`):

```
IF capacity_wh <= 25000 AND intended_use IN ["mobility", "e-scooter", "e-bike", "lmt"]
    THEN category = "LMT"
ELSE IF capacity_wh > 5000 AND NOT LMT AND NOT EV
    THEN category = "Industrial"
ELSE IF portable == true AND capacity_wh < 5000 (or not heavy industry)
    THEN category = "Portable"
ELSE IF intended_use == "EV" OR capacity_wh > 25000
    THEN category = "EV"
```

**Concrete examples from `partners.json`:**
- `P003-A` PowerBank 20k (li-ion, 74 Wh, portable) → `Portable`
- `P003-B` IndusCell 2.5kWh (li-ion, 2500 Wh, industrial) → `Industrial`
- `P013-A` e-Scooter Battery Pack 280Wh → `LMT`

**Battery passport applicability by category:**
- `LMT` → Art. 77, deadline 2027-02-18
- `Industrial` > 2 kWh → Art. 77, deadline 2027-08-18
- `Portable` → Art. 77, deadline 2027-02-18 (consumer-facing)
- `EV` → Art. 77, deadline 2026-08-18

### Todo List
- [ ] Build CAS-to-canonical lookup table covering all substances in `taxonomy.json`
- [ ] Build synonym list per canonical substance key (EN + DE + FR common names minimum)
- [ ] Define context disambiguation rules for ambiguous terms ("lead", "cadmium" as a colour, etc.)
- [ ] Define the legislative text parse schema with regex patterns per field
- [ ] Define battery category decision tree with capacity and use-case thresholds
- [ ] Define battery passport deadline mapping per category

### Relevant Context
- `taxonomy.json` — canonical substance and category identifiers
- `partners.json` — `battery_info` object structure: `{ type, capacity_wh, portable }`
- `regulatory_updates.json` — `scope.substances` and `scope.categories` use taxonomy keys
- `sample_expected_output.json` — confirms output fields `regulation`, `gap`, `deadline`, `recommended_action`

---

## Sub-Task 4 — Exemption Suspension and Algorithmic Gap Analysis

**Status:** `[ ] pending`

### Intent
Define the mathematical predicates `Applies(P, Reg)` and `Satisfied(P, Reg)` with full support for exemption lifecycle states, multi-jurisdictional transpositions, and physical design derogations. The output is a gap payload matching `sample_expected_output.json`.

### Expected Outcomes
- Formal definitions of `Applies` and `Satisfied` predicates.
- Exemption Suspension State logic for RoHS 6(c) / 7(c)-I.
- Physical design derogation handling for Battery Regulation Art. 11 and WEEE.
- Step-by-step evaluation flowchart from product schema to gap payload.

### Formal Definitions

**Product tuple:**
```
P = ⟨ C, M, S, B, R, U ⟩
  C = set of product_category keys
  M = set of market ISO codes (EU expanded to all 27)
  S = { substance_key: { concentration: float, exemptions: [exemption_id] } }
  B = { type, capacity_wh, portable, removable, sealed }
  R = { has_radio: bool, connector: string }
  U = intended_use string
```

**Regulation tuple:**
```
Reg = ⟨ Φ_cat, Φ_mkt, Φ_sub, Φ_bat, Φ_use, Θ_sub, Deadline, ExemptionAllowed, Derogations ⟩
  Φ_cat = required product categories (∅ = all)
  Φ_mkt = required markets
  Φ_sub = regulated substance keys
  Θ_sub = concentration thresholds per substance
  ExemptionAllowed = { exemption_id: { expiry, suspended_until } }
  Derogations = [ { condition, scope } ]
```

**Applies(P, Reg):**
```
Applies(P, Reg) = TRUE  iff
  (Φ_cat = ∅  OR  C ∩ Φ_cat ≠ ∅)  AND
  M ∩ Φ_mkt ≠ ∅  AND
  (Φ_sub = ∅  OR  keys(S) ∩ Φ_sub ≠ ∅  OR  Φ_bat applies to B  OR  other scope predicates)
```

**Satisfied(P, Reg):**
```
Satisfied(P, Reg) = TRUE  iff  Applies(P, Reg)  AND  for all s in (keys(S) ∩ Φ_sub):
  S[s].concentration <= Θ_sub[s]
  OR  ExemptionValid(s, S[s].exemptions, Reg, evaluation_date)
```

### Exemption Validity and Suspension State

```
ExemptionValid(substance, claimed_exemptions, Reg, T) =
  ∃ e ∈ claimed_exemptions such that:
    e ∈ Reg.ExemptionAllowed  AND
    (
      Reg.ExemptionAllowed[e].expiry > T                  -- not yet expired
      OR
      SuspensionActive(e, Reg, T)                         -- suspended
    )

SuspensionActive(e, Reg, T) =
  Reg.ExemptionAllowed[e].renewal_submitted = TRUE  AND
  Reg.ExemptionAllowed[e].renewal_submitted_date <= Reg.ExemptionAllowed[e].nominal_expiry
  -- A timely renewal submission legally extends the exemption until a Commission decision
```

**RoHS 6(c) / 7(c)-I example:**
- Nominal expiry: 2027-06-30
- Renewal submitted: December 2025 (before expiry → timely)
- At evaluation time T = 2026-01-01: `SuspensionActive = TRUE`
- Gap payload severity: `"medium"` with note `"At Risk — exemption renewal pending; legally compliant while suspension active"`

**Gap classification table:**

| Condition | Gap Status | Severity |
|---|---|---|
| `!Applies` | No gap | none |
| `Applies AND Satisfied` | Compliant | none |
| `Applies AND !Satisfied AND ExemptionValid (active suspension)` | At Risk | medium |
| `Applies AND !Satisfied AND !ExemptionValid` | Non-compliant | high |
| `Applies AND !Satisfied AND Deadline > T + 180 days` | Pre-deadline gap | low |
| `Applies AND !Satisfied AND Deadline <= T` | Overdue | critical |

### Physical Design Derogations (Battery Reg Art. 11 / WEEE)

Battery Regulation Art. 11 requires portable batteries to be removable and replaceable by end users. A derogation applies if:

```
DerogationApplies(P, Reg) =
  Reg.Derogations ∋ d  such that
    d.condition(P) = TRUE

-- Condition for Commission Notice C/2025/214:
d.condition(P) = (
  P.U ∈ {"medical", "industrial"}  AND
  P.B.sealed = TRUE  AND
  d.scope covers P.C
)
```

If `DerogationApplies = TRUE`, the physical design gap is suppressed. The gap payload includes a `"derogation_applied"` note referencing the Commission Notice URL.

### Evaluation Engine Step-by-Step

```
For each update U in feed/cache.json:
  1. Parse U → Reg tuple (using Sub-Task 3 extraction)
  2. For each partner P in partners.json:
     For each product prod in P.products:
       a. Build P tuple from prod attributes
       b. Evaluate Applies(prod, Reg) → skip if FALSE
       c. Evaluate Satisfied(prod, Reg):
          i.  Check substance concentrations vs thresholds
          ii. Check ExemptionValid for each claimed exemption
          iii.Check DerogationApplies for physical design requirements
       d. If NOT Satisfied:
          - Compute gap_status and severity (table above)
          - Build gap payload (sample_expected_output.json schema)
          - Append to output gaps list
3. Write gaps list to output file
4. Pass gaps to Notification Router (Sub-Task 5)
```

### Todo List
- [ ] Formalise `Applies` predicate covering all scope axes: category, market, substance, battery, radio, use
- [ ] Formalise `Satisfied` predicate with exemption suspension logic
- [ ] Define `ExemptionValid` and `SuspensionActive` functions with input/output contracts
- [ ] Define gap severity classification table with all 6 states
- [ ] Define `DerogationApplies` condition for Battery Reg Art. 11 and Commission Notice C/2025/214
- [ ] Define gap payload schema consistent with `sample_expected_output.json`
- [ ] Define evaluation loop order: updates → partners → products

### Relevant Context
- `partners.json` — `substances`, `battery_info`, `intended_use`, `markets`, `compliance_streams`
- `taxonomy.json` — canonical keys for substances, categories, regulation families
- `regulatory_updates.json` — `scope` object structure: `categories`, `substances`, `markets`, `conditions`
- `sample_expected_output.json` — gap payload schema to match exactly

---

## Sub-Task 5 — Notification Routing and Webhook Orchestration

**Status:** `[ ] pending`

### Intent
Route confirmed gap payloads to the correct alert channel per partner, format messages within carrier limits, handle delivery failures, and process inbound Twilio webhook replies for opt-out and escalation.

### Expected Outcomes
- Message formatting rules for SMS (GSM-7, 160 chars) and WhatsApp (1600 chars, template-based).
- An asynchronous dispatch queue design that decouples evaluation from delivery.
- A `/twilio/callback` webhook receiver specification with Twilio signature verification.
- A reply state-machine covering opt-out, info request, and escalation paths.

### Message Format Templates

**SMS (≤ 160 GSM-7 characters):**
```
{company}: {product} needs {regulation_short} action by {deadline}.
{recommended_action_short}. Source: {source_url_short}
```
Example (from `sample_expected_output.json`):
```
RideVolt: e-Scooter Battery needs EU battery passport by 18 Feb 2027 (2023/1542). Set up QR/data carrier. eur-lex.europa.eu
```
Character budget allocation: company (20) + product (30) + requirement (50) + deadline (15) + action (30) + URL (20) = ~165 → use URL shortener or abbreviated regulation reference if over 160.

**WhatsApp (≤ 1600 chars):**
Full message with: company name, product name, full regulation title, requirement description, gap description, deadline (ISO + human-readable), full recommended action, source URL, reply instructions ("Reply STOP to opt out. Reply INFO for details.").

**WhatsApp destination format:** `whatsapp:+{e164_number}` (prepend `whatsapp:` to standard E.164 number from `contact.phone`).

### Dispatch Queue Design

```
Gap Payloads
     │
     ▼
┌──────────────────────────────────┐
│  In-Memory FIFO Queue            │
│  (list of gap payloads)          │
│  Max concurrency: 5 dispatchers  │
└──────────┬───────────────────────┘
           │  dequeue one at a time per worker
           ▼
┌──────────────────────────────────┐
│  Channel Router                  │
│  preferred_channel == "sms"      │──► Twilio SMS API (POST /Messages)
│  preferred_channel == "whatsapp" │──► Twilio WhatsApp API (POST /Messages)
│  preferred_channel == "email"    │──► (future: SMTP stub for hackathon)
└──────────────────────────────────┘
           │
           ▼
    Delivery receipt logged
    Retry on 429/5xx (max 3, backoff 5s)
```

**Rationale for queue:** Prevents evaluation engine from blocking on Twilio API latency during batch processing of 53 products × N gaps.

### Webhook Receiver — `/twilio/callback`

**Trigger:** Twilio HTTP POST on inbound reply or delivery status update.

**Security validation (Twilio signature verification):**
1. Retrieve `X-Twilio-Signature` header from the incoming request.
2. Sort all POST body parameters alphabetically by key.
3. Concatenate the full request URL + sorted key-value pairs into a validation string.
4. Compute HMAC-SHA1 of the validation string using `TWILIO_AUTH_TOKEN` as the key.
5. Base64-encode the HMAC digest.
6. Compare to `X-Twilio-Signature`. If they differ, return HTTP 403 and log the attempt.

**Webhook payload fields used:**
- `From` — sender's phone number (E.164)
- `Body` — message text
- `MessageStatus` — delivery status (for outbound status callbacks)
- `To` — the Twilio number that received the message

### Reply State Machine

```
Inbound message received
         │
         ▼
Parse Body (upper-case, strip whitespace)
         │
    ┌────┴────────────────────┐
    │                         │
Body = "STOP"            Body = "INFO"        Body = other
    │                         │                     │
    ▼                         ▼                     ▼
Add sender to          Send detail       Log as "unknown reply"
opt-out list;          email/message     Forward to support
stop all future        with full gap     queue (manual review)
alerts for this        payload JSON
number
```

**Opt-out persistence:** Store opted-out numbers in `feed/optouts.json` as a list of E.164 strings. Check this list before every dispatch.

**Escalation:** Any reply not matching STOP or INFO is forwarded as a new task to `support_email` (configurable env var `SUPPORT_EMAIL`), including the original gap context retrieved by matching `From` to `partner_id` in `partners.json`.

### Todo List
- [ ] Define SMS template with character budget breakdown (160 GSM-7 limit)
- [ ] Define WhatsApp template with full field list and `whatsapp:` prefix rule
- [ ] Define dispatch queue structure and max concurrency limit
- [ ] Define channel routing logic based on `preferred_channel` values in `partners.json`
- [ ] Define `/twilio/callback` request validation steps using `TWILIO_AUTH_TOKEN`
- [ ] Define reply state-machine transitions: STOP, INFO, escalation
- [ ] Define `feed/optouts.json` schema and pre-dispatch check

### Relevant Context
- `partners.json` — `contact.preferred_channel`, `contact.phone`, `contact.email` per company
- `sample_expected_output.json` — `alert` object: `channel`, `to`, `message` fields
- Environment variables: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`

---

## Cross-Cutting Concerns

### Environment Variables Summary

| Variable | Used By | Description |
|---|---|---|
| `EURLEX_USER` | Sub-Task 2 | EUR-Lex SOAP username |
| `EURLEX_PASSWORD` | Sub-Task 2 | EUR-Lex SOAP password |
| `BUNDESTAG_DIP_KEY` | Sub-Task 2 | Bundestag DIP API key |
| `TWILIO_ACCOUNT_SID` | Sub-Task 5 | Twilio account identifier |
| `TWILIO_AUTH_TOKEN` | Sub-Task 5 | Twilio auth token (also for webhook sig validation) |
| `TWILIO_FROM_NUMBER` | Sub-Task 5 | Twilio sending number (E.164) |
| `SUPPORT_EMAIL` | Sub-Task 5 | Escalation target for unknown replies |

### File I/O Map

| File | Written By | Read By |
|---|---|---|
| `feed/state.json` | Ingestion Layer | Ingestion Layer (next run) |
| `feed/cache.json` | Ingestion Layer | Evaluation Engine |
| `feed/optouts.json` | Webhook Receiver | Notification Router |
| `partners.json` | (pre-existing) | Evaluation Engine, Notification Router |
| `taxonomy.json` | (pre-existing) | Semantic Translation Layer |
| `regulatory_updates.json` | (pre-existing sample) | Evaluation Engine (as test fixture) |
| `sample_expected_output.json` | (pre-existing) | Validation / test fixture |

### Pony Rule Compliance Notes

- `ponytail:` No new data model invented — `feed/cache.json` reuses the schema of the existing `regulatory_updates.json`.
- `ponytail:` No database introduced — file-based JSON store is sufficient for 50–100 updates per run; upgrade path is SQLite if volume exceeds memory comfort.
- `ponytail:` No message broker introduced — in-memory queue is sufficient for 53 products × single-digit gaps per run; upgrade path is Redis if horizontal scaling needed.
- `ponytail:` Dedup key uses SHA-256 from stdlib — no external library needed.
- `ponytail:` Twilio signature validation uses HMAC-SHA1 from stdlib — no Twilio SDK required (though the SDK would also work and is already a common dependency).
