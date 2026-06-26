"""Product / ingredient chat — find EUR-Lex & Open Legal Data regulations."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any

from radar.mcp import embed
from radar.ingest import regcache, translate
from radar.compliance import taxonomy
from radar.config import OPENLEGALDATA_BASE, env, load_dotenv
from radar.ingest.fetch import FALLBACK_CELEX, load_cache

ALLOWED_SOURCES = {"EUR-Lex", "OpenLegalData"}
MAX_RESULTS = 10
MAX_SECTION_FETCH = 5
MAX_SECTIONS_PER_REG = 4
SECTION_WINDOW = 320
TIMEOUT = 20
SKIP_SEARCH_TERMS = {"reach", "rohs", "red", "weee", "gpsr", "ppwr", "battery"}

SECTION_LABEL = re.compile(
    r"(?i)^(article\s+\d+[a-z]?(?:\s*\([^)]+\))?|annex\s+[ivxlcdm\d]+|chapter\s+\d+|section\s+\d+|§\s*\d+[^\s]*)",
)


def _has_word(text: str, term: str) -> bool:
    return bool(re.search(rf"\b{re.escape(term.lower())}\b", text.lower()))


def _relevant_oldp(update: dict, parsed: dict, search_term: str = "") -> bool:
    blob = " ".join(
        filter(None, [update.get("title"), update.get("summary"), update.get("reference")])
    ).lower()
    if any(sub.lower() in blob for sub in parsed.get("substances") or []):
        return True
    term = search_term.lower()
    if term and len(term) >= 4 and term not in SKIP_SEARCH_TERMS and _has_word(blob, term):
        return True
    for kw in parsed.get("keywords") or []:
        if len(kw) >= 5 and _has_word(blob, kw):
            return True
    return False


def _tokenize(text: str) -> set[str]:
    return set(embed.tokenize(text))


def parse_query(text: str) -> dict[str, Any]:
    """Extract substances, regulation families, and search tokens from free text."""
    load_dotenv()
    substance_set = set(taxonomy.resolve_substances(text))
    family = taxonomy.detect_family(text)
    families = {family} if family else set()
    for fam, kws in taxonomy.FAMILY_KEYWORDS.items():
        if any(kw in text.lower() for kw in kws):
            families.add(fam)

    extra_keywords: set[str] = set()
    for word in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{2,}", text.lower()):
        if word not in ("the", "and", "with", "for", "contains", "ingredients", "product"):
            extra_keywords.add(word)

    if "battery" in text.lower() or "lithium" in text.lower():
        families.add("Battery")
    if "phthalate" in text.lower() or "dehp" in text.lower():
        substance_set.add("DEHP")
        families.add("REACH")
        families.add("RoHS")

    return {
        "substances": sorted(substance_set),
        "families": sorted(families),
        "keywords": sorted(extra_keywords)[:20],
    }


def _score_update(update: dict, parsed: dict, query_tokens: set[str]) -> tuple[int, list[str]]:
    text = " ".join(
        filter(
            None,
            [
                update.get("title"),
                update.get("summary"),
                update.get("reference"),
                update.get("regulation_family"),
                " ".join(update.get("scope", {}).get("substances") or []),
            ],
        )
    ).lower()
    utokens = _tokenize(text)
    overlap = query_tokens & utokens
    matched: list[str] = []

    score = len(overlap) * 8
    if overlap:
        matched.extend(sorted(overlap)[:5])

    reg_subs = set(update.get("scope", {}).get("substances") or [])
    sub_hits = set(parsed.get("substances") or []) & reg_subs
    if sub_hits:
        score += 25 * len(sub_hits)
        matched.extend(sorted(sub_hits))

    fam = update.get("regulation_family", "")
    if fam in (parsed.get("families") or []):
        if update.get("source") == "EUR-Lex" or any(
            _has_word(text, sub.lower()) for sub in parsed.get("substances") or []
        ):
            score += 20
            if fam not in matched:
                matched.append(fam)

    for kw in parsed.get("keywords") or []:
        if kw in text:
            score += 5
            if kw not in matched:
                matched.append(kw)

    return score, matched


def _search_terms(parsed: dict, matched_terms: list[str] | None = None) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for group in (
        matched_terms or [],
        parsed.get("substances") or [],
        parsed.get("keywords") or [],
        [f for f in parsed.get("families") or [] if f.lower() not in SKIP_SEARCH_TERMS],
    ):
        for term in group:
            key = term.lower()
            if key and key not in seen and len(term) >= 2:
                seen.add(key)
                terms.append(term)
    return terms


def _snippet_around(text: str, term: str, window: int = SECTION_WINDOW) -> str:
    match = re.search(rf"(?i)\b{re.escape(term)}\b", text)
    if not match:
        return ""
    start = max(0, match.start() - window // 2)
    end = min(len(text), match.end() + window // 2)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return re.sub(r"\s+", " ", snippet)


def extract_relevant_sections(text: str, terms: list[str], max_sections: int = MAX_SECTIONS_PER_REG) -> list[dict]:
    """Pull regulation passages that mention query terms."""
    if not text or not terms:
        return []

    patterns = [(t, re.compile(rf"(?i)\b{re.escape(t)}\b")) for t in terms]
    labeled_chunks: list[tuple[str, str]] = []

    parts = re.split(
        r"(?=\b(?:Article|ANNEX|Annex|Chapter|Section)\s+[\w\d]+|\b§\s*\d+)",
        text,
        flags=re.I,
    )
    for part in parts:
        part = re.sub(r"\s+", " ", part).strip()
        if len(part) < 40:
            continue
        label_match = SECTION_LABEL.match(part[:120])
        label = label_match.group(0).strip() if label_match else "Excerpt"
        labeled_chunks.append((label, part[:2400]))

    if len(labeled_chunks) < 2:
        sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text))
        buf = ""
        for sentence in sentences:
            buf = f"{buf} {sentence}".strip()
            if len(buf) >= 350:
                labeled_chunks.append(("Excerpt", buf[:2400]))
                buf = ""
        if buf.strip():
            labeled_chunks.append(("Excerpt", buf.strip()[:2400]))

    scored: list[dict] = []
    seen_text: set[str] = set()
    for label, body in labeled_chunks:
        hits = [term for term, pat in patterns if pat.search(body)]
        if not hits:
            continue
        key = body[:120]
        if key in seen_text:
            continue
        seen_text.add(key)
        scored.append({
            "label": label,
            "text": body[:700],
            "matched_terms": hits,
            "score": len(hits) * 12 + sum(len(pat.findall(body)) for _, pat in patterns),
        })

    scored.sort(key=lambda item: -item["score"])

    if not scored:
        for term in terms[:4]:
            snippet = _snippet_around(text, term)
            if snippet:
                scored.append({
                    "label": f"Mention of {term}",
                    "text": snippet,
                    "matched_terms": [term],
                    "score": 1,
                })

    return [
        {
            "label": item["label"],
            "text": item["text"],
            "matched_terms": item["matched_terms"],
        }
        for item in scored[:max_sections]
    ]


def _enrich_with_sections(reg: dict, update: dict, parsed: dict) -> dict:
    terms = _search_terms(parsed, reg.get("matched_terms"))
    if not terms:
        return reg
    try:
        record = regcache.get_or_fetch(
            update.get("source") or reg["source"],
            update.get("reference") or reg["reference"],
            update.get("title") or reg["title"],
            regcache._raw_from_update(update),
        )
        reg["regulation_text_key"] = record.get("key")
        reg["sections"] = extract_relevant_sections(record.get("text") or "", terms)
        if reg["sections"] and not reg.get("excerpt"):
            reg["excerpt"] = reg["sections"][0]["text"][:400]
    except Exception:
        reg["sections"] = []
    return reg


def _build_term_sections(regulations: list[dict]) -> dict[str, list[dict]]:
    term_map: dict[str, list[dict]] = {}
    for reg in regulations:
        for section in reg.get("sections") or []:
            for term in section.get("matched_terms") or []:
                term_map.setdefault(term, [])
                term_map[term].append({
                    "regulation_id": reg["id"],
                    "regulation_title": reg.get("title"),
                    "source": reg.get("source"),
                    "label": section.get("label"),
                    "text": section.get("text"),
                    "matched_terms": section.get("matched_terms"),
                })
    return term_map


def _update_to_reg(update: dict, score: int, matched_terms: list[str]) -> dict[str, Any]:
    excerpt = (update.get("regulation_text_preview") or update.get("summary") or "")[:400]
    return {
        "id": update.get("update_id") or update.get("dedup_key", ""),
        "source": update.get("source"),
        "title": update.get("title") or update.get("reference"),
        "reference": update.get("reference", ""),
        "url": update.get("source_url", ""),
        "regulation_text_key": update.get("regulation_text_key"),
        "family": update.get("regulation_family", ""),
        "match_score": min(99, score),
        "matched_terms": matched_terms,
        "excerpt": excerpt,
        "sections": [],
    }


def _search_cache(query: str, parsed: dict) -> list[dict]:
    cache = load_cache()
    updates = cache.get("updates", [])
    qtokens = _tokenize(query)
    qtokens |= set(parsed.get("substances") or [])
    qtokens |= set(k.lower() for k in parsed.get("families") or [])
    qtokens |= set(parsed.get("keywords") or [])

    scored: list[tuple[int, dict, list[str]]] = []
    for u in updates:
        if u.get("source") not in ALLOWED_SOURCES:
            continue
        if u.get("source") == "OpenLegalData" and not _relevant_oldp(u, parsed):
            continue
        score, matched = _score_update(u, parsed, qtokens)
        if score > 0:
            scored.append((score, u, matched))

    scored.sort(key=lambda x: -x[0])
    return [_update_to_reg(u, s, m) for s, u, m in scored[:MAX_RESULTS]]


def _search_eurlex_anchors(query: str, parsed: dict) -> tuple[list[dict], dict[str, dict]]:
    """Known CELEX anchors when cache has no strong EUR-Lex hit."""
    q = query.lower()
    hits: list[dict] = []
    updates_by_id: dict[str, dict] = {}
    for celex, title in FALLBACK_CELEX:
        blob = f"{title} {celex}".lower()
        score = 0
        matched: list[str] = []
        if any(fam.lower() in q or fam.lower() in blob for fam in parsed.get("families") or []):
            score += 30
            for fam in parsed.get("families") or []:
                if fam.lower() in blob or fam.lower() in q:
                    matched.append(fam)
        for sub in parsed.get("substances") or []:
            if sub.lower() in q and celex in ("32011L0065", "32006R1907", "32007R1907"):
                score += 20
                matched.append(sub)
        if "battery" in q and "1542" in celex:
            score += 40
            matched.append("Battery")
        if score < 15:
            continue
        url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
        raw = {"celex": celex, "title": title, "reference": celex, "url": url}
        update = translate.from_eurlex(raw)
        update = regcache.attach_to_update(update, raw)
        reg = _update_to_reg(update, score, matched or [title[:30]])
        hits.append(reg)
        updates_by_id[reg["id"]] = update
    return hits[:4], updates_by_id


def _search_openlegaldata_live(query: str, parsed: dict) -> tuple[list[dict], dict[str, dict]]:
    load_dotenv()
    headers: dict[str, str] = {"Accept": "application/json"}
    api_key = env("OPENLEGALDATA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Token {api_key}"

    terms = list(parsed.get("substances") or [])
    terms += [w for w in parsed.get("keywords") or [] if len(w) > 4 and w.lower() not in SKIP_SEARCH_TERMS][:3]
    if not terms:
        terms = [w for w in _tokenize(query) if len(w) > 4 and w not in SKIP_SEARCH_TERMS][:2]
    if not terms:
        return [], {}

    seen: set[int] = set()
    results: list[dict] = []
    updates_by_id: dict[str, dict] = {}

    for term in terms[:4]:
        params = urllib.parse.urlencode({"search": term, "limit": "5", "ordering": "-updated_date"})
        url = f"{OPENLEGALDATA_BASE}/laws/?{params}"
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue
        for item in data.get("results", []):
            if not isinstance(item, dict):
                continue
            iid = item.get("id")
            if iid in seen:
                continue
            seen.add(iid)
            update = translate.from_openlegaldata(item)
            update = regcache.attach_to_update(update, item)
            if not _relevant_oldp(update, parsed, term):
                continue
            matched = [t for t in terms if t.lower() in (update.get("title") or "").lower()]
            reg = _update_to_reg(update, 40 + len(matched) * 10, matched or [term])
            results.append(reg)
            updates_by_id[reg["id"]] = update
            if len(results) >= 6:
                return results, updates_by_id
    return results, updates_by_id


def _build_message_parts(query: str, parsed: dict, regulations: list[dict]) -> list[dict]:
    """Build chat message with clickable term segments."""
    if not regulations:
        return [{
            "type": "text",
            "content": (
                "I couldn't find a strong EUR-Lex or Open Legal Data match for that description. "
                "Try naming specific substances (e.g. lead, DEHP) or product type (battery, toy, lighting)."
            ),
        }]

    parts: list[dict] = [{"type": "text", "content": "For your product description, these regulations may apply:\n\n"}]

    term_to_regs: dict[str, list[str]] = {}
    for reg in regulations:
        for term in reg.get("matched_terms") or []:
            term_to_regs.setdefault(term, [])
            if reg["id"] not in term_to_regs[term]:
                term_to_regs[term].append(reg["id"])

    if parsed.get("substances"):
        parts.append({"type": "text", "content": "Detected ingredients: "})
        for i, sub in enumerate(parsed["substances"]):
            if i:
                parts.append({"type": "text", "content": ", "})
            parts.append({
                "type": "term",
                "term": sub,
                "regulation_ids": term_to_regs.get(sub, [r["id"] for r in regulations[:2]]),
            })
        parts.append({"type": "text", "content": ".\n\n"})

    if parsed.get("families"):
        parts.append({"type": "text", "content": "Relevant rule areas: "})
        for i, fam in enumerate(parsed["families"]):
            if i:
                parts.append({"type": "text", "content": ", "})
            parts.append({
                "type": "term",
                "term": fam,
                "regulation_ids": term_to_regs.get(fam, [r["id"] for r in regulations if r.get("family") == fam][:2] or [regulations[0]["id"]]),
            })
        parts.append({"type": "text", "content": ".\n\nClick a highlighted term to jump to the matching passage, or open the full regulation below.\n"})

    return parts


def lookup(query: str) -> dict[str, Any]:
    """Find regulations for a product label / ingredient list."""
    query = (query or "").strip()
    if not query:
        return {"error": "Please describe the product or paste ingredient list."}

    parsed = parse_query(query)
    updates_by_id: dict[str, dict] = {}
    regulations = _search_cache(query, parsed)

    has_eurlex = any(r["source"] == "EUR-Lex" for r in regulations)
    has_oldp = any(r["source"] == "OpenLegalData" for r in regulations)

    if not has_eurlex or len([r for r in regulations if r["source"] == "EUR-Lex"]) < 2:
        seen_ids = {r["id"] for r in regulations}
        anchor_regs, anchor_updates = _search_eurlex_anchors(query, parsed)
        for reg in anchor_regs:
            if reg["id"] not in seen_ids:
                regulations.append(reg)
                updates_by_id[reg["id"]] = anchor_updates[reg["id"]]
                seen_ids.add(reg["id"])

    if not has_oldp or len([r for r in regulations if r["source"] == "OpenLegalData"]) < 2:
        seen_ids = {r["id"] for r in regulations}
        oldp_regs, oldp_updates = _search_openlegaldata_live(query, parsed)
        for reg in oldp_regs:
            if reg["id"] not in seen_ids:
                regulations.append(reg)
                updates_by_id[reg["id"]] = oldp_updates[reg["id"]]
                seen_ids.add(reg["id"])

    regulations.sort(key=lambda r: -r.get("match_score", 0))
    regulations = regulations[:MAX_RESULTS]

    cache = load_cache()
    for u in cache.get("updates", []):
        uid = u.get("update_id") or u.get("dedup_key", "")
        if uid:
            updates_by_id.setdefault(uid, u)

    enriched: list[dict] = []
    for reg in regulations:
        update = updates_by_id.get(reg["id"], {
            "source": reg.get("source"),
            "reference": reg.get("reference"),
            "title": reg.get("title"),
            "source_url": reg.get("url"),
        })
        if len(enriched) < MAX_SECTION_FETCH:
            enriched.append(_enrich_with_sections(reg, update, parsed))
        else:
            enriched.append(reg)
    regulations = enriched

    return {
        "query": query,
        "parsed": parsed,
        "message_parts": _build_message_parts(query, parsed, regulations),
        "term_sections": _build_term_sections(regulations),
        "regulations": regulations,
    }
