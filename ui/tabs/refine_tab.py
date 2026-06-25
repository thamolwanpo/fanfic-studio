"""UI tab for Feature 1: refine a chapter."""
import gradio as gr

from core.epub_io import read_chapter_text
from features.f1_refine_chapter import (
    run_refine_loop, propose_name_fixes, merge_name_proposal, apply_refinement,
)
from ui.components import require_project, require_client


def build_refine_tab(project_picker, model_picker, api_key_box):
    with gr.Tab("1. Refine Chapter"):
        gr.Markdown("Polish translation, fill small gaps, fix dialogue formatting, and apply consistent character names — one chapter at a time.")
        chapter_n = gr.Number(label="Chapter number", precision=0, value=1)
        load_btn = gr.Button("Load raw chapter")
        raw_box = gr.Textbox(label="Raw chapter text", lines=10)

        refine_btn = gr.Button("Run refine reflection loop")
        progress_log = gr.Markdown()
        draft_box = gr.Textbox(label="Refined draft (editable before applying)", lines=15)

        names_btn = gr.Button("Propose name fixes")
        names_table = gr.Dataframe(
            headers=["alias", "canonical"], datatype=["str", "str"], interactive=True,
            label="Proposed canonical name additions (edit/delete before confirming)",
        )
        confirm_names_btn = gr.Button("Confirm name additions")
        names_status = gr.Markdown()

        apply_btn = gr.Button("Apply refinement + names to working.epub")
        apply_status = gr.Markdown()

        def on_load(project_name, n):
            project = require_project(project_name)
            title, text, _html = read_chapter_text(project.working_epub, project, int(n))
            return text

        load_btn.click(on_load, inputs=[project_picker, chapter_n], outputs=raw_box)

        def on_refine(project_name, model, api_key, n):
            project = require_project(project_name)
            client = require_client(model, api_key)
            log = []
            last_text = ""
            for step in run_refine_loop(project, client, project.working_epub, int(n)):
                log.append(str({k: v for k, v in step.items() if k != "text"}))
                last_text = step.get("text", last_text)
                yield "\n".join(log[-6:]), last_text

        refine_btn.click(on_refine, inputs=[project_picker, model_picker, api_key_box, chapter_n],
                          outputs=[progress_log, draft_box])

        def on_propose_names(project_name, model, api_key, n):
            project = require_project(project_name)
            client = require_client(model, api_key)
            proposal = propose_name_fixes(project, client, project.working_epub, int(n))
            rows = [[alias, canon] for alias, canon in proposal.get("canonical_names", {}).items()]
            return rows

        names_btn.click(on_propose_names, inputs=[project_picker, model_picker, api_key_box, chapter_n], outputs=names_table)

        def on_confirm_names(project_name, rows):
            project = require_project(project_name)
            proposal = {"canonical_names": {r[0]: r[1] for r in rows if r[0] and r[1]}, "au_canon_swaps": []}
            merge_name_proposal(project, proposal)
            return "Name canon updated."

        confirm_names_btn.click(on_confirm_names, inputs=[project_picker, names_table], outputs=names_status)

        def on_apply(project_name, n, draft_text):
            project = require_project(project_name)
            title, _text, _html = read_chapter_text(project.working_epub, project, int(n))
            apply_refinement(project.working_epub, project, int(n), title, draft_text)
            return f"Chapter {int(n)} refined and saved to working.epub."

        apply_btn.click(on_apply, inputs=[project_picker, chapter_n, draft_box], outputs=apply_status)
