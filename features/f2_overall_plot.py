"""Feature 2: propose the overall ending plot (README §7, Feature 2).

map_reduce_summarize (via summaries cache) -> direction proposals -> user picks/blends ->
reflection_loop refines the chosen direction -> save as plot_overall.txt.
"""
import json

from core.files import write_text
from core.state import set_artifact
from core.worldbuilding import load_world_bible, render_for_prompt
from features._shared import get_summaries_text
from llm.json_utils import parse_json_response
from llm.pipelines import reflection_loop
from llm.prompt_loader import render_prompt

MAX_ITERS = 3


def propose_directions(project, client):
    world_bible_text = render_for_prompt(load_world_bible(project))
    summaries_text = get_summaries_text(project)
    prompt = render_prompt("f2_directions", world_bible=world_bible_text, summaries=summaries_text)
    response = client.call(
        system="You are an award-winning novelist with deep knowledge of story theory. Respond with strict JSON.",
        messages=[{"role": "user", "content": prompt}], json_mode=True, temperature=0.8,
    )
    return parse_json_response(response, default={}).get("directions", [])


def run_plot_loop(project, client, chosen_direction_text, max_iters=MAX_ITERS):
    """Generator: reflection loop that turns the user's picked/blended direction into a
    polished prose plot for the remainder of the story."""
    world_bible_text = render_for_prompt(load_world_bible(project))
    summaries_text = get_summaries_text(project)

    def draft_fn():
        return chosen_direction_text

    def critique_fn(draft):
        prompt = render_prompt("f2_critique", world_bible=world_bible_text, summaries=summaries_text, draft=draft)
        response = client.call(
            system="You are a meticulous story consistency critic. Respond with strict JSON.",
            messages=[{"role": "user", "content": prompt}], json_mode=True, temperature=0.2,
        )
        return parse_json_response(response, default={}).get("fixes", [])

    def revise_fn(draft, fixes):
        prompt = render_prompt("f2_revise", draft=draft, fixes=json.dumps(fixes, ensure_ascii=False))
        return client.call(
            system="You are an award-winning novelist refining a story plan.",
            messages=[{"role": "user", "content": prompt}], temperature=0.6,
        )

    yield from reflection_loop(draft_fn, critique_fn, revise_fn, max_iters=max_iters)


def save_overall_plot(project, plot_text):
    write_text(project.plot_overall_txt, plot_text)
    set_artifact(project, "plot_overall", True)
