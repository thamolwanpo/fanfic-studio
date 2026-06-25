"""world_bible.json model: static rules + evolving facts ledger (README §4.3)."""
from core.files import read_json, write_json

DEFAULT_WORLD_BIBLE = {
    "premise": "",
    "rules": [],
    "facts": [],
    "canon_deviations": [],
}


def load_world_bible(project):
    return read_json(project.world_bible_json, default=None) or dict(DEFAULT_WORLD_BIBLE)


def save_world_bible(project, data):
    write_json(project.world_bible_json, data)


def next_id(items, prefix):
    existing = [int(item["id"][len(prefix):]) for item in items if item["id"].startswith(prefix) and item["id"][len(prefix):].isdigit()]
    return f"{prefix}{(max(existing) + 1) if existing else 1}"


def add_rule(data, statement, category, diverges_from_canon, established_chapter, locked=True):
    rule = {
        "id": next_id(data["rules"], "r"),
        "category": category,
        "statement": statement,
        "diverges_from_canon": diverges_from_canon,
        "established_chapter": established_chapter,
        "locked": locked,
    }
    data["rules"].append(rule)
    return data


def update_rule(data, rule_id, **fields):
    for rule in data["rules"]:
        if rule["id"] == rule_id:
            if rule.get("locked") and any(k != "locked" for k in fields):
                fields["_warning"] = "Editing a locked rule may break downstream chapters that depend on it."
            rule.update({k: v for k, v in fields.items() if not k.startswith("_")})
            return rule.get("_warning") if "_warning" in fields else None
    return None


def add_fact(data, statement, category, established_chapter, supersedes=None):
    fact = {
        "id": next_id(data["facts"], "f"),
        "category": category,
        "statement": statement,
        "established_chapter": established_chapter,
        "status": "current",
        "supersedes": None,
    }
    if supersedes:
        for old in data["facts"]:
            if old["id"] == supersedes:
                old["status"] = "superseded"
        fact["supersedes"] = supersedes
    data["facts"].append(fact)
    return data


def current_facts(data):
    return [f for f in data.get("facts", []) if f.get("status") == "current"]


def render_for_prompt(data):
    """Flatten the world bible into compact text suitable for injection into LLM context."""
    lines = [f"AU Premise: {data.get('premise', '')}", "", "Rules (must never be violated):"]
    for r in data.get("rules", []):
        lines.append(f"- [{r['id']}] ({r['category']}) {r['statement']}")
    lines.append("")
    lines.append("Current facts:")
    for f in current_facts(data):
        lines.append(f"- [{f['id']}] (ch.{f['established_chapter']}, {f['category']}) {f['statement']}")
    if data.get("canon_deviations"):
        lines.append("")
        lines.append("Canon deviations to remember:")
        for d in data["canon_deviations"]:
            lines.append(f"- {d}")
    return "\n".join(lines)
