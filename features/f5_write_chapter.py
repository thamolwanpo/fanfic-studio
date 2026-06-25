"""Feature 5: write the next chapter (README §7, Feature 5 + §7.1 editor-style adjustment).

Assembles all artifacts -> reflection_loop drafts the chapter -> two-track editor
(direct text edits + line-range instructions) -> on Done: append to working.epub,
advance state.current_write_chapter, summarize the new chapter, and surface any newly
proposed world facts to Feature 0's review gate.
"""
import json

from core.characters import load_characters, apply_name_canon
from core.epub_io import append_chapter
from core.files import read_text, read_json, write_text
from core.state import load_state, save_state
from core.summaries import upsert_chapter_summary
from core.worldbuilding import load_world_bible, render_for_prompt, current_facts
from features._shared import get_summaries_text, SUMMARY_PROMPT, SUMMARY_SYSTEM
from llm.json_utils import parse_json_response
from llm.pipelines import reflection_loop
from llm.prompt_loader import render_prompt

MAX_ITERS = 3


def present_artifact_status(project):
    state = load_state(project)
    return {
        "world_bible": state["artifacts"].get("world_bible", False),
        "plot_overall": state["artifacts"].get("plot_overall", False),
        "plot_chapters": state["artifacts"].get("plot_chapters", False),
        "style_guide": state["artifacts"].get("style_guide", False),
        "next_chapter": state["current_write_chapter"],
    }


def _chapter_outline_entry(project, chapter_n):
    plot_chapters = read_json(project.plot_chapters_json, default=[])
    for entry in plot_chapters:
        if entry.get("chapter") == chapter_n:
            return entry
    return {"chapter": chapter_n, "goal": "(no outline entry yet)", "beats": [], "arcs_advanced": []}


def run_write_loop(project, client, max_iters=MAX_ITERS):
    """Generator: drafts the next chapter using all available artifacts."""
    state = load_state(project)
    chapter_n = state["current_write_chapter"]

    world_bible_text = render_for_prompt(load_world_bible(project))
    characters = load_characters(project)
    name_canon_text = json.dumps(characters.get("canonical_names", {}), ensure_ascii=False)
    style_guide = read_text(project.style_guide_txt, default="(no style guide yet)")
    outline_entry = _chapter_outline_entry(project, chapter_n)
    character_arcs = read_json(project.character_arcs_json, default={})
    recent_summaries = get_summaries_text(project, last_n=5)

    def draft_fn():
        prompt = render_prompt(
            "f5_draft", world_bible=world_bible_text, name_canon=name_canon_text,
            style_guide=style_guide, chapter_outline=json.dumps(outline_entry, ensure_ascii=False),
            character_arcs=json.dumps(character_arcs, ensure_ascii=False),
            recent_summaries=recent_summaries, chapter_n=chapter_n,
        )
        return client.call(
            system="You are ghost-writing in the original author's voice. Stay strictly within the AU.",
            messages=[{"role": "user", "content": prompt}], temperature=0.8,
        )

    def critique_fn(draft):
        prompt = render_prompt(
            "f5_critique", world_bible=world_bible_text, chapter_outline=json.dumps(outline_entry, ensure_ascii=False),
            style_guide=style_guide, draft=draft,
        )
        response = client.call(
            system="You are a meticulous fiction critic. Respond with strict JSON.",
            messages=[{"role": "user", "content": prompt}], json_mode=True, temperature=0.2,
        )
        return parse_json_response(response, default={}).get("fixes", [])

    def revise_fn(draft, fixes):
        prompt = render_prompt("f5_revise", draft=draft, fixes=json.dumps(fixes, ensure_ascii=False))
        return client.call(
            system="You apply precise fiction edits in the author's voice.",
            messages=[{"role": "user", "content": prompt}], temperature=0.6,
        )

    yield from reflection_loop(draft_fn, critique_fn, revise_fn, max_iters=max_iters)


def apply_editor_adjustment(project, client, current_text, instructions):
    """Track A (direct edits, already folded into current_text by the caller) + Track B
    (targeted line-range instructions) -> one reflection/adjustment pass (README §7.1)."""
    world_bible_text = render_for_prompt(load_world_bible(project))
    style_guide = read_text(project.style_guide_txt, default="(no style guide yet)")
    instructions_text = "\n".join(
        f"- lines {i['start']}-{i['end']}: {i['instruction']}" for i in instructions
    ) or "(no targeted instructions; only direct edits)"

    prompt = render_prompt(
        "f5_adjust", world_bible=world_bible_text, style_guide=style_guide,
        current_text=current_text, instructions=instructions_text,
    )
    return client.call(
        system="You apply edit instructions precisely and verify world/style/name consistency.",
        messages=[{"role": "user", "content": prompt}], temperature=0.5,
    )


def propose_new_facts(project, client, chapter_text):
    data = load_world_bible(project)
    existing = json.dumps(current_facts(data), ensure_ascii=False)
    prompt = render_prompt("f5_facts", existing_facts=existing, chapter_text=chapter_text)
    response = client.call(
        system="You extract newly established worldbuilding facts. Respond with strict JSON.",
        messages=[{"role": "user", "content": prompt}], json_mode=True, temperature=0.2,
    )
    return parse_json_response(response, default={}).get("new_facts", [])


def commit_chapter(working_epub_path, project, client, accepted_text, model_name, title=None):
    """On Done: apply name canon, append to working.epub, advance the pointer, and cache
    a summary of the new chapter. Returns (chapter_n, proposed_new_facts) — the caller is
    responsible for routing proposed_new_facts to Feature 0's review gate."""
    state = load_state(project)
    chapter_n = state["current_write_chapter"]
    chapter_title = title or f"Chapter {chapter_n}"

    characters = load_characters(project)
    final_text = apply_name_canon(accepted_text, characters, chapter_n=chapter_n)

    new_chapter_n = append_chapter(working_epub_path, project, chapter_title, final_text)

    summary_prompt = SUMMARY_PROMPT.format(n=new_chapter_n, title=chapter_title, text=final_text)
    response = client.call(system=SUMMARY_SYSTEM, messages=[{"role": "user", "content": summary_prompt}],
                            json_mode=True, temperature=0.2)
    parsed = parse_json_response(response, default={})
    upsert_chapter_summary(
        project, new_chapter_n, chapter_title,
        parsed.get("summary", ""), parsed.get("characters_present", []),
        parsed.get("open_threads", []), model_name,
    )

    state["current_write_chapter"] = new_chapter_n + 1
    save_state(project, state)

    proposed_facts = propose_new_facts(project, client, final_text)
    return new_chapter_n, proposed_facts
