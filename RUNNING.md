# Running Fanfic Studio

## 1. Requirements

- Python 3.10+
- An OpenAI API key (the app is OpenAI-only; you paste the key into the UI each session — it is never written to disk)
- An AO3 EPUB export of the fic you want to work on

## 2. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Start the app

```bash
python3 app.py
```

Gradio prints a local URL (default `http://127.0.0.1:7860`). Open it in a browser.

## 4. First-time project setup

1. Go to the **Project** tab.
2. Enter a project name and upload your `.epub` file, then click **Create project**.
3. Review the spine table that appears — each row is one spine item from the EPUB. AO3
   exports often include front matter (title page, summary, notes) or endnotes as spine
   items, so the `likely_chapter` column is a guess. Edit it (check/uncheck) until it
   matches reality: checked rows become "Chapter 1, 2, 3…" in order.
4. Click **Confirm chapter list & build chapter map**. This writes `chapter_map.json` and
   `source_chapter_count` to that project — every other feature reads chapters through this
   map, not raw spine order.
5. Click **Refresh** next to the project dropdown in the page header, then select your new
   project there. Pick a **model** and paste your **API key** in the header — both fields
   are shared across every tab.

Your project now lives under `projects/<project-name>/`:
- `source.epub` — untouched original
- `working.epub` — copy that every feature edits
- everything else (`state.json`, `characters.json`, etc.) is created as you use each tab

## 5. Suggested order of use

This mirrors the build order in the README and the dependency chain between features:

1. **0. World Bible** — click "Ensure chapter summaries are built" first (this populates
   `summaries.json`, which every later feature reuses), then "Extract world bible proposal",
   review/edit the rules and facts tables, then save.
2. **1. Refine Chapter** — pick a chapter number, load it, run the refine loop, propose/
   confirm name fixes, then apply. Repeat per chapter as needed.
3. **4. Style Guide** — quick, and feeds Feature 5 later.
4. **2. Overall Plot** — propose directions, pick/blend one, run the reflection loop, save.
5. **3. Chapter Plot & Arcs** — requires `plot_overall.txt` from step 4 to exist first.
6. **5. Write Next Chapter** — needs the artifacts above (degrades gracefully if some are
   missing). Draft, then use the Track A/B editor to adjust, then **Done** to append the
   chapter to `working.epub` and advance the pointer.

## 6. Resuming later

Everything lives on disk under `projects/<name>/`. Closing the app and reopening it,
re-selecting the same project from the header dropdown, picks up exactly where you left
off — `state.json` tracks the write pointer, refined chapters, and which artifacts exist.

## 7. Downloading your work

`working.epub` inside the project folder is the file to grab once you're happy with it —
copy it out of `projects/<name>/` (there's no in-UI download button yet; this is a natural
follow-up if you want one added).

## Troubleshooting

- **"Select or create a project first."** — pick a project in the header dropdown (click
  Refresh if you just created one).
- **"Enter an API key first."** — the key field in the header is required for any LLM call;
  it's per-session only and resets when you restart the app.
- **Feature 3 warns `plot_overall.txt` is missing** — run Feature 2 and save its output first.
- **Spine table looks wrong after import** — re-check the `likely_chapter` checkboxes and
  re-click confirm; it's safe to re-run as long as you haven't started refining chapters yet.
