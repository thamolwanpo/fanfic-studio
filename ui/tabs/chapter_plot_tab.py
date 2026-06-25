"""UI tab for Feature 3: chapter-by-chapter plot + character arcs."""
import json

import gradio as gr

from features.f3_chapter_plot import has_overall_plot, load_existing_outline, run_outline_loop, save_outline
from ui.components import require_project, require_client


def build_chapter_plot_tab(project_picker, model_picker, api_key_box):
    with gr.Tab("3. Chapter Plot & Arcs"):
        gr.Markdown("Requires `plot_overall.txt` (Feature 2) first. Turns the overall plot into a chapter-by-chapter outline and tracks character arcs.")
        precondition_warning = gr.Markdown()
        load_btn = gr.Button("Load existing outline from file")
        outline_box = gr.Textbox(label="Outline JSON ({plot_chapters, character_arcs})", lines=15)

        run_btn = gr.Button("Run outline reflection loop")
        progress_log = gr.Markdown()

        save_btn = gr.Button("Save plot_chapters.json + character_arcs.json")
        save_status = gr.Markdown()

        def on_load(project_name):
            project = require_project(project_name)
            warning = "" if has_overall_plot(project) else "⚠️ plot_overall.txt not found — run Feature 2 first."
            plot_chapters, character_arcs = load_existing_outline(project)
            return warning, json.dumps({"plot_chapters": plot_chapters, "character_arcs": character_arcs}, ensure_ascii=False, indent=2)

        load_btn.click(on_load, inputs=project_picker, outputs=[precondition_warning, outline_box])

        def on_run(project_name, model, api_key):
            project = require_project(project_name)
            if not has_overall_plot(project):
                raise gr.Error("plot_overall.txt is missing. Complete Feature 2 first.")
            client = require_client(model, api_key)
            log = []
            last_text = ""
            for step in run_outline_loop(project, client):
                log.append(str({k: v for k, v in step.items() if k != "text"}))
                last_text = step.get("text", last_text)
                yield "\n".join(log[-6:]), last_text

        run_btn.click(on_run, inputs=[project_picker, model_picker, api_key_box], outputs=[progress_log, outline_box])

        def on_save(project_name, outline_text):
            project = require_project(project_name)
            save_outline(project, outline_text)
            return "Saved plot_chapters.json and character_arcs.json"

        save_btn.click(on_save, inputs=[project_picker, outline_box], outputs=save_status)
