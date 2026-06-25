# Fanfic Refiner & Continuation Studio

A local **Gradio** app for working with a long, multi-chapter AO3 fanfiction that was machine-translated from Chinese (and is incomplete). It lets you: clean up and refine existing chapters, lock down inconsistent character names, study the original author's style, plan the rest of the story, and draft new chapters — all powered by an LLM API you supply a key for.

This document is the **spec the repository is built from**. It defines the folder structure, the shared data model, the per-feature pipelines, and the conventions every module follows. Read this before writing any code.

---

## 1. Design principles

1. **The original is sacred.** `source.epub` is read-only after import. All changes go to a separate `working.epub`. You can always re-derive everything from the source.
2. **State lives on disk, not in memory.** The user can close the app mid-project and resume. Every feature reads and writes shared files in a project folder (see §3). Gradio session state holds only the *current project path* and transient UI values.
3. **The LLM proposes; the human disposes.** Anything risky and irreversible — especially renaming characters — is generated as a *proposal* that the user reviews and edits before it is applied deterministically.
4. **"Multi-agent" = a role pipeline, not magic.** Each feature uses the simplest pattern that produces good output (see §5). Most are a **draft → critique → revise reflection loop** with a hard iteration cap plus a human "good enough" gate. We do not run parallel autonomous agents.
5. **Long text is handled by summarize-then-reason.** No feature assumes the whole fic fits in one context window. A per-chapter summary cache (§4.3) is the backbone of every "read the whole thing" feature.
6. **Model-agnostic.** The user picks a model and pastes an API key in the UI. All LLM calls go through one adapter (§6) so swapping providers/models never touches feature code.

---

## 2. Tech stack

| Concern | Choice | Notes |
|---|---|---|
| UI | **Gradio** | Native support for streaming generator output, chat components for refine-until-satisfied loops, file upload/download. |
| EPUB I/O | `ebooklib` + `BeautifulSoup4` + `lxml` | Parse, edit, and rewrite EPUB chapter XHTML. |
| LLM calls | `openai` SDK (OpenAI-compatible base URL) | One adapter; supports OpenAI + any compatible endpoint. Key/model passed at call time. |
| Data files | plain `json` / `txt` | Human-readable so the user can hand-edit. |
| Concurrency | Python `threading` + Gradio generators | Long jobs `yield` progress; UI stays responsive. |
| Config/secrets | in-memory only; never written to disk | API key is held for the session, not persisted. |

> If you do not already know Gradio: the key idea is that a function can `yield` multiple times to stream partial results into the UI. We use that for "show me each agent step as it happens."

---

## 3. Repository layout

