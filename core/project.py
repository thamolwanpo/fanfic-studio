"""Project class: create/load projects and resolve paths to the files defined in the README's
shared data model (state.json, characters.json, world_bible.json, etc.)."""
import os
import shutil

PROJECTS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "projects")


def list_projects():
    if not os.path.isdir(PROJECTS_ROOT):
        return []
    return sorted(
        name for name in os.listdir(PROJECTS_ROOT)
        if os.path.isdir(os.path.join(PROJECTS_ROOT, name))
    )


class Project:
    def __init__(self, name):
        self.name = name
        self.dir = os.path.join(PROJECTS_ROOT, name)

    @classmethod
    def create(cls, name, source_epub_path):
        proj = cls(name)
        if os.path.exists(proj.dir):
            raise ValueError(f"Project '{name}' already exists.")
        os.makedirs(proj.dir, exist_ok=True)
        shutil.copyfile(source_epub_path, proj.source_epub)
        shutil.copyfile(source_epub_path, proj.working_epub)
        return proj

    @classmethod
    def load(cls, name):
        proj = cls(name)
        if not os.path.isdir(proj.dir):
            raise ValueError(f"Project '{name}' does not exist.")
        return proj

    def exists(self):
        return os.path.isdir(self.dir)

    def path(self, filename):
        return os.path.join(self.dir, filename)

    @property
    def source_epub(self):
        return self.path("source.epub")

    @property
    def working_epub(self):
        return self.path("working.epub")

    @property
    def characters_json(self):
        return self.path("characters.json")

    @property
    def world_bible_json(self):
        return self.path("world_bible.json")

    @property
    def summaries_json(self):
        return self.path("summaries.json")

    @property
    def plot_overall_txt(self):
        return self.path("plot_overall.txt")

    @property
    def plot_chapters_json(self):
        return self.path("plot_chapters.json")

    @property
    def character_arcs_json(self):
        return self.path("character_arcs.json")

    @property
    def style_guide_txt(self):
        return self.path("style_guide.txt")

    @property
    def state_json(self):
        return self.path("state.json")

    @property
    def chapter_map_json(self):
        return self.path("chapter_map.json")
