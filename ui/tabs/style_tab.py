"""UI tab for Feature 4: author style guide."""
import gradio as gr

from features.f4_style_guide import run_style_analysis, save_style_guide
from ui.components import require_project, require_client


def build_style_tab(project_picker, model_picker, api_key_box):
    with gr.Tab("4. Style Guide"):
        gr.Markdown("Analyze a sample of chapters and produce a reusable instruction text so the model writes in the author's voice.")
        sample_size = gr.Number(label="Sample size (chapters)", value=5, precision=0)
        run_btn = gr.Button("Run style analysis (map -> reduce)")
        progress_log = gr.Markdown()
        guide_box = gr.Textbox(label="Style guide draft", lines=15)

        save_btn = gr.Button("Save as style_guide.txt")
        save_status = gr.Markdown()

        def on_run(project_name, model, api_key, sample_n):
            project = require_project(project_name)
            client = require_client(model, api_key)
            log = []
            last_result = ""
            for step in run_style_analysis(project, client, project.working_epub, int(sample_n)):
                log.append(str({k: v for k, v in step.items() if k != "result"}))
                if step.get("step") == "done":
                    last_result = step.get("result", "")
                yield "\n".join(log[-6:]), last_result

        run_btn.click(on_run, inputs=[project_picker, model_picker, api_key_box, sample_size],
                       outputs=[progress_log, guide_box])

        def on_save(project_name, guide_text):
            project = require_project(project_name)
            save_style_guide(project, guide_text)
            return "Saved style_guide.txt"

        save_btn.click(on_save, inputs=[project_picker, guide_box], outputs=save_status)
