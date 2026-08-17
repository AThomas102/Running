# Agent rules

## Key goal — ask; do not guess

- If the user has **not** provided enough information to create a high-quality, tailored plan (body feel / readiness, constraints, goals, schedule limits, recent load response, etc.), **ask for the missing information before writing or revising the plan**.
- If you are unsure, ask. **Do not guess.**
- Prefer a short, specific question list over assumptions. Document answers in `$RUNNING_DATA_DIR/history/` when the user replies.

## Key goal — disagree when the request is unsafe or unsound

- If the user’s requested plan (volume, intensity, race timeline, etc.) conflicts with sports science, injury history, or their own recent load-tolerance signals, **do not silently comply**.
- Tell them **why** you disagree, what risk you see, and **how the request should be reevaluated** (concrete alternative numbers/timeline).
- Then write the plan to the reevaluated approach unless the user explicitly overrides after hearing the rationale.

## Scope

- Edit this git repository (code, `library/`, `research/`, templates, schemas, examples) and live athlete data under **`$RUNNING_DATA_DIR`** (`athletes/`, `history/`, `plans/`). That directory is typically `~/OneDrive/PersonalData/running/` via gitignored `.env`; it is not the git tree.
- Never modify the Obsidian vault. Do not write secrets, `.env`, Intervals dumps, or unrelated files to OneDrive.
- Do not add files or folders that do not help create high-quality running training plans.

## Before writing or revising a plan

1. Read the relevant profile in `$RUNNING_DATA_DIR/athletes/` (goals, constraints, PBs, anchors).
2. Read recent entries in `$RUNNING_DATA_DIR/history/` (verbatim athlete feedback).
3. If present, read `.cache/intervals/<YYYY-MM>/month.md` for recent completed load (run/ride km, sessions). Cache is gitignored and may be missing on a fresh clone — run `uv run fetch-activities YYYY-MM` first (after `uv sync`). Still use `history/` for body-feel and constraints; the cache is load evidence only. These Intervals dumps stay in local `.cache/` and are not PersonalData.
4. Read the current week plan in `$RUNNING_DATA_DIR/plans/` (`*-week.json`, and generated `.md` if useful).
5. Read relevant material in `library/` and `research/` (in this git repo).
6. Confirm you have enough tailored info (see Key goal). If not, stop and ask.
7. Follow sound sports science (progressive load, recovery, injury and illness flags, intensity distribution). Respect red flags already recorded in the athlete profile, history, or prior week plans in `$RUNNING_DATA_DIR/plans/` (e.g. arrhythmia, persistent high HR).
8. Once the athlete is on sustainable mileage, actively track **macrocycle timing**: when the current block should end, when to peak for a race, and when to insert rest or transition weeks. Do not wait for the athlete to ask — flag upcoming block changes in plans and in discussion.

## Periodization (blocks, peak, rest)

- After base mileage is stable, structure work in clear **blocks** (typically 3–6 weeks build + 1 easier/deload week, adjusted to the athlete).
- For A-races: plan a defined **peak** (sharpening / taper) and a **post-race recovery / transition** before the next build.
- Watch for end-of-block signals in `$RUNNING_DATA_DIR/history/` (persistent fatigue, foot flare, easy-pace drift, stalled sessions) and cut or deload early rather than finishing a block on principle.
- Keep the long-term roadmap (`$RUNNING_DATA_DIR/plans/roadmap.md` or athlete-linked equivalent) in mind when choosing block focus (base vs threshold vs VO₂ vs race-specific). Author from [`templates/roadmap.md`](templates/roadmap.md).

## Athletes

- Durable, general information about each athlete lives in `$RUNNING_DATA_DIR/athletes/<name>.md` — the single reference point for goals, constraints, performances, and training anchors. Author from [`templates/athlete.md`](templates/athlete.md).
- Update the profile when lasting facts change (new PB, new injury constraint, goal change). Do not dump week-to-week body-feel notes here; those go in `$RUNNING_DATA_DIR/history/`.
- When planning for someone new, create their profile file before writing the plan.

## Plans

