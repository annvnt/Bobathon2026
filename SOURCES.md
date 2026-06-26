# 📡 Where to get current regulations (start here)

The challenge is to assess the portfolio against **current** EU requirements. This is a curated
starting list of real, public sources — you don't have to use all of them. Pick one or two, go deep,
and **cite the URL** for every gap you report.

> Tip: prefer **official APIs / RSS / downloadable lists** over scraping rendered HTML — they're more
> stable and polite. Respect `robots.txt` and rate limits, cache what you pull, and record the access
> date. If a site is hard or Wi-Fi fails on the day, fall back to `regulatory_updates.json` / `feed/`.

## Primary legislation

| Source | What you'll find | Access tip |
|--------|------------------|-----------|
| **EUR-Lex** — eur-lex.europa.eu | The legal texts themselves: RoHS, REACH, the Battery Regulation, PPWR, GPSR, RED, EMC, LVD, ESPR, Toy Safety, MDR, POPs. Consolidated versions show what's in force *now*. | Has a webservice / SPARQL "Cellar" API and per-document RSS. Search by CELEX number. |
| **EU Official Journal (OJ)** — eur-lex.europa.eu/oj | Newly published acts, corrigenda and amendments, by date. | Daily OJ has an RSS feed — good for "what changed recently". |

## Chemicals (RoHS / REACH / CLP / POPs)

| Source | What you'll find | Access tip |
|--------|------------------|-----------|
| **ECHA** — echa.europa.eu | The **SVHC Candidate List**, Annex XVII restrictions, CLP, the restrictions roadmap. The single best source for "which substances are restricted now". | Candidate List and restriction lists are downloadable (and searchable); ECHA publishes news + RSS. |

## Energy & ecodesign

| Source | What you'll find | Access tip |
|--------|------------------|-----------|
| **EPREL** — eprel.ec.europa.eu | The EU energy-label database for displays, lighting, power supplies, etc. | EPREL has a **public API** — query by product group. |
| **Ecodesign / ESPR** — commission.europa.eu (energy-efficient-products) | Product-group ecodesign measures and the Digital Product Passport roadmap. | Mostly HTML + linked PDFs; pair with the EUR-Lex text. |

## National producer / EPR registers (market-specific)

| Source | What you'll find | Access tip |
|--------|------------------|-----------|
| **Germany — stiftung ear** (ElektroG) — stiftung-ear.de | WEEE/EEE producer registration obligations for the German market. | Registration rules + registered-producer lookup. |
| **France — ADEME / SYDEREP** + AGEC repairability index — ademe.fr / data.ademe.fr | EPR obligations and the French repairability/durability index. | ADEME publishes open datasets. |
| (Other EU states have their own EPR registers — relevant when a company sells there.) | | |

## Product safety & recalls

| Source | What you'll find | Access tip |
|--------|------------------|-----------|
| **Safety Gate / RAPEX** — ec.europa.eu/safety-gate-alerts | Weekly alerts on dangerous non-food products (great for GPSR-style risk signals). | Has a weekly alerts feed/export. |

## Standards (RED / EMC / LVD)

| Source | What you'll find | Access tip |
|--------|------------------|-----------|
| **Harmonised standards lists** — single-market-economy.ec.europa.eu | Which harmonised standards give "presumption of conformity" per directive (incl. RED cybersecurity EN 18031). | Published as HTML tables + OJ citations. |
| **ETSI / CENELEC** — etsi.org | Radio/EMC standards detail. | Standards search. |

## Which source for which rule (quick map)

- Restricted **substances** (RoHS/REACH/POPs) → **ECHA** + the EUR-Lex text.
- **Batteries** (passport, carbon footprint, removability, labelling) → **EUR-Lex** Reg (EU) 2023/1542.
- **Packaging** (PPWR) → **EUR-Lex** Reg (EU) 2025/40.
- **Radio** (common charger, cybersecurity) → **EUR-Lex** Directive 2014/53/EU + harmonised-standards list.
- **Energy label / ecodesign** → **EPREL** + ESPR pages.
- **WEEE / national EPR** → the relevant **national register** (DE, FR, …) for the markets a company sells in.
- **General safety / recalls** → **Safety Gate** + GPSR text.

## How to cite a gap

For every finding, record: the **requirement**, the **source URL** you read it from, the **deadline**,
and which **company/product** it hits and why. That's what makes your result trustworthy to the jury —
and to EcoComply.