```
fanfic-studio/
├── README.md                  # this document
├── requirements.txt
├── app.py                     # Gradio entrypoint: builds tabs, wires callbacks
│
├── core/                      # shared, feature-independent layer
│   ├── __init__.py
│   ├── project.py             # Project class: create/load/save, path resolution
│   ├── epub_io.py             # spine inspector + resolved chapter↔spine map; read/replace/append/export
│   ├── state.py               # state.json read/write (current chapter, refined set, etc.)
│   ├── characters.py          # characters.json model + deterministic name application
│   ├── worldbuilding.py       # world_bible.json model: rules + evolving facts ledger
│   ├── summaries.py           # chapter summary cache build/read (§4.3)
│   └── files.py               # safe read/write for plot/style txt + json outputs
│
├── llm/
│   ├── __init__.py
│   ├── client.py              # LLMClient adapter (OpenAI only): one call() method, model+key injected
│   ├── models.py              # model registry + per-model context-token limits (UI dropdown source)
│   └── pipelines.py           # reflection_loop(), map_reduce_summarize(), chunk_text(), build_context()
│
├── features/                  # one module per UI tab; each owns its agent prompts
│   ├── __init__.py
│   ├── f0_world_bible.py      # Feature 0: extract + maintain AU world bible
│   ├── f1_refine_chapter.py   # Feature 1: refine/fill-gaps + name fixing for one chapter
│   ├── f2_overall_plot.py     # Feature 2: read whole fic -> propose ending plot
│   ├── f3_chapter_plot.py     # Feature 3: chapter-by-chapter plot + character arcs
│   ├── f4_style_guide.py      # Feature 4: analyze author style -> reusable style guide
│   └── f5_write_chapter.py    # Feature 5: draft next chapter using all artifacts
│
├── prompts/                   # prompt templates kept out of code for easy tuning
│   ├── f1_*.txt
│   ├── f2_*.txt
│   ├── f3_*.txt
│   ├── f4_*.txt
│   └── f5_*.txt
│
├── ui/
│   ├── __init__.py
│   ├── components.py          # shared widgets: model picker, API key box, project picker
│   └── tabs/                  # one builder function per tab, imported by app.py
│       ├── world_bible_tab.py
│       ├── refine_tab.py
│       ├── overall_plot_tab.py
│       ├── chapter_plot_tab.py
│       ├── style_tab.py
│       └── write_tab.py
│
└── projects/                  # created at runtime; one subfolder per imported fic
    └── <project-name>/
        ├── source.epub                 # READ-ONLY original
        ├── working.epub                 # mutable; chapters replaced/appended here
        ├── characters.json              # name canon map + AU/canon swaps + arcs
        ├── world_bible.json             # AU rules (static) + evolving facts ledger
        ├── summaries.json               # per-chapter summary cache (§4.3)
        ├── plot_overall.txt             # Feature 2 output
        ├── plot_chapters.json           # Feature 3 output (chapter-by-chapter)
        ├── character_arcs.json          # Feature 3 output (development tracking)
        ├── style_guide.txt              # Feature 4 output
        └── state.json                   # pointers + progress flags
```

---

## 4. Shared data model

These files are the contract between features. Every feature reads what it needs and writes its own outputs; nothing is passed feature-to-feature except through disk.

### 4.1 `state.json`
Tracks progress so the user can resume after closing the app.
```json
{
  "project_name": "my-fic",
  "source_chapter_count": 42,
  "current_write_chapter": 43,
  "refined_chapters": [1, 2, 5],
  "artifacts": {
    "world_bible": true,
    "plot_overall": true,
    "plot_chapters": false,
    "style_guide": true,
    "summaries_built_through": 42
  },
  "last_modified": "ISO-8601"
}
```

### 4.2 `characters.json`
The heart of Feature 1 and the trickiest data in the project. Three concerns are kept separate and explicit.
```json
{
  "canonical_names": {
    "晓明": "Xiaoming",
    "Xiao Ming": "Xiaoming",
    "X. Ming": "Xiaoming"
  },
  "au_canon_swaps": [
    {
      "au_name": "Mentor Lin",
      "replaced_by_canon": "Dumbledore",
      "effective_from_chapter": 12,
      "note": "Canon character takes over the AU mentor role; use new name from ch.12 on."
    }
  ],
  "arcs": {
    "Xiaoming": {
      "role": "OC protagonist",
      "summary": "...",
      "beats": []
    }
  }
}
```
- `canonical_names` is a **flat alias → canonical** map. Applied as deterministic find/replace during refinement.
- `au_canon_swaps` handles your "a canon character replaces an AU one but the old name lingers" case. Chapter-scoped so it only kicks in from the right point.
- `arcs` is shared with Feature 3 (it writes the richer version to `character_arcs.json`, but a lightweight copy lives here too).

**Critical rule:** the LLM only ever *proposes* additions/edits to `canonical_names` and `au_canon_swaps`. The UI shows them as an editable table; application to text is a deterministic pass the user triggers. The model never silently renames.

