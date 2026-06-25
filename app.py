"""Gradio entrypoint: builds tabs, wires callbacks (README §2 tech stack, §3 layout).

Session state holds only the current project path and transient UI values; everything
else is read/written to disk per project (README design principle #2).
"""
import gradio as gr

from ui.components import shared_header
from ui.tabs.project_tab import build_project_tab
from ui.tabs.world_bible_tab import build_world_bible_tab
from ui.tabs.refine_tab import build_refine_tab
from ui.tabs.overall_plot_tab import build_overall_plot_tab
from ui.tabs.chapter_plot_tab import build_chapter_plot_tab
from ui.tabs.style_tab import build_style_tab
from ui.tabs.write_tab import build_write_tab


def build_app():
    with gr.Blocks(title="Fanfic Refiner & Continuation Studio") as demo:
        gr.Markdown("# Fanfic Refiner & Continuation Studio")
        gr.Markdown(
            "Local Gradio app for refining a machine-translated AO3 fanfiction, locking "
            "character names, studying author style, planning the rest of the story, and "
            "drafting new chapters. Your API key stays in memory for this session only."
        )
        project_picker, model_picker, api_key_box = shared_header()

        build_project_tab()
        build_world_bible_tab(project_picker, model_picker, api_key_box)
        build_refine_tab(project_picker, model_picker, api_key_box)
        build_overall_plot_tab(project_picker, model_picker, api_key_box)
        build_chapter_plot_tab(project_picker, model_picker, api_key_box)
        build_style_tab(project_picker, model_picker, api_key_box)
        build_write_tab(project_picker, model_picker, api_key_box)

    return demo


if __name__ == "__main__":
    app = build_app()
    app.launch()
