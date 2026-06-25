"""Feature 3: chapter-by-chapter plot + character arcs (README §7, Feature 3).

Requires plot_overall.txt as a precondition. Reduces summaries + overall plot into an
outline via reflection_loop; writes plot_chapters.json and character_arcs.json, both
re-loaded and adjusted from file on subsequent edits.
"""
import json

from core.files import read_text, read_json, write_json
from core.state import load_state, set_artifact
from core.worldbuilding import load_world_bible, render_for_prompt
from features._shared import get_summaries_text
from llm.json_utils import parse_json_response
from llm.pipelines import reflection_loop
from llm.prompt_loader import render_prompt

MAX_ITERS = 3


def has_overall_plot(project):
    return bool(read_text(project.plot_overall_txt, default="").strip())


def load_existing_outline(project):
    plot_chapters = read_json(project.plot_chapters_json, default=[])
    character_arcs = read_json(project.character_arcs_json, default={})
    return plot_chapters, character_arcs


def run_outline_loop(project, client, max_iters=MAX_ITERS):
    """Generator: builds/refines the chapter-by-chapter outline + character arcs."""
    world_bible_text = render_for_prompt(load_world_bible(project))
    summaries_text = get_summaries_text(project)
    plot_overall = read_text(project.plot_overall_txt)
    state = load_state(project)
    start_chapter = state["current_write_chapter"]

    def draft_fn():
        prompt = render_prompt(
            "f3_outline", world_bible=world_bible_text, summaries=summaries_text,
            plot_overall=plot_overall, start_chapter=start_chapter,
        )
        response = client.call(
            system="You are a meticulous story outliner. Respond with strict JSON.",
            messages=[{"role": "user", "content": prompt}], json_mode=True, temperature=0.5,
        )
        parsed = parse_json_response(response, default={"plot_chapters": [], "character_arcs": {}})
        return json.dumps(parsed, ensure_ascii=False)

    def critique_fn(draft):
        prompt = render_prompt("f3_critique", plot_overall=plot_overall, draft=draft)
        response = client.call(
            system="You are a meticulous outline critic. Respond with strict JSON.",
            messages=[{"role": "user", "content": prompt}], json_mode=True, temperature=0.2,
        )
        return parse_json_response(response, default={}).get("fixes", [])

    def revise_fn(draft, fixes):
        prompt = render_prompt("f3_revise", draft=draft, fixes=json.dumps(fixes, ensure_ascii=False))
        response = client.call(
            system="You revise structured outlines precisely. Respond with strict JSON.",
            messages=[{"role": "user", "content": prompt}], json_mode=True, temperature=0.3,
        )
        return response

    yield from reflection_loop(draft_fn, critique_fn, revise_fn, max_iters=max_iters)


def save_outline(project, outline_json_text):
    parsed = parse_json_response(outline_json_text, default={"plot_chapters": [], "character_arcs": {}})
    write_json(project.plot_chapters_json, parsed.get("plot_chapters", []))
    write_json(project.character_arcs_json, parsed.get("character_arcs", {}))
    set_artifact(project, "plot_chapters", True)
    return parsed
