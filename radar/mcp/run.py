"""
MCP — API-key-driven knowledge extraction and orchestration.

Whiteboard flow (credentials required for live APIs):
  EUR-Lex / DIP / Open Legal Data (your API keys)
        -> MCP knowledge extract
        -> embed (same model) -> router -> taxonomy + HIL -> present
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

from radar import embed, hil, ingest, regcache, router, translate, vectordb
from radar.config import ensure_dirs, env, load_dotenv
from radar import sources

# ponytail: registry maps each live API to required .env keys
API_SOURCES: dict[str, dict[str, Any]] = {
    "EUR-Lex": {
        "env_keys": ["EURLEX_USER", "EURLEX_PASSWORD"],
        "fetch_raw": ingest.fetch_eurlex_raw,
        "to_update": translate.from_eurlex,
        "fallback": ingest.eurlex_fallback_raw,
    },
    "Bundestag": {
        "env_keys": ["BUNDESTAG_DIP_KEY"],
        "fetch_raw": ingest.fetch_bundestag_raw,
        "to_update": translate.from_dip,
    },
    "OpenLegalData": {
        "env_keys": ["OPENLEGALDATA_API_KEY"],
        "optional_keys": True,
        "fetch_raw": ingest.fetch_openlegaldata_raw,
        "to_update": translate.from_openlegaldata,
    },
    "ECHA": {
        "env_keys": [],
        "local": True,
        "fetch": ingest.fetch_echa,
    },
}


def credentials_status() -> dict[str, dict[str, Any]]:
    """Report which API keys are configured (never exposes values)."""
    out: dict[str, dict[str, Any]] = {}
    for name, cfg in API_SOURCES.items():
        keys = cfg.get("env_keys", [])
        if cfg.get("local"):
            out[name] = {"configured": True, "mode": "local_files", "keys": []}
            continue
        present = {k: bool(env(k)) for k in keys}
        if cfg.get("optional_keys"):
            configured = True
        else:
            configured = all(present.values()) if keys else True
        out[name] = {
            "configured": configured,
            "keys": keys,
            "present": present,
            "optional": bool(cfg.get("optional_keys")),
        }
    return out


def extract_knowledge(raw: dict[str, Any], source: str) -> dict[str, Any]:
    """Normalize any API payload into MCP knowledge record."""
    title = raw.get("title") or raw.get("titel") or raw.get("legislationTitle") or raw.get("kurztitel") or ""
    ref = raw.get("reference") or raw.get("celex") or raw.get("id") or raw.get("Dokumentnummer") or ""
    summary = raw.get("summary") or raw.get("abstract") or raw.get("Kurztitel") or title
    return {
        "source": source,
        "title": title,
        "reference": ref,
        "summary": summary,
        "text_blob": f"{title} {ref} {summary}",
        "extracted_at": datetime.utcnow().isoformat() + "Z",
    }


def _knowledge_to_update(raw: dict[str, Any], source: str, to_update: Callable) -> dict[str, Any]:
    knowledge = extract_knowledge(raw, source)
    update = to_update(raw)
    update["mcp_knowledge"] = knowledge
    update["mcp_source_authenticated"] = True
    return regcache.attach_to_update(update, raw)


def fetch_from_apis(sources_filter: tuple[str, ...] | None = None) -> dict[str, Any]:
    """
    MCP fetch stage: call live APIs using configured keys, extract knowledge, write cache.
    Skips sources without credentials (except ECHA local + OpenLegalData public GET).
    """
    load_dotenv()
    ensure_dirs()
    state = ingest.load_state()
    cache = ingest.load_cache()
    creds = credentials_status()
    active = sources_filter or sources.ACTIVE_CONNECTORS
    total_added = 0
    source_stats: dict[str, Any] = {}

    for name in active:
        cfg = API_SOURCES.get(name)
        if not cfg:
            continue

        src_state = state.get(name, {})
        last = src_state.get("last_fetched", "2025-01-01")
        records: list[dict] = []

        if cfg.get("local"):
            print(f"MCP: loading {name} from local organizer files...")
            records = cfg["fetch"](last)
            for rec in records:
                rec["mcp_knowledge"] = extract_knowledge(
                    {"title": rec.get("title"), "reference": rec.get("reference"), "summary": rec.get("summary")},
                    name,
                )
                rec["mcp_source_authenticated"] = True
                regcache.attach_to_update(rec, {"title": rec.get("title"), "reference": rec.get("reference"), "summary": rec.get("summary")})
            source_stats[name] = {"status": "ok", "mode": "local", "fetched": len(records)}
        else:
            status = creds.get(name, {})
            has_keys = status.get("configured", False)

            if not has_keys:
                if name == "EUR-Lex" and cfg.get("fallback"):
                    print(f"MCP: {name} keys missing - using CELEX fallback anchors")
                    raw_hits = cfg["fallback"]()
                    records = [_knowledge_to_update(r, name, cfg["to_update"]) for r in raw_hits]
                    source_stats[name] = {"status": "fallback", "reason": "missing_api_keys", "fetched": len(records)}
                else:
                    missing = [k for k, ok in status.get("present", {}).items() if not ok]
                    print(f"MCP: skipping {name} - set {', '.join(missing or cfg.get('env_keys', []))}")
                    source_stats[name] = {"status": "skipped", "reason": "missing_api_keys", "fetched": 0}
                    continue
            else:
                key_hint = ", ".join(k for k in cfg.get("env_keys", []) if env(k))
                print(f"MCP: fetching {name} with API credentials ({key_hint})...")
                try:
                    raw_hits = cfg["fetch_raw"](last)
                    records = [_knowledge_to_update(r, name, cfg["to_update"]) for r in raw_hits]
                    source_stats[name] = {
                        "status": "ok",
                        "mode": "live_api",
                        "authenticated": True,
                        "fetched": len(records),
                    }
                except Exception as e:
                    print(f"MCP: {name} API error - {e}")
                    source_stats[name] = {"status": "error", "error": str(e), "fetched": 0}
                    continue

        added = ingest.merge_updates(cache, records)
        total_added += added
        source_stats[name]["added"] = added
        state[name] = {
            "last_fetched": date.today().isoformat(),
            "last_run": datetime.utcnow().isoformat() + "Z",
            "mcp_authenticated": source_stats[name].get("authenticated", name != "EUR-Lex"),
        }

    ingest.save_cache(cache)
    ingest.save_state(state)

    return {
        "ingested_new": total_added,
        "api_credentials": creds,
        "sources": source_stats,
    }


def enrich_cache() -> dict[str, Any]:
    """MCP enrich stage: embed, cosine-route, cluster, HIL queue."""
    ensure_dirs()
    cache = ingest.load_cache()
    updates = cache.get("updates", [])
    if not updates:
        return {"processed": 0, "clusters": 0, "hil_queued": 0, "vector_entries": 0}

    texts = [u.get("mcp_knowledge", {}).get("text_blob") or f"{u.get('title', '')} {u.get('summary', '')}" for u in updates]
    tax = router._taxonomy_index_text()
    texts.extend(e["text"] for e in tax)

    embedder = embed.Embedder()
    embedder.fit(texts)
    router.build_index(embedder)

    enriched: list[dict] = []
    vectors: list[tuple[str, list[float]]] = []

    for update in updates:
        if not update.get("regulation_text_key"):
            regcache.attach_to_update(update)
        text = update.get("mcp_knowledge", {}).get("text_blob") or f"{update.get('title', '')} {update.get('summary', '')}"
        vec = embedder.embed(text)
        uid = update.get("update_id") or update.get("dedup_key", "")
        vectors.append((uid, vec))
        vectordb.upsert(
            f"reg:{uid}",
            "regulation",
            text,
            vec,
            {"source": update.get("source"), "title": update.get("title")},
        )

        matches = router.route(text, embedder, top_k=3)
        enriched_update = router.apply_routing_to_update(update, matches)
        enriched_update["mcp_processed"] = True
        hil.enqueue(enriched_update, matches)
        enriched.append(enriched_update)

    cluster_map = embed.cluster_by_similarity(vectors)
    for u in enriched:
        uid = u.get("update_id") or u.get("dedup_key", "")
        u["cluster_id"] = cluster_map.get(uid)

    cache["updates"] = enriched
    ingest.save_cache(cache)

    return {
        "processed": len(enriched),
        "clusters": len(set(cluster_map.values())),
        "hil_queued": len(hil.list_pending()),
        "vector_entries": len(vectordb.get_all()),
    }


def run(sources_filter: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Full MCP pipeline: API fetch (with keys) -> enrich -> return combined stats."""
    fetch_stats = fetch_from_apis(sources_filter)
    enrich_stats = enrich_cache()
    return {**fetch_stats, **enrich_stats}


# Backward-compatible alias
process_cache = enrich_cache
