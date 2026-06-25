"""UI tab for Feature 5: write the next chapter, with the two-track editor-style
adjustment (README §7.1): Track A direct text edits, Track B line-range instructions."""
import gradio as gr

from features.f5_write_chapter import (
    present_artifact_status, run_write_loop, apply_editor_adjustment, commit_chapter,
)
from features.f0_world_bible import commit_new_facts
from ui.components import require_project, require_client


def build_write_tab(project_picker, model_picker, api_key_box):
    with gr.Tab("5. Write Next Chapter"):
        status_btn = gr.Button("Check artifact status")
        status_box = gr.Markdown()

        draft_btn = gr.Button("Draft next chapter (reflection loop)")
        progress_log = gr.Markdown()

        gr.Markdown("### Editor — Track A: direct edits, Track B: targeted line-range instructions")
        editor_box = gr.Textbox(label="Chapter text (hand-edit directly here)", lines=20)
        instructions_table = gr.Dataframe(
            headers=["start_line", "end_line", "instruction"], datatype=["number", "number", "str"],
            type="array", interactive=True, label="Targeted instructions",
        )
        adjust_btn = gr.Button("Submit -> reflect adjustment")
        adjust_status = gr.Markdown()

        done_btn = gr.Button("Done — append to working.epub")
        done_status = gr.Markdown()
        new_facts_box = gr.Markdown()

        def on_status(project_name):
            project = require_project(project_name)
            return str(present_artifact_status(project))

        status_btn.click(on_status, inputs=project_picker, outputs=status_box)

        def on_draft(project_name, model, api_key):
            project = require_project(project_name)
            client = require_client(model, api_key)
            log = []
            last_text = ""
            for step in run_write_loop(project, client):
                log.append(str({k: v for k, v in step.items() if k != "text"}))
                last_text = step.get("text", last_text)
                yield "\n".join(log[-6:]), last_text

        draft_btn.click(on_draft, inputs=[project_picker, model_picker, api_key_box],
                         outputs=[progress_log, editor_box])

        def on_adjust(project_name, model, api_key, current_text, rows):
            project = require_project(project_name)
            client = require_client(model, api_key)
            instructions = [
                {"start": int(r[0]), "end": int(r[1]), "instruction": r[2]}
                for r in rows if r[2]
            ]
            adjusted = apply_editor_adjustment(project, client, current_text, instructions)
            return adjusted, "Adjustment applied. Review and iterate, or press Done."

        adjust_btn.click(on_adjust, inputs=[project_picker, model_picker, api_key_box, editor_box, instructions_table],
                          outputs=[editor_box, adjust_status])

        def on_done(project_name, model, api_key, final_text):
            project = require_project(project_name)
            client = require_client(model, api_key)
            chapter_n, proposed_facts = commit_chapter(project.working_epub, project, client, final_text, model)
            facts_note = ""
            if proposed_facts:
                commit_new_facts(project, proposed_facts)
                facts_note = f"Proposed/committed {len(proposed_facts)} new world fact(s) — review in the World Bible tab."
            return f"Chapter {chapter_n} appended to working.epub.", facts_note

        done_btn.click(on_done, inputs=[project_picker, model_picker, api_key_box, editor_box],
                        outputs=[done_status, new_facts_box])
