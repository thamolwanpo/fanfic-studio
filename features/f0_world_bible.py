"""Feature 0: extract + maintain the AU world bible (README §7, Feature 0).

Flow: ensure summaries exist -> extraction agent proposes premise/rules/facts/canon
deviations -> UI shows an editable review panel -> user confirms -> save. Maintenance
mode (F5 proposing new facts) is exposed via review_new_facts() below.
"""
from core.state import set_artifact
from core.summaries import load_summaries, render_summaries_for_prompt
from core.worldbuilding import load_world_bible, save_world_bible, add_fact
from llm.client import LLMClient
from llm.json_utils import parse_json_response
from llm.prompt_loader import render_prompt


def extract_world_bible(project, client: LLMClient):
    """Runs the extraction agent against cached summaries. Returns a proposal dict;
    does NOT save. The UI review panel is responsible for the human approval gate."""
    summaries = load_summaries(project)
    if not summaries["chapters"]:
        raise ValueError("No chapter summaries found. Build the summary cache first.")

    prompt = render_prompt(
        "f0_extract",
        summaries=render_summaries_for_prompt(summaries),
    )
    response = client.call(
        system="You are a meticulous AU worldbuilding analyst. Always respond with strict JSON.",
        messages=[{"role": "user", "content": prompt}],
        json_mode=True,
        temperature=0.4,
    )
    proposal = parse_json_response(response, default={})
    proposal.setdefault("premise", "")
    proposal.setdefault("rules", [])
    proposal.setdefault("facts", [])
    proposal.setdefault("canon_deviations", [])
    for i, rule in enumerate(proposal["rules"], start=1):
        rule.setdefault("id", f"r{i}")
        rule.setdefault("locked", True)
    for i, fact in enumerate(proposal["facts"], start=1):
        fact.setdefault("id", f"f{i}")
        fact.setdefault("status", "current")
        fact.setdefault("supersedes", None)
    return proposal


def save_reviewed_world_bible(project, reviewed_data):
    """Called once the user has confirmed/edited the proposal in the UI review panel."""
    save_world_bible(project, reviewed_data)
    set_artifact(project, "world_bible", True)
    return reviewed_data


def review_new_facts(project, proposed_facts):
    """Surfaces F5-proposed new facts for review; called from the world bible tab when
    arriving with pending proposals. Returns the current bible plus the pending proposals
    so the UI can render them in the same review panel as initial extraction."""
    data = load_world_bible(project)
    return data, proposed_facts


def commit_new_facts(project, approved_facts):
    """Deterministically commits user-approved new facts (from F5 maintenance mode)."""
    data = load_world_bible(project)
    for fact in approved_facts:
        add_fact(
            data,
            statement=fact["statement"],
            category=fact.get("category", "general"),
            established_chapter=fact.get("established_chapter"),
            supersedes=fact.get("supersedes"),
        )
    save_world_bible(project, data)
    return data
