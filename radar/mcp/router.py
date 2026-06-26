"""Cosine-similarity router: regulation -> taxonomy with probabilities."""

from __future__ import annotations

import json
from typing import Any

from radar.mcp import embed, vectordb
from radar.compliance import taxonomy
from radar.config import PARTNERS_FILE, ROUTER_INDEX_FILE, TAXONOMY_FILE, ensure_dirs


def _taxonomy_index_text() -> list[dict[str, Any]]:
    """Build routable taxonomy entries (Book -> Category -> Regulation families)."""
    tax = taxonomy.load_taxonomy()
    entries: list[dict[str, Any]] = []
    for family, desc in tax.get("regulation_families", {}).items():
        entries.append({
            "id": f"family:{family}",
            "label": family,
            "book": "Regulation",
            "category": family,
            "text": f"{family} {desc}",
        })
    for cat, desc in tax.get("product_categories", {}).items():
        entries.append({
            "id": f"category:{cat}",
            "label": cat,
            "book": "Product",
            "category": cat,
            "text": f"{cat} {desc}",
        })
    for sub, desc in tax.get("substances", {}).items():
        entries.append({
            "id": f"substance:{sub}",
            "label": sub,
            "book": "Substance",
            "category": "chemicals",
            "text": f"{sub} {desc}",
        })
    return entries


def build_index(embedder: embed.Embedder) -> list[dict]:
    """Index taxonomy + partner portfolio into vector DB."""
    texts: list[str] = []
    entries = _taxonomy_index_text()

    partners = json.loads(PARTNERS_FILE.read_text(encoding="utf-8"))
    for p in partners.get("partners", []):
        for prod in p.get("products", []):
            text = (
                f"{prod.get('name')} {prod.get('category')} "
                f"{' '.join(prod.get('substances', []))} "
                f"{prod.get('battery_type', '')} {prod.get('intended_use', '')}"
            )
            entries.append({
                "id": f"product:{prod.get('product_id')}",
                "label": prod.get("name"),
                "book": "Partner",
                "category": prod.get("category"),
                "text": text,
                "meta": {"partner_id": p.get("partner_id"), "product_id": prod.get("product_id")},
            })
            texts.append(text)

    for e in entries:
        texts.append(e["text"])

    embedder.fit(texts)
    vectordb.save_vocab(embedder.vocab)

    indexed: list[dict] = []
    for e in entries:
        vec = embedder.embed(e["text"])
        vectordb.upsert(e["id"], e["book"].lower(), e["text"], vec, {
            "label": e["label"],
            "category": e.get("category"),
            **e.get("meta", {}),
        })
        indexed.append({**e, "vector": vec})

    ensure_dirs()
    ROUTER_INDEX_FILE.write_text(
        json.dumps({"entries": [{k: v for k, v in e.items() if k != "vector"} for e in indexed]}, indent=2) + "\n",
        encoding="utf-8",
    )
    return indexed


def route(
    text: str,
    embedder: embed.Embedder,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Return top-k taxonomy/partner matches with normalized probabilities."""
    vec = embedder.embed(text)
    scored: list[dict[str, Any]] = []
    for entry in vectordb.get_all():
        sim = embed.cosine_similarity(vec, entry.get("vector", []))
        if sim <= 0.05:
            continue
        meta = entry.get("meta", {})
        scored.append({
            "id": entry["id"],
            "label": meta.get("label", entry["id"]),
            "kind": entry.get("kind"),
            "similarity": round(sim, 4),
        })
    scored.sort(key=lambda x: -x["similarity"])
    top = scored[:top_k]
    total = sum(x["similarity"] for x in top) or 1.0
    for x in top:
        x["probability_pct"] = round(x["similarity"] / total * 100, 1)
    return top


def apply_routing_to_update(update: dict, matches: list[dict]) -> dict:
    """Enrich update scope from router top match when keyword rules are weak."""
    if not matches:
        return update
    top = matches[0]
    update = dict(update)
    update["router_matches"] = matches
    update["router_confidence"] = top.get("probability_pct", 0)

    scope = dict(update.get("scope") or {})
    tid = top.get("id", "")
    if tid.startswith("family:") and update.get("regulation_family") in (None, "", "REACH"):
        update["regulation_family"] = tid.split(":", 1)[1]
    if tid.startswith("category:"):
        cat = tid.split(":", 1)[1]
        if scope.get("categories") == "all":
            scope["categories"] = [cat]
    if tid.startswith("substance:"):
        sub = tid.split(":", 1)[1]
        subs = list(scope.get("substances") or [])
        if sub not in subs:
            subs.append(sub)
        scope["substances"] = subs
    update["scope"] = scope
    return update
