# Agent rules

## Key goal — ask; do not guess

- If the user has **not** provided enough information to create a high-quality, tailored plan (body feel / readiness, constraints, goals, schedule limits, recent load response, etc.), **ask for the missing information before writing or revising the plan**.
- If you are unsure, ask. **Do not guess.**
- Prefer a short, specific question list over assumptions. Document answers in `history/` when the user replies.

## Key goal — disagree when the request is unsafe or unsound

- If the user’s requested plan (volume, intensity, race timeline, etc.) conflicts with sports science, injury history, or their own recent load-tolerance signals, **do not silently comply**.
- Tell them **why** you disagree, what risk you see, and **how the request should be reevaluated** (concrete alternative numbers/timeline).
- Then write the plan to the reevaluated approach unless the user explicitly overrides after hearing the rationale.

## Scope

- **Only edit files inside this repository.** Never modify the Obsidian vault or any path outside this project.
- Do not add files or folders that do not help create high-quality running training plans.

## Before writing or revising a plan

1. Read the relevant profile in `athletes/` (goals, constraints, PBs, anchors).
2. Read recent entries in `history/` (verbatim athlete feedback).
3. If present, read `.cache/intervals/<YYYY-MM>/month.md` for recent completed load (run/ride km, sessions). Cache is gitignored and may be missing on a fresh clone — run `uv run fetch-activities YYYY-MM` first (after `uv sync`). Still use `history/` for body-feel and constraints; the cache is load evidence only.
4. Read the current week plan in `plans/` (`*-week.yaml`, and generated `.md` if useful).
5. Read relevant material in `library/` and `research/`.
6. Confirm you have enough tailored info (see Key goal). If not, stop and ask.
7. Follow sound sports science (progressive load, recovery, injury and illness flags, intensity distribution). Respect red flags already recorded in the athlete profile, history, or prior week plans in `plans/` (e.g. arrhythmia, persistent high HR).
8. Once the athlete is on sustainable mileage, actively track **macrocycle timing**: when the current block should end, when to peak for a race, and when to insert rest or transition weeks. Do not wait for the athlete to ask — flag upcoming block changes in plans and in discussion.

## Periodization (blocks, peak, rest)

- After base mileage is stable, structure work in clear **blocks** (typically 3–6 weeks build + 1 easier/deload week, adjusted to the athlete).
- For A-races: plan a defined **peak** (sharpening / taper) and a **post-race recovery / transition** before the next build.
- Watch for end-of-block signals in `history/` (persistent fatigue, foot flare, easy-pace drift, stalled sessions) and cut or deload early rather than finishing a block on principle.
- Keep the long-term roadmap ([`plans/long-term-roadmap.md`](plans/long-term-roadmap.md) or athlete-linked equivalent) in mind when choosing block focus (base vs threshold vs VO₂ vs race-specific).

## Athletes

- Durable, general information about each athlete lives in `athletes/<name>.md` — the single reference point for goals, constraints, performances, and training anchors.
- Update the profile when lasting facts change (new PB, new injury constraint, goal change). Do not dump week-to-week body-feel notes here; those go in `history/`.
- When planning for someone new, create their profile file before writing the plan.

## Plans

- **Source of truth:** `plans/YYYY-MM-DD-week.yaml` (Monday date). Author from [`templates/TEMPLATE.yaml`](templates/TEMPLATE.yaml).
- Render readable markdown: `uv run render-week-plan` → `plans/YYYY-MM-DD-week.md` (generated; do not hand-edit as source).
- Keep all week plans flat under `plans/` — do not move superseded weeks. Current week = newest `*-week.yaml` by Monday date in the filename.
- [`plans/archive/`](plans/archive/) is for legacy/reference notes only (old plans, zones, examples) — not part of the weekly workflow.
- Date plans via filename (`week_start`) and YAML fields (`generated_on`, `updated_at_gmt`). Use `uv run gmt-now` for GMT tags.
- Push to Intervals/Garmin: `uv run update-weekly-plan` (reads YAML `days` — runs and simple `bike_min`/`bike_km` Rides). Use `--intervals-only` for quality run sessions only. Never updates calendar days before today.

## History

- When the user provides running-related information (body feel, soreness, sleep/stress, adherence, illness, injury, goals, constraints), save a **dated verbatim** copy under `history/` (e.g. `history/2026-07-19-body-feel.md`).
- Do not paraphrase away the original wording. A short metadata header (date received, preferably GMT via `scripts/gmt_now.py`) is fine.
- Never overwrite prior history entries; add new dated files.

## Research

- When further sports science is required, diligently research high-quality sources (prefer primary literature or reputable secondary sources).
- **Download or save** useful material into `research/` (see [`research/INDEX.md`](research/INDEX.md)), including source URL, access date (GMT), and planning implications. Do not leave findings only in chat.
- Prefer citing **in-repo** evidence cards before making new web claims.
- When a plan decision depends on evidence, list the local paths in that plan’s frontmatter `research_used:` (paper trail). Example: `research/load-injury/ramskov-2024-session-spikes-5200.md`.

## README

- Keep [`README.md`](README.md) up to date with a concise description of each folder whenever folders are added or their role changes.

## Dating

- Date-stamp plans, history entries, and saved research (filenames and/or frontmatter) so past information can inform future training.
- Prefer GMT/UTC from `uv run gmt-now` when tagging.

## Images

- Convert every image in this repo into a simple markdown file that captures the image content **absolutely correctly** (tables, numbers, wording, structure).
- Each image should be processed/converted **only once**. After a correct conversion, **delete the image** from the repo and point any links at the new `.md` file.
- Do not leave image binaries in the repo once their markdown equivalent exists.
