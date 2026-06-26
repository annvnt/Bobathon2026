# Label Map — canonical regulation labels for EcoComply

This file is the **single source of truth** for automated product labeling. The classifier
emits **only** labels listed in the machine-readable table below, and uses each label's
`Source URL` when citing a gap. It is derived from `SOURCES.md` ("Which source for which
rule") and `taxonomy.json` (`regulation_families`).

To add/remove a label or change which products it attaches to, edit the table — no code change.

## Trigger syntax

The `Triggers` column is a space-separated list of conditions; a label attaches to a product
if **any** condition matches (OR). Tokens:

- `eee` — any electrical/electronic equipment (any category except `cable`)
- `battery` — `has_battery` is true
- `radio` — `has_radio` is true
- `consumer` / `toy` / `medical` / `industrial` — `intended_use` equals this
- `packaging` — product has any packaging
- `substance:A,B,C` — product contains any of these substance keys
- `category:a,b,c` — product category is one of these keys

## Labels (machine-readable)

| Label | Regulation | Source | Source URL | Triggers |
|-------|-----------|--------|-----------|----------|
| RoHS | Directive 2011/65/EU — restriction of hazardous substances | ECHA + EUR-Lex | https://eur-lex.europa.eu/eli/dir/2011/65/oj | eee |
| REACH | Regulation (EC) 1907/2006 — SVHC list & Annex XVII | ECHA | https://echa.europa.eu/candidate-list-table | substance:DEHP,DBP,BBP,BPA,PFAS_PFHxA,MCCP,TBBPA,decaBDE,dioxane |
| WEEE | Directive 2012/19/EU — waste electrical & electronic equipment | National EPR (stiftung ear) | https://eur-lex.europa.eu/eli/dir/2012/19/oj | eee |
| Battery | Regulation (EU) 2023/1542 — batteries & battery passport | EUR-Lex | https://eur-lex.europa.eu/eli/reg/2023/1542/oj | battery |
| PPWR | Regulation (EU) 2025/40 — packaging & packaging waste | EUR-Lex | https://eur-lex.europa.eu/eli/reg/2025/40/oj | packaging |
| GPSR | Regulation (EU) 2023/988 — general product safety | Safety Gate + EUR-Lex | https://eur-lex.europa.eu/eli/reg/2023/988/oj | consumer toy |
| RED | Directive 2014/53/EU — radio equipment | EUR-Lex + harmonised standards | https://eur-lex.europa.eu/eli/dir/2014/53/oj | radio |
| EMC | Directive 2014/30/EU — electromagnetic compatibility | EUR-Lex | https://eur-lex.europa.eu/eli/dir/2014/30/oj | eee |
| LVD | Directive 2014/35/EU — low voltage | EUR-Lex | https://eur-lex.europa.eu/eli/dir/2014/35/oj | eee |
| ESPR | Regulation (EU) 2024/1781 — ecodesign & Digital Product Passport | ESPR / EPREL | https://eur-lex.europa.eu/eli/reg/2024/1781/oj | category:display,led_lighting,power_supply |
| EnergyLabel | Regulation (EU) 2017/1369 — energy labelling | EPREL | https://eprel.ec.europa.eu | category:led_lighting,display,power_supply,appliance |
| ToySafety | Directive 2009/48/EC — toy safety | EUR-Lex | https://eur-lex.europa.eu/eli/dir/2009/48/oj | toy |
| MDR | Regulation (EU) 2017/745 — medical devices | EUR-Lex | https://eur-lex.europa.eu/eli/reg/2017/745/oj | medical |
| POPs | Regulation (EU) 2019/1021 — persistent organic pollutants | ECHA + EUR-Lex | https://eur-lex.europa.eu/eli/reg/2019/1021/oj | substance:decaBDE,TBBPA |
| Machinery | Regulation (EU) 2023/1230 — machinery | EUR-Lex | https://eur-lex.europa.eu/eli/reg/2023/1230/oj | category:printer_3d,appliance |
