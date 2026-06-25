"""Project tab: import a source EPUB, run the spine inspector, confirm which spine items
are real chapters, and build the resolved chapter<->spine map (README §8, milestone 1).
This is the prerequisite step before any feature tab can be used.
"""
import gradio as gr

from core.epub_io import inspect_spine, build_chapter_map, save_chapter_map
from core.project import Project, list_projects
from core.state import save_state, load_state


def build_project_tab():
    with gr.Tab("Project"):
        gr.Markdown(
            "Import an AO3 EPUB to create a new project, or just pick an existing one from "
            "the header above. `source.epub` stays read-only; all edits happen in `working.epub`."
        )
        with gr.Row():
            new_name = gr.Textbox(label="New project name")
            upload = gr.File(label="Source EPUB", file_types=[".epub"])
            create_btn = gr.Button("Create project")

        spine_state = gr.State([])
        create_status = gr.Markdown()
        spine_table = gr.Dataframe(
            headers=["spine_index", "file_name", "title_guess", "preview", "likely_chapter"],
            datatype=["number", "str", "str", "str", "bool"],
            interactive=True,
            label="Spine items — edit 'likely_chapter' to correct misclassified front/back matter",
        )
        confirm_btn = gr.Button("Confirm chapter list & build chapter map")
        confirm_status = gr.Markdown()
        project_refresh_note = gr.Markdown(
            "After confirming, refresh the project dropdown in the header to select this project."
        )

        def on_create(name, file):
            if not name or not file:
                raise gr.Error("Provide both a project name and a source EPUB file.")
            project = Project.create(name, file.name if hasattr(file, "name") else file)
            spine_items = inspect_spine(project.source_epub)
            rows = [[s["spine_index"], s["file_name"], s["title_guess"], s["preview"], s["likely_chapter"]] for s in spine_items]
            return f"Created project '{name}'. Review the spine below.", rows, spine_items

        create_btn.click(on_create, inputs=[new_name, upload], outputs=[create_status, spine_table, spine_state])

        def on_confirm(name, table_rows):
            if not name:
                raise gr.Error("No project name to confirm against.")
            project = Project.load(name)
            chapter_spine_indices = [
                int(row[0]) for row in table_rows if bool(row[4])
            ]
            chapter_spine_indices.sort()
            chapter_map = build_chapter_map(project.source_epub, chapter_spine_indices)
            save_chapter_map(project, chapter_map)
            state = load_state(project)
            state["source_chapter_count"] = len(chapter_map)
            state["current_write_chapter"] = len(chapter_map) + 1
            save_state(project, state)
            return f"Chapter map built: {len(chapter_map)} chapters confirmed for '{name}'."

        confirm_btn.click(on_confirm, inputs=[new_name, spine_table], outputs=confirm_status)
