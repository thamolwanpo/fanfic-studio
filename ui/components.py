"""Shared widgets used at the top of every tab: project picker, model dropdown, API key
field (README §7: 'Shared header on every tab')."""
import gradio as gr

from core.project import list_projects
from llm.models import model_choices, DEFAULT_MODEL


def shared_header():
    with gr.Row():
        project_picker = gr.Dropdown(
            label="Project", choices=list_projects(), value=None, interactive=True,
        )
        refresh_btn = gr.Button("Refresh", scale=0)
        model_picker = gr.Dropdown(
            label="Model", choices=model_choices(), value=DEFAULT_MODEL, interactive=True,
        )
        api_key_box = gr.Textbox(
            label="API key", type="password", placeholder="sk-...", interactive=True,
        )
    refresh_btn.click(lambda: gr.update(choices=list_projects()), outputs=project_picker)
    return project_picker, model_picker, api_key_box


def require_project(project_name):
    if not project_name:
        raise gr.Error("Select or create a project first.")
    from core.project import Project
    return Project.load(project_name)


def require_client(model, api_key):
    if not api_key:
        raise gr.Error("Enter an API key first.")
    from llm.client import LLMClient
    return LLMClient(model=model, api_key=api_key)