- **Source of truth:** `$RUNNING_DATA_DIR/plans/YYYY-MM-DD-week.json` (Monday date). Author from [`templates/week.json`](templates/week.json); contract in [`schemas/week.schema.json`](schemas/week.schema.json).
- Render readable markdown: `uv run render-week-plan` → `$RUNNING_DATA_DIR/plans/YYYY-MM-DD-week.md` (generated; do not hand-edit as source).
- Keep all week plans flat under `$RUNNING_DATA_DIR/plans/` — do not move superseded weeks. Current week = newest `*-week.json` by Monday date in the filename.
- `$RUNNING_DATA_DIR/plans/archive/` is for leftover vault / reference notes only (old plans, zones, examples) — not part of the weekly workflow.
- **Arithmetic check (mandatory):** before finishing any week plan, sum every `days[].run_km` and set `run_total_km` to that exact total. Day `run_name` / `description` distances must match `run_km`. `uv run render-week-plan` and `uv run update-weekly-plan` refuse mismatched totals — do not bypass by editing the markdown alone. Schema validation does **not** replace this Python check.
- Intervals workout steps: build via `running/workout_syntax.py` following [Intervals workout builder syntax](https://forum.intervals.icu/t/workout-builder-syntax-quick-guide/123701). Prefer documented targets (`% HR`, `Zx HR`, absolute Pace). Absolute bpm is **not** in that guide and must not be used as a structured target.
- Date plans via filename (`week_start`) and JSON fields (`generated_on`, `updated_at_gmt`). Use `uv run gmt-now` for GMT tags.
- Push to Intervals/Garmin: `uv run update-weekly-plan` (reads JSON `days` — runs and simple `bike_min`/`bike_km` Rides). Use `--intervals-only` for quality run sessions only. Never updates calendar days before today.
- **Do not push** with `update-weekly-plan` until the athlete has **explicitly accepted** the week plan in chat. Writing/rendering JSON+markdown is fine; calendar/Garmin upload waits on acceptance. If pushed by mistake, clear the week’s managed `running-repo:` events and say so.
- **Always paste the exact week in chat** whenever you create or revise a week plan (the copy-paste summary block and/or day-by-day table with distances). Do not only point at the file.

## Code (Python)

- Always document new and meaningfully changed functions with **Google-style** (PEP 257) docstrings: concise one-line summary first; expand only when behaviour is non-obvious. Use `Args:`, `Returns:`, and `Raises:` when the signature or side effects are not obvious from the name alone.
- Do **not** put types in the docstring — types live in annotations. Do **not** use type-brief forms like `(name: str) -> Path`.

```python
def multiply(a: int, b: int) -> int:
    """Return the product of two numbers.

    Args:
        a: First number.
        b: Second number.

    Returns:
        Product of ``a`` and ``b``.
    """
    return a * b
```

- Prefer modular helpers (e.g. workout string builders in `running/workout_syntax.py`) over inlining Intervals syntax in plan JSON loaders.
- After changing workout string generation, run `uv run pytest`.

## Testing

- Tests must assert **intended** behaviour, not “whatever the code currently does.”
- If a test fails, **report the failure** and diagnose (bad data vs code bug vs wrong intended assertion) before changing production code — rather than silently loosening assertions to match broken behaviour.
- **Never** silently loosen, rewrite, or delete assertions to match broken behaviour.
- We should **never** match broken behaviour.
- Test docstrings stay Google-style and concise: one-line summary, then optional `Purpose:` / `Remove when:` sections (contract guarded, and when the test can be deleted).

## History

- When the user provides running-related information (body feel, soreness, sleep/stress, adherence, illness, injury, goals, constraints), save a **dated verbatim** copy under `$RUNNING_DATA_DIR/history/` (e.g. `history/2026-07-19-body-feel.md`). Author from [`templates/history.md`](templates/history.md).
- Do not paraphrase away the original wording. A short metadata header (date received, preferably GMT via `uv run gmt-now`) is fine.
- Never overwrite prior history entries; add new dated files.

## Research

- When further sports science is required, diligently research high-quality sources (prefer primary literature or reputable secondary sources).
- **Download or save** useful material into in-repo `research/` (see [`research/INDEX.md`](research/INDEX.md); copy [`templates/research.md`](templates/research.md) for new cards), including source URL, access date (GMT), and planning implications. Do not leave findings only in chat. Research stays in git — it is generic evidence, not PersonalData.
- Prefer citing **in-repo** evidence cards before making new web claims.
- When a plan decision depends on evidence, list the local paths in that plan’s `research_used` field (paper trail). Example: `research/load-injury/ramskov-2024-session-spikes-5200.md`.

## README

- Keep [`README.md`](README.md) up to date with a concise description of each folder whenever folders are added or their role changes.

## Dating

- Date-stamp plans (`week_start`, `generated_on`, `updated_at_gmt` in JSON), history entries, and research (filenames and/or YAML frontmatter) so past information can inform future training.
- Prefer GMT/UTC from `uv run gmt-now` when tagging.

## Images

- Convert every image in this repo into a simple markdown file that captures the image content **absolutely correctly** (tables, numbers, wording, structure).
- Each image should be processed/converted **only once**. After a correct conversion, **delete the image** from the repo and point any links at the new `.md` file.
- Do not leave image binaries in the repo once their markdown equivalent exists.
