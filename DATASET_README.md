# Regulatory Radar - Data Dictionary

The field-by-field guide to the dataset. For the **challenge itself** (what to build, how to start,
how you're judged) read **README.md**. For **where to get current regulations**, read **SOURCES.md**.

**The company portfolio is your fixed dataset.** Your job is to pull *current* EU requirements from
live sources, find where these companies are not compliant today, and alert them. The portfolio
companies and contacts are **fabricated and safe** - `@example.com` emails and placeholder phone
numbers, so test alerts never reach a real person. Use your **own** Twilio test number for the demo.

## What's in here

| File | What it is |
|------|------------|
| `partners.json` | 22 synthetic SME companies and their 53 products - the portfolio you assess. A few carry illustrative current gaps (5 companies); the rest are for you to assess. |
| `partners.csv` | The same portfolio, one row per product, for spreadsheets. |
| `taxonomy.json` | Controlled vocabulary: product categories, substances, regulation families. |
| `sample_expected_output.json` | The shape of one finding (gap + source + alert) - what your agent should emit. |
| `regulatory_updates.json` | **Examples** (50) of regulatory updates - they show the shape of a rule so you recognise one when you scrape live. Illustrative, not the task and not a dataset to match against. |
| `feed/` | 10 of the same examples rendered as HTML notices, so you see what a real page looks like. |
| `dataset_stats.json` | Summary counts. |

## The portfolio (`partners.json`)

Each **partner** has `partner_id`, `company`, `hq_country`, `sells_in` (markets; `EU` = all 27
states), and a `contact` (`name`, `email`, `phone`, `preferred_channel`).

Each **product** carries the attributes you reason about to infer obligations:
`category`, `substances`, `has_battery` + `battery_type` (`portable`/`button_cell`/`lmt`/`industrial`)
+ `battery_capacity_wh`, `has_radio`, `connector`, `packaging`, `intended_use`
(`consumer`/`toy`/`industrial`/`medical`), `markets`, and `compliance_streams`.

A few companies also include a **`compliance_status`** block: `certs_held` and `known_gaps` (concrete
current failings you can verify against live sources). Most companies have no such block on purpose -
working out their gaps from current requirements is the challenge.

## How to think about obligations & gaps

For each company/product, an obligation generally applies when the product's profile lands in a
rule's scope:
1. **Market** - the company sells where the rule applies (`EU` = all 27 states; some rules are one
   country only).
2. **Category** - the rule covers the product's category (or all electronics).
3. **Substance** - if a rule names a substance, the product actually contains it.
4. **Attributes** - e.g. battery type/capacity, has-radio, connector, intended use, packaging.
5. **Exclusions** - e.g. general consumer-safety rules don't cover medical/industrial-only equipment.

A **gap** is an obligation that applies *and* the company hasn't met yet. Watch the look-alikes:
right category but wrong market, a substance that isn't actually present, or an attribute that takes
a product out of scope (e.g. a passport rule that hits industrial batteries but not portable ones).
Cite the source you used for every gap.

## Example regulatory updates (`regulatory_updates.json` + `feed/`)

These are **examples** - they show you the shape of a regulatory update so you recognise one when you
pull current rules from live sources. They are illustrative, **not the task and not a dataset to match
against**. The set is deliberately varied - it mixes in unrelated-domain entries and
duplicate/correction entries (`corrects` field) - so you also see what noise looks like. Each example
has a free-text `summary` plus a `scope` block (categories / substances / markets / conditions).

*The portfolio is generated from a maintainer script and is intentionally synthetic.*