### 4.3 `world_bible.json`
Captures the **alternate universe** the story takes place in — the single most important thing that separates this fic from canon. Without it, the planning and writing features (F2/F3/F5) drift back toward canon assumptions. It is **agent-extracted from the fic, then user-reviewed/edited**, and has two layers: fixed **rules** set early, and an evolving **facts ledger** that grows as new chapters are written.
```json
{
  "premise": "One-paragraph statement of how this AU diverges from canon.",
  "rules": [
    {
      "id": "r1",
      "category": "magic-system",
      "statement": "Magic here is powered by written contracts, not wands.",
      "diverges_from_canon": "Canon uses wand-channeled magic.",
      "established_chapter": 1,
      "locked": true
    }
  ],
  "facts": [
    {
      "id": "f1",
      "category": "geography",
      "statement": "The Northern Academy was destroyed in the war.",
      "established_chapter": 8,
      "status": "current",
      "supersedes": null
    }
  ],
  "canon_deviations": [
    "Bullet list of notable departures from source canon for quick reference."
  ]
}
```
- **`rules`** = the static foundation (magic system, world laws, AU premise). Set once, marked `locked`; changing a locked rule warns the user since downstream chapters may depend on it.
- **`facts`** = the evolving ledger. New chapters (F5) can **add** facts or **supersede** old ones (`status: "current" | "superseded"`, with `supersedes` pointing at the replaced fact's id). This is how the world bible "grows as the story continues" without rewriting history — superseded facts stay for traceability.
- **`canon_deviations`** is a flat quick-reference the writing prompts lean on so the model doesn't snap back to canon.

**Population & review:** an extraction agent reads the summaries (and key chapters) and proposes the initial `premise`, `rules`, and `facts`. The UI presents them in an **editable review panel**; the user confirms, edits, deletes, or adds before anything is saved. Same human-approval principle as `characters.json` — the agent drafts, the user owns the final bible.

**Consumed by:** F2, F3, and F5 inject the world bible into their context so plot, outline, and prose all respect the AU. F5 may *propose* new facts when it writes a chapter; those go through the same review gate before being committed.

### 4.4 `summaries.json` (the backbone)
A cache so the expensive "read everything" step happens once and is reused by Features 2, 3, and 5.
```json
{
  "built_through_chapter": 42,
  "model_used": "gpt-5.1",
  "chapters": [
    { "n": 1, "title": "...", "summary": "...", "characters_present": ["Xiaoming"], "open_threads": ["..."] }
  ]
}
```
Built incrementally; if new chapters are appended, only the new ones are summarized.

### 4.5 Output text/JSON files
- `plot_overall.txt` — prose plot for the remainder of the story (Feature 2).
- `plot_chapters.json` — `[{ "chapter": 43, "goal": "...", "beats": [...], "arcs_advanced": [...] }]` (Feature 3).
- `character_arcs.json` — per-character development tracking (Feature 3).
- `style_guide.txt` — instructions for the model to imitate the author (Feature 4).

---

## 5. LLM pipeline patterns

Defined once in `llm/pipelines.py`, reused everywhere. Each task picks the pattern that fits. **Every pattern below uses separate API calls with fresh context — roles never accumulate into one prompt — and all payloads pass through the context budgeter (§5.4) so nothing exceeds the model's limit.**

### 5.1 `reflection_loop(draft_fn, critique_fn, revise_fn, max_iters, user_gate)`
The default for generative tasks. Three **separate** calls per iteration (each gets only the context it needs, not the accumulated history):
1. **Draft** — produce a first version. For long inputs, drafts per chunk (§5.3) with a rolling story-so-far summary rather than the full prior text.
2. **Critique** — a fresh call evaluates the draft against explicit criteria (AU/world consistency, name canon, author intent, style match, dialogue-on-new-line) and returns a **small structured list of targeted fixes** — not a rewrite. Keeps the critique output tiny and the revise step cheap and precise. Operates per scene/chunk for long chapters, not whole-chapter.
3. **Revise** — applies the fix list to the relevant spans.

Loops until either `max_iters` (e.g. 3) is hit **or** the user accepts. The function is a Python generator that `yield`s each step so the UI streams progress, including a running count toward `max_iters`. The user-satisfaction gate is a UI pause: the loop surfaces the result and waits for "accept" or new feedback. The structured fix list dovetails with F5's line-range editor (§7.1).

### 5.2 `map_reduce_summarize(chapters, model)`
For "read the whole fic." **Map:** summarize each chapter independently (parallelizable). **Reduce:** feed the chapter summaries (not full text) into a planning prompt. This is what keeps long fics inside context limits and powers Features 2, 3, 5.

### 5.3 Chunking (`chunk_text`, decided once here)
Very long chapters are split into scene-sized chunks with a fixed **overlap** so context isn't lost at boundaries. Chunk size and overlap are a **single decision made in `pipelines.py`** and reused everywhere — features never re-invent chunking. Draft, critique, and revise all operate at chunk granularity for long inputs; a compact rolling summary carries cross-chunk continuity instead of re-sending full text.

### 5.4 Context budgeter (`build_context`)
One function decides, per call, how the model's token limit is divided between the primary text (chapter/draft/chunk) and the supporting context (world bible → name canon → style guide → recent summaries). When everything won't fit, it trims **least-critical first** (oldest summaries before the world bible's locked rules). Features never assemble raw context themselves — they ask the budgeter, so no single call can blow the limit. Provider is OpenAI-only, so the limit lookup lives in `llm/models.py` per model.

### 5.5 When each feature uses what
| Feature | Pattern | Why |
|---|---|---|
| F1 refine chapter | reflection_loop on one chapter + deterministic name pass | Quality + safe renaming |
| F2 overall plot | map_reduce_summarize → reflection_loop, looped with user choices | Whole-fic comprehension + iterative planning (world bible in context) |
| F3 chapter plot | reduce over summaries + plot_overall → reflection_loop | Structured planning, feedback-driven (world bible in context) |
| F4 style guide | map a sample of chapters → reduce into one guide | Style is global, not per-chapter |
| F5 write chapter | assemble all artifacts → reflection_loop, user-gated | Highest-context generative task (world bible enforced) |

---

## 6. LLM adapter (`llm/client.py`)

A single class so feature code never touches provider details.

```
LLMClient(model: str, api_key: str)        # OpenAI only
  .call(system: str, messages: list, *, temperature=..., json_mode=False) -> str
  .stream(...) -> Iterator[str]      # for live token display where useful
```
- **Provider: OpenAI only.** The adapter targets OpenAI's API; no multi-provider abstraction needed.
- Model list comes from `llm/models.py` and populates the UI dropdown (e.g. `gpt-5.1`, plus any others you add). Each registry entry carries the model's **context-token limit**, which the budgeter (§5.4) reads. Adding a model = one registry entry, no feature changes.
- The API key is read from the UI field, held in session memory, and **never written to disk or logged**.
- All retry/timeout/error handling lives here; features get clean strings or a typed error.

---

## 7. Feature specifications

Each feature is one Gradio tab. Shared header on every tab: **project picker**, **model dropdown**, **API key field**.

### Feature 0 — World bible builder (`f0_world_bible.py`)
**Goal:** extract and maintain the AU's rules and an evolving facts ledger (§4.3), so every downstream feature respects the alternate universe instead of canon.

**Flow:**
1. Ensure summaries exist (or read key chapters directly).
2. Extraction agent proposes `premise`, `rules` (static foundation), `facts`, and a `canon_deviations` quick list.
3. UI shows an **editable review panel** (separate tables for rules and facts): user confirms, edits, deletes, adds, and marks rules `locked`.
4. Save to `world_bible.json`; downloadable.
5. Maintenance mode: when F5 proposes new facts (or supersedes old ones), they surface here for review before commit. Editing a `locked` rule warns the user that downstream chapters may depend on it.

This is best built right after the summaries cache, since F2/F3/F5 all consume it. Agent drafts, user owns the final bible — same principle as the name canon.

### Feature 1 — Refine a chapter (`f1_refine_chapter.py`)
**Goal:** polish translation, fill small gaps, fix dialogue formatting, and apply consistent character names — one chapter at a time.

**Flow:**
1. User selects a chapter number to process.
2. Build/refresh that chapter's entry in `summaries.json` (context for the agents).
3. Run `reflection_loop`: draft refined prose → critique for translation fidelity, gap-filling that respects author intent, and **dialogue on its own new line per speaker** → revise.
4. In parallel, a name-analysis prompt **proposes** additions to `canonical_names` / `au_canon_swaps`. UI shows them in an **editable table**; user confirms.
5. Deterministic pass applies the confirmed name map (and any chapter-scoped AU/canon swaps that are in effect from this chapter onward).
6. The refined chapter **replaces** the corresponding chapter in `working.epub`.
7. User downloads the updated `working.epub`. `state.refined_chapters` is updated.

**Key requirements baked in:**
- Dialogue formatting: every spoken line starts a new paragraph.
- Names: first appearance wins as canonical unless the user overrides; AU/canon swaps take effect from a chapter boundary.
- Long chapters: chunk within the chapter if needed, but keep the reflection loop coherent across chunks.

### Feature 2 — Propose the overall ending plot (`f2_overall_plot.py`)
**Goal:** read the entire (unfinished) fic and help the user decide how the story should end, honoring the original author's intent.

**Flow:**
1. Ensure `summaries.json` is built for all chapters (`map_reduce_summarize`).
2. Planning agent proposes **several distinct directions** the plot could go, grounded in open threads, the AU world bible, and inferred author intent.
3. UI presents the options; user picks/blends. A reflection step self-critiques the chosen direction for consistency and intent fidelity.
4. **Loop**: refine and re-present until the user says it's perfect.
5. Output is a **prose plot of the remainder** (not chapter-by-chapter). Saved to `plot_overall.txt`, downloadable as `.txt`.

System framing: the planning agent is prompted as an award-winning novelist who knows story theory.

### Feature 3 — Chapter-by-chapter plot + character arcs (`f3_chapter_plot.py`)
**Goal:** turn the overall plot into a chapter-by-chapter outline and track character development.

**Inputs:** `working.epub` (or summaries), `world_bible.json`, **and** `plot_overall.txt` (required precondition; tab warns if missing).

**Flow:**
1. Reduce over summaries + overall plot into a chapter-by-chapter outline.
2. Reflection loop refines it; user gives feedback until satisfied.
3. Write **two** outputs: `plot_chapters.json` (the outline) and `character_arcs.json` (development tracking). Both are downloadable and **re-loaded and adjusted from file** on subsequent edits.

### Feature 4 — Author style guide (`f4_style_guide.py`)
**Goal:** produce a reusable instruction text so the model writes in the author's voice instead of generic AI style.

**Flow:**
1. Map over a representative sample of chapters (analyze diction, sentence rhythm, pacing, dialogue habits, imagery).
2. Reduce into a single `style_guide.txt` that also includes general fiction-craft reminders the model should apply per chapter.
3. Downloadable; consumed by Feature 5.

### Feature 5 — Write the next chapter (`f5_write_chapter.py`)
**Goal:** draft the next chapter using everything produced so far, then refine with the user and append to the book.

**Inputs:** `working.epub`, `world_bible.json`, `plot_overall.txt`, `plot_chapters.json`, `character_arcs.json`, `style_guide.txt`, `characters.json`, `summaries.json`. Tab indicates which artifacts are present; missing ones degrade gracefully.

**Flow:**
1. Read `state.current_write_chapter` to know what to write next.
2. Assemble context: the relevant entry from `plot_chapters.json`, arcs, style guide, the AU world bible (rules + current facts), recent chapter summaries, name canon.
3. `reflection_loop` drafts the chapter in the author's style with correct names, dialogue formatting, and AU consistency.
4. **Review & adjust the draft (editor-style, see §7.1).** Two tracks the user can mix freely: edit the text directly, and/or give targeted line-range instructions. Submit → a reflection pass produces an adjusted version → user iterates or presses **Done**.
5. On Done, the writing agent may **propose new world facts** (e.g. a place introduced this chapter); these surface in Feature 0's review gate before commit.
6. **Append** the accepted chapter to `working.epub`; increment `state.current_write_chapter`; summarize the new chapter into `summaries.json`.
7. User downloads `working.epub`. Because state is on disk, the user can close the app, reopen the project later, and write the next chapter — the pointer persists.

#### 7.1 Editor-style adjustment (the chapter editor)
Replaces plain chat refinement on the last written chapter with a two-track editor.

- **Track A — direct edit:** the draft lives in an editable text area (`gr.Textbox`/`gr.Code`); the user can hand-edit any line.
- **Track B — targeted instructions:** a small list where the user specifies a **line range** and what to change ("lines 14–18: tighten, make Xiaoming's tone colder"). Both tracks can be used in the same submit.
- **Submit → reflect:** the adjustment agent takes the current text *plus* the user's direct edits *plus* the targeted instructions, applies them, and runs one reflection pass (does it honor the instruction? still consistent with style/world/names?). Returns the adjusted version.
- **Done gate:** user accepts, or iterates again. Accept commits the chapter.

**Gradio feasibility:** the two-track design works fully in plain Gradio (editable textarea + an instructions list keyed by line range) — this is the build target. A nicer line-anchored editor (click a line, attach a note inline) needs a small custom HTML/CodeMirror component embedded via `gr.HTML`; it's an **optional UX upgrade**, not required, and the backend contract is identical either way, so it can be added later without touching feature logic.

---

## 8. Cross-cutting requirements

- **EPUB chapter integrity:** "chapter N" means one thing project-wide. The spine (from the `.opf` manifest), not file order, is the authoritative sequence; AO3 exports include front matter (title/summary/tags/notes) and sometimes endnotes as spine items, so a resolved **chapter↔spine map** is built once at import (after the inspector confirms which spine items are real chapters) and every feature reads chapters through it — never by raw spine index. This is what keeps F5's append/pointer logic from going off-by-N.
- **Resumability:** every feature reads `state.json` on entry and writes it on completion. Closing/reopening the app loses nothing.
- **Dialogue formatting** (each spoken line on its own paragraph) is enforced in F1 refinement and F5 writing.
- **Name integrity** is centralized in `core/characters.py`; no feature does ad-hoc renaming.
- **AU consistency:** the world bible (rules + current facts) is injected into F2/F3/F5 context so planning and prose never drift back to canon. Superseded facts are retained for traceability.
- **Author intent** is an explicit critique criterion in F2/F3/F5 prompts, since the fic is unfinished and we are completing someone else's work.
- **Cost/time visibility:** long jobs stream step-by-step progress; the UI never silently hangs. Reflection loops show a running count toward `max_iters`.
- **Privacy:** API key in memory only; project files stay local under `projects/`.

---

## 9. Build order (suggested milestones)

1. **Core layer** — `project.py`, `epub_io.py`, `state.py`. Start with the **spine inspector** (print each spine item's index/file/title/first ~100 chars), confirm against your real EPUB which items are chapters, build the resolved chapter↔spine map, then a round-trip test (import → replace a chapter → export → re-open in a reader to verify it isn't mangled).
2. **LLM adapter + model picker** — `client.py`, `models.py`; smoke-test one call.
3. **Summaries cache** — `summaries.py` + `map_reduce_summarize`. Everything else depends on it.
4. **Feature 0** (world bible) — `worldbuilding.py` + extraction/review. Built early because F2/F3/F5 consume it.
5. **Feature 1** end to end (refine + name table + replace + download). Highest day-to-day value; exercises the whole stack.
6. **Feature 4** (style guide) — small, feeds F5.
7. **Feature 2 → Feature 3** (overall plot → chapter plot).
8. **Feature 5** (write next chapter + editor-style adjustment) — depends on all of the above; build the plain-Gradio two-track editor first, treat the custom inline editor as an optional later upgrade.

---

## 10. Resolved decisions & remaining notes

**Resolved:**
- **Provider scope:** OpenAI only. No multi-provider abstraction.
- **EPUB chapter detection:** use the spine as authoritative order; build the inspector first, confirm chapter vs. front/back matter against the real file, store a resolved chapter↔spine map all features share (§8, milestone 1).
- **Token limits:** chunk long chapters with fixed size + overlap decided once in `pipelines.py`; all context flows through the budgeter (§5.4); critique returns structured fixes, not rewrites. The three-role loop is unaffected since roles are separate calls, not one accumulating context.

**Still to settle during implementation:**
- Exact chunk size and overlap values — tune against your real chapter lengths and chosen model's limit.
- `max_iters` default for reflection loops (start at 3, adjust by observed quality/cost).
- Sample size for F4 style analysis (how many chapters is "representative" for this fic).