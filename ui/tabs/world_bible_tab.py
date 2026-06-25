"""UI tab for Feature 0: world bible builder."""
import json

import gradio as gr

from core.worldbuilding import load_world_bible
from features._shared import ensure_summaries
from features.f0_world_bible import extract_world_bible, save_reviewed_world_bible
from ui.components import require_project, require_client


def build_world_bible_tab(project_picker, model_picker, api_key_box):
    with gr.Tab("0. World Bible"):
        gr.Markdown(
            "Extract the AU's static rules and evolving facts ledger from the fic so later "
            "features don't drift back toward canon. The agent drafts; you own the final bible."
        )
        build_summaries_btn = gr.Button("1. Ensure chapter summaries are built")
        summary_progress = gr.Markdown()

        extract_btn = gr.Button("2. Extract world bible proposal")
        premise_box = gr.Textbox(label="Premise", lines=3)
        rules_table = gr.Dataframe(
            headers=["id", "category", "statement", "diverges_from_canon", "established_chapter", "locked"],
            datatype=["str", "str", "str", "str", "number", "bool"],
            interactive=True, label="Rules (static foundation)",
        )
        facts_table = gr.Dataframe(
            headers=["id", "category", "statement", "established_chapter", "status"],
            datatype=["str", "str", "str", "number", "str"],
            interactive=True, label="Facts ledger",
        )
        deviations_box = gr.Textbox(label="Canon deviations (one per line)", lines=4)
        save_btn = gr.Button("3. Save world bible")
        save_status = gr.Markdown()

        def on_extract(project_name, model, api_key):
            project = require_project(project_name)
            client = require_client(model, api_key)
            proposal = extract_world_bible(project, client)
            rules_rows = [[r["id"], r["category"], r["statement"], r["diverges_from_canon"], r["established_chapter"], r["locked"]] for r in proposal["rules"]]
            facts_rows = [[f["id"], f["category"], f["statement"], f["established_chapter"], f["status"]] for f in proposal["facts"]]
            return proposal["premise"], rules_rows, facts_rows, "\n".join(proposal["canon_deviations"])

        extract_btn.click(on_extract, inputs=[project_picker, model_picker, api_key_box],
                           outputs=[premise_box, rules_table, facts_table, deviations_box])

        def on_build_summaries_real(project_name, model, api_key):
            project = require_project(project_name)
            client = require_client(model, api_key)
            log = []
            for progress in ensure_summaries(project, project.working_epub, client, model):
                log.append(str(progress))
                yield "\n".join(log[-5:])

        build_summaries_btn.click(on_build_summaries_real, inputs=[project_picker, model_picker, api_key_box],
                                   outputs=summary_progress)

        def on_save(project_name, premise, rules_rows, facts_rows, deviations_text):
            project = require_project(project_name)
            data = {
                "premise": premise,
                "rules": [
                    {"id": r[0], "category": r[1], "statement": r[2], "diverges_from_canon": r[3],
                     "established_chapter": int(r[4]) if r[4] is not None else 1, "locked": bool(r[5])}
                    for r in rules_rows
                ],
                "facts": [
                    {"id": f[0], "category": f[1], "statement": f[2],
                     "established_chapter": int(f[3]) if f[3] is not None else 1,
                     "status": f[4] or "current", "supersedes": None}
                    for f in facts_rows
                ],
                "canon_deviations": [line for line in deviations_text.splitlines() if line.strip()],
            }
            save_reviewed_world_bible(project, data)
            return "World bible saved."

        save_btn.click(on_save, inputs=[project_picker, premise_box, rules_table, facts_table, deviations_box],
                        outputs=save_status)
