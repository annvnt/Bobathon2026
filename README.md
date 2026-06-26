# 🛰️ Regulatory Radar — IBM Bobathon Challenge

> Companies are drowning in EU product regulations that change constantly. Build an AI agent that
> **pulls the current rules from live sources, works out which companies in the portfolio are not
> compliant today, and alerts them** — with the gap, the source, the deadline, and the fix.
> Built with **IBM Bob**; alerts fired with **Twilio**.

**GenAI Builders Day · GDGoC TUM Campus Heilbronn · partner challenge by EcoComply**

💬 **Questions any time?** Join the event WhatsApp group: <https://chat.whatsapp.com/BQf8Eul1t2gA7LCaBD1z2Q>

---

## TL;DR

You're given a **portfolio of electronics SMEs** (the companies to protect). Your agent goes out to
the **live web**, finds **current EU requirements** those companies must meet, figures out **where
they're falling short right now**, and **sends a real alert** for each gap. Pick your regulations and
depth. One real gap, from a real source, with a real alert firing, beats a big plan.

## Why this matters

[EcoComply](https://ecocomply.ai) is a Heilbronn startup that keeps electronics SMEs EU-market-ready.
One of their services is *continuous monitoring of regulatory updates* — and a lot of it is still
manual: people read legislation portals, map rules to clients by hand, and email them one by one. A
missed rule means fines, blocked shipments, or delisting. **That monitor → assess → alert loop is
exactly what you're going to automate.**

## What you'll build

```
  ┌───────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────┐
  │ FIND THE RULES│ → │  UNDERSTAND  │ → │  ASSESS GAPS │ → │  ALERT   │
  │ scrape / pull │   │  (IBM Bob)   │   │  vs. the     │   │ (Twilio) │
  │ live sources  │   │ read+extract │   │  portfolio   │   │  notify  │
  └───────────────┘   └──────────────┘   └──────────────┘   └──────────┘
   real current rules   requirement +      who is not        a real, actionable
   (see SOURCES.md)     deadline + scope   compliant today   message per company
```

---

## 🚀 Quickstart

```bash
git clone https://github.com/TUM-GDCoC/regulatory-radar-bobathon.git
cd regulatory-radar-bobathon
```

Then:
1. Get your **IBM Bob** access (30-day free): https://ibm.biz/student-bobathon
2. Grab your **Twilio** credit — promo code **`TUM-TWILIO-50`** (for the alert step).
3. Open this repo in Bob and ask it to read `README.md`, `DATASET_README.md` and `SOURCES.md`, then
   help you **design and build** the pipeline yourself (see [Working with IBM Bob](#-working-with-ibm-bob)).

## 📦 What's in the repo

| File | What it is |
|------|------------|
| `partners.json` / `partners.csv` | **Your fixed dataset:** the SME portfolio (companies + products to assess). |
| `SOURCES.md` | **Start here for rules:** a curated list of live regulatory sources to scrape/query. |
| `taxonomy.json` | Controlled vocabulary (product categories, substances, regulation families). |
| `sample_expected_output.json` | The shape of one finding (gap + source + alert) your agent should emit. |
| `regulatory_updates.json` + `feed/` | **Examples** of regulatory updates — they show the shape of a rule so you recognise one when you scrape live. Illustrative, not the task and not a dataset to match against. |
| `DATASET_README.md` | Full field-by-field data dictionary. |

**By the numbers:** 22 companies · 53 products · a curated source list · example regulatory updates.
Every company and contact is **fabricated and safe** (`@example.com`, placeholder phones) — use your
**own** Twilio test number/email for the alert demo so nothing reaches a real person.

---

## 🎯 The challenge, step by step

### Step 1 — Find the current rules (live)
Pull **current** EU product requirements from real sources. **`SOURCES.md`** lists good starting
points (EUR-Lex, ECHA, national EPR registers, EPREL, agency feeds) with tips. Scrape pages, hit
official APIs/RSS, or read published lists — your call. *(Not sure what a rule looks like? Browse the
**examples** in `regulatory_updates.json` / `feed/` first, then go find the current ones live.)*

### Step 2 — Understand each rule (use IBM Bob)
Use **IBM Bob** to read each requirement and extract the facts you need: which product categories /
substances / markets it covers, the deadline, the conditions, and whether it's the current version.

### Step 3 — Assess the portfolio for gaps
For each company/product in `partners.json`, decide whether a current requirement applies and whether
they've met it. A **gap** = an obligation that applies and isn't satisfied. Reason from the product's
attributes (category, substances, battery type, radio, markets, intended use…). A few companies carry
an explicit `compliance_status` you can check against; for the rest, you infer. Mind the look-alikes
(right category, wrong market/substance/attribute). **Cite the source** for every gap.

### Step 4 — Alert
For each gap, send **one** clear, actionable message on the company's `preferred_channel`
(email / SMS / WhatsApp): *"Your product Y must meet rule X by deadline Z — here's the fix."*
**Twilio** is the quick way to fire a real notification (promo `TUM-TWILIO-50`). Use **your own** test
number/email. At least one real alert firing in your demo is the wow moment.

**Output shape:** see `sample_expected_output.json` — a finding with the company, product, regulation,
**source URL**, the gap, deadline, recommended action, and the alert.

---

## 🪜 Difficulty tiers (pick your level)

| Tier | Who | Do this |
|------|-----|---------|
| **Beginner** | New to coding/AI | Use the **example regulations** + the `compliance_status` companies: find a known gap and fire one alert. The pipeline end-to-end on easy mode. |
| **Core** (target) | Most teams | Scrape **one or two live sources**, use Bob to extract the rule, assess several portfolio companies for gaps, fire real alerts. The full loop on live data. |
| **Stretch** | Strong teams | Cover more regulations, add a **risk dashboard**, de-duplicate across sources, prioritise by deadline, multi-language alerts, or an audit log of "rule → source → company → action". |

A correct **Core** solution on live data beats a flashy-but-wrong Stretch one.

## 🤖 Working with IBM Bob

Open the repo in Bob and ask it to read `README.md`, `DATASET_README.md` and `SOURCES.md`, then
scaffold the pipeline. Example prompts:

- **Orient:** *"Read the three docs in this repo and summarise the four steps and the data I have."*
- **Find rules:** *"Here's the HTML of an EUR-Lex / ECHA page: `<paste>`. Extract each current
  requirement as JSON: regulation, what it requires, affected categories/substances/markets, deadline,
  and the source URL."*
- **Assess a company:** *"Given this company `<paste from partners.json>` and this requirement
  `<paste>`, does it apply, and is there a gap? Reason through market, category, substance and
  attributes, and cite the deciding factor."*
- **Alert:** *"Draft a concise SMS (under 300 chars) telling company X that product Y must meet rule Z
  by the deadline, with one recommended action and the source link."*

## 🧰 Tools

- **IBM Bob — required.** Build the pipeline fast *and* use it to read rules and reason about gaps.
  IBM mentors on-site. (30-day free: https://ibm.biz/student-bobathon)
- **Twilio — recommended for alerts.** Real SMS/WhatsApp/email. Promo **`TUM-TWILIO-50`**. Any channel
  that delivers a real alert counts.
- **Anything else** — any language, scraping lib, or framework. Keep the scope to a thin end-to-end slice.

## 📤 What to submit

- **A working prototype** — a live demo where a current rule → a real gap → a real alert fires.
- **Your findings** — JSON in the shape of `sample_expected_output.json`, with source URLs.
- **A short README** — what it does, your stack, and how you used **IBM Bob** and **Twilio**.
- **A 3-min demo + 1-min pitch.**

## 🏆 How you're judged

| Criterion | What we look for | Weight |
|---|---|---|
| **Works end-to-end** | Live: a current rule → a real gap → a real alert fires | 30% |
| **Quality of insight** | The gap is real and correctly reasoned, with a **source cited** | 25% |
| **Use of IBM Bob** | How effectively Bob built and powered it | 15% |
| **Alert delivery** | A real notification actually fires; sensible channel | 10% |
| **Real-world fit** | Would EcoComply use it? Actionable, auditable, right deadline | 10% |
| **Demo & communication** | Clear story, crisp pitch | 10% |

No hidden answer key — judging is on what you build and present. Show a **real source**, a **real
gap**, and a **real alert**, and explain your reasoning.

## ❓ FAQ

- **Do we have to scrape live?** That's the goal. The `regulatory_updates.json` / `feed/` files are
  **examples** of what rules look like — use them to learn the format, but the task is to pull the
  current ones from live sources.
- **How do we know a company is non-compliant?** You reason from the product's attributes against the
  rule. A few companies have an explicit `compliance_status` to make gaps concrete; for the rest you assess.
- **Do alerts have to be real?** Aim for at least one real notification in the demo. Twilio makes it trivial.
- **Teams?** Solo or teams, formed at the event. All levels welcome — pick a tier.
- **Stuck?** Ask any mentor, or post in the WhatsApp group:
  <https://chat.whatsapp.com/BQf8Eul1t2gA7LCaBD1z2Q>

## 🗂️ Repo structure

```
regulatory-radar/
├── README.md                  ← you are here (the whole challenge)
├── SOURCES.md                 ← where to get current regulations (start here for rules)
├── DATASET_README.md          ← full data dictionary
├── partners.json / .csv       ← the SME portfolio (your fixed dataset)
├── taxonomy.json              ← controlled vocabulary
├── sample_expected_output.json← the output shape (one finding)
├── regulatory_updates.json    ← example regulatory updates (illustrative)
├── feed/                      ← the same examples, rendered as HTML
└── dataset_stats.json
```

---

*GDGoC TUM Campus Heilbronn · GenAI Builders Day · partner challenge by EcoComply · build with IBM Bob + Twilio.*
*Now go build the radar. 🛰️*
