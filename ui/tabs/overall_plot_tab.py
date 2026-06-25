"""UI tab for Feature 2: propose the overall ending plot."""
import gradio as gr

from features.f2_overall_plot import propose_directions, run_plot_loop, save_overall_plot
from ui.components import require_project, require_client


def build_overall_plot_tab(project_picker, model_picker, api_key_box):
    with gr.Tab("2. Overall Plot"):
        gr.Markdown("Read the whole fic and propose distinct directions for how it could end, honoring the original author's intent.")
        propose_btn = gr.Button("Propose directions")
        directions_box = gr.Textbox(label="Proposed directions (JSON)", lines=10, interactive=False)
        chosen_box = gr.Textbox(label="Your chosen/blended direction (edit freely)", lines=6)

        refine_btn = gr.Button("Run plot reflection loop")
        progress_log = gr.Markdown()
        plot_box = gr.Textbox(label="Plot draft for the remainder of the story", lines=15)

        save_btn = gr.Button("Save as plot_overall.txt")
        save_status = gr.Markdown()

        def on_propose(project_name, model, api_key):
            project = require_project(project_name)
            client = require_client(model, api_key)
            import json
            directions = propose_directions(project, client)
            return json.dumps(directions, ensure_ascii=False, indent=2)

        propose_btn.click(on_propose, inputs=[project_picker, model_picker, api_key_box], outputs=directions_box)

        def on_refine(project_name, model, api_key, chosen_text):
            project = require_project(project_name)
            client = require_client(model, api_key)
            log = []
            last_text = chosen_text
            for step in run_plot_loop(project, client, chosen_text):
                log.append(str({k: v for k, v in step.items() if k != "text"}))
                last_text = step.get("text", last_text)
                yield "\n".join(log[-6:]), last_text

        refine_btn.click(on_refine, inputs=[project_picker, model_picker, api_key_box, chosen_box],
                          outputs=[progress_log, plot_box])

        def on_save(project_name, plot_text):
            project = require_project(project_name)
            save_overall_plot(project, plot_text)
            return "Saved plot_overall.txt"

        save_btn.click(on_save, inputs=[project_picker, plot_box], outputs=save_status)
