"""Feature 1: refine a chapter's prose/translation + propose name canon fixes (README §7,
Feature 1). reflection_loop on one chapter + a deterministic name pass."""
import json

from core.characters import load_characters, propose_name_additions, apply_name_canon
from core.epub_io import read_chapter_text, replace_chapter
from core.state import mark_chapter_refined
from core.worldbuilding import load_world_bible, render_for_prompt
from llm.json_utils import parse_json_response
from llm.pipelines import reflection_loop
from llm.prompt_loader import render_prompt

MAX_ITERS = 3


def get_chapter_for_refine(working_epub_path, project, chapter_n):
    return read_chapter_text(working_epub_path, project, chapter_n)


def run_refine_loop(project, client, working_epub_path, chapter_n, max_iters=MAX_ITERS):
    """Generator yielding reflection_loop progress for refining one chapter."""
    title, chapter_text, _html = read_chapter_text(working_epub_path, project, chapter_n)
    world_bible_text = render_for_prompt(load_world_bible(project))
    characters = load_characters(project)
    name_canon_text = json.dumps(characters.get("canonical_names", {}), ensure_ascii=False)

    def draft_fn():
        prompt = render_prompt(
            "f1_draft", world_bible=world_bible_text, name_canon=name_canon_text,
            chapter_n=chapter_n, chapter_text=chapter_text,
        )
        return client.call(
            system="You are a careful fanfiction editor. Preserve plot and voice; fix only translation and formatting issues.",
            messages=[{"role": "user", "content": prompt}], temperature=0.4,
        )

    def critique_fn(draft):
        prompt = render_prompt(
            "f1_critique", world_bible=world_bible_text, chapter_text=chapter_text, draft=draft,
        )
        response = client.call(
            system="You are a precise editorial critic. Always respond with strict JSON.",
            messages=[{"role": "user", "content": prompt}], json_mode=True, temperature=0.2,
        )
        return parse_json_response(response, default={}).get("fixes", [])

    def revise_fn(draft, fixes):
        prompt = render_prompt("f1_revise", draft=draft, fixes=json.dumps(fixes, ensure_ascii=False))
        return client.call(
            system="You apply precise edits without introducing new changes.",
            messages=[{"role": "user", "content": prompt}], temperature=0.3,
        )

    yield from reflection_loop(draft_fn, critique_fn, revise_fn, max_iters=max_iters)


def propose_name_fixes(project, client, working_epub_path, chapter_n):
    """Name-analysis prompt that PROPOSES additions; never applies them."""
    _title, chapter_text, _html = read_chapter_text(working_epub_path, project, chapter_n)
    characters = load_characters(project)
    prompt = render_prompt(
        "f1_names",
        existing_canon=json.dumps(characters.get("canonical_names", {}), ensure_ascii=False),
        chapter_n=chapter_n, chapter_text=chapter_text,
    )
    response = client.call(
        system="You detect character name inconsistencies. Always respond with strict JSON.",
        messages=[{"role": "user", "content": prompt}], json_mode=True, temperature=0.2,
    )
    proposal = parse_json_response(response, default={})
    proposal.setdefault("canonical_names", {})
    proposal.setdefault("au_canon_swaps", [])
    return proposal


def merge_name_proposal(project, proposal):
    """User-confirmed proposal -> merged into characters.json (still no text changed)."""
    data = load_characters(project)
    merged = propose_name_additions(data, proposal)
    from core.characters import save_characters
    save_characters(project, merged)
    return merged


def apply_refinement(working_epub_path, project, chapter_n, title, refined_text):
    """Deterministic pass: apply confirmed name canon, then replace the chapter in
    working.epub and mark it refined in state.json."""
    characters = load_characters(project)
    final_text = apply_name_canon(refined_text, characters, chapter_n=chapter_n)
    replace_chapter(working_epub_path, project, chapter_n, title, final_text)
    mark_chapter_refined(project, chapter_n)
    return final_text
