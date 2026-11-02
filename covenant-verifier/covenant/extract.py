"""LLM extraction: retrieved definition text in, draft spec JSON out. The only probabilistic step.

Runs only when OPENROUTER_API_KEY is set. Raw responses are cached in outputs/ so results are reproducible
and reviewers can rerun the notebook without a key.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

PROMPT = """You convert one credit agreement definition into a JSON rule spec. You do not compute anything.

Rules:
- Use ONLY the text provided. Every "quote" must be copied VERBATIM from it (a short exact span).
- If something affects the calculation but you cannot pin it down from the text, add a sentence to "unresolved". Never guess.
- Cap "basis": "before_addbacks" or "after_addbacks", exactly as the proviso says.
- Output JSON only, no prose, no markdown fences.

Schema:
{{"adjustments": [{{"clause": "(a)", "label": str, "direction": "add"|"deduct", "cap_group": str|null,
   "conditions": [{{"type": "max_realization_months"|"officer_certification"|"analyst_judgment", "value": number|null,
                   "description": str, "citation": {{"section": str, "quote": str}}}}],
   "citation": {{"section": str, "quote": str}}}}],
 "cap_groups": [{{"id": str, "pct": number, "basis": str, "order": int, "members": [str], "citation": {{"section": str, "quote": str}}}}],
 "unresolved": [str]}}

Defined terms used by this definition (text provided below where relevant): {deps}

DEFINITION ({term}, Section 1.01):
{text}
"""


def build_prompt(term: str, text: str, deps: dict) -> str:
    return PROMPT.format(term=term, text=text, deps=", ".join(deps.get("computational", [])))


def call_openrouter(prompt: str, model: str) -> str:
    import requests
    key = os.environ["OPENROUTER_API_KEY"]
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "temperature": 0, "messages": [{"role": "user", "content": prompt}]},
        timeout=180,
    )
    if not resp.ok:
        raise RuntimeError(
            f"OpenRouter error {resp.status_code}: {resp.text}")

    data = resp.json()
    return data["choices"][0]["message"]["content"]


def parse_json(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    start, end = raw.find("{"), raw.rfind("}")
    return json.loads(raw[start:end + 1])


def extract(term: str, text: str, deps: dict, model: str, cache_dir: str = "outputs") -> dict | None:
    cache = Path(cache_dir) / f"extraction_{re.sub(r'[^A-Za-z0-9]+', '_', model)}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    if not os.environ.get("OPENROUTER_API_KEY"):
        return None
    raw = call_openrouter(build_prompt(term, text, deps), model)
    out = {"model": model, "raw": raw}
    try:
        out["spec"] = parse_json(raw)
    except Exception as e:  # report malformed output honestly rather than repairing it silently
        out["parse_error"] = str(e)
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps(out, indent=2))
    return out


def score(pred: dict, gold: dict, source_text: str) -> list[dict]:
    """Field-level comparison against the hand-built gold spec."""
    from .parser import quote_in_source
    rows = []
    g_adj = {a["clause"]: a for a in gold["adjustments"]}
    p_adj = {a.get("clause"): a for a in pred.get("adjustments", [])}
    for c, ga in g_adj.items():
        pa = p_adj.get(c)
        rows.append({"field": f"adjustment {c} found", "ok": pa is not None})
        if pa:
            rows.append({"field": f"adjustment {c} direction", "ok": pa.get("direction") == ga["direction"]})
            g_conds = sorted(x["type"] for x in ga.get("conditions", []))
            p_conds = sorted(x.get("type") for x in pa.get("conditions", []) or [])
            if g_conds:
                rows.append({"field": f"adjustment {c} conditions", "ok": g_conds == p_conds,
                             "note": f"pred {p_conds}"})
    for extra in set(p_adj) - set(g_adj):
        rows.append({"field": f"spurious adjustment {extra}", "ok": False})
    # cap groups matched by membership, not by the id the model invented
    for gg in gold["cap_groups"]:
        pg = next((x for x in pred.get("cap_groups", []) if sorted(x.get("members", [])) == sorted(gg["members"])), None)
        name = "+".join(gg["members"])
        rows.append({"field": f"cap group {name} members", "ok": pg is not None})
        if pg:
            rows.append({"field": f"cap group {name} pct", "ok": abs(float(pg.get("pct", 0)) - gg["pct"]) < 1e-9
                         or abs(float(pg.get("pct", 0)) / 100 - gg["pct"]) < 1e-9})
            rows.append({"field": f"cap group {name} basis", "ok": pg.get("basis") == gg["basis"]})
    quotes = [a.get("citation", {}).get("quote", "") for a in pred.get("adjustments", [])]
    quotes += [g.get("citation", {}).get("quote", "") for g in pred.get("cap_groups", [])]
    bad = [q for q in quotes if not quote_in_source(q, source_text)]
    rows.append({"field": f"quotes verbatim ({len(quotes) - len(bad)}/{len(quotes)})", "ok": not bad,
                 "note": "; ".join(q[:50] for q in bad[:3])})
    rows.append({"field": "unresolved items raised", "ok": True, "note": "; ".join(pred.get("unresolved", []))[:200]})
    return rows
