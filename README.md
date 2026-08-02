# Running

Generate high-quality, sports-science–grounded running training plans for myself and possibly others. Plans are tuned to dated feedback on how the body is handling training load.

## Setup

Requires [uv](https://github.com/astral-sh/uv). From the repo root:

```bash
uv sync
```

## Folders

| Folder | Description |
|--------|-------------|
| [`library/`](library/) | Reference material: workout recipes, double-threshold notes, strength & conditioning, injury notes, club logistics. |
| [`research/`](research/) | Sports science evidence cards and notes ([INDEX](research/INDEX.md)); topic subfolders for intensity, load/injury, taper, strength, tendinopathy, cross-training. |
| [`athletes/`](athletes/) | Athlete profiles — durable goals, constraints, PBs, and training anchors for each person. |
| [`plans/`](plans/) | Week plans flat: **`YYYY-MM-DD-week.yaml`** (source of truth) + generated `.md`; also [`long-term-roadmap.md`](plans/long-term-roadmap.md). Current week = newest `*-week.yaml` by date. |
| [`plans/archive/`](plans/archive/) | Legacy/reference notes only (old plans, zones, examples) — not part of the weekly workflow. |
| [`templates/`](templates/) | Blank starters for new weeks ([`TEMPLATE.yaml`](templates/TEMPLATE.yaml), readable-view notes). |
| [`history/`](history/) | Dated verbatim copies of running-related information the athlete provides (body feel, constraints, goals, adherence). |
| [`running/`](running/) | Installable Python package (Intervals helpers, week YAML render/push). Run via `uv run …`. |
| [`scripts/`](scripts/) | Pointers only — use `uv run` entry points (see [`scripts/README.md`](scripts/README.md)). |
| [`.cache/`](.cache/) | Local-only (gitignored). Monthly Intervals digests under `.cache/intervals/YYYY-MM/` (`month.md`, JSON). |

## How it works

1. Athlete provides how the body feels and related training context → saved under `history/` with a date.
2. Agent reads the athlete’s profile in `athletes/`, recent `history/`, the current plan in `plans/`, relevant `library/` notes, and `research/`.
3. If more sports science is needed, agent researches and saves sources into `research/`.
4. New or updated week is written as `plans/YYYY-MM-DD-week.yaml` from [`templates/TEMPLATE.yaml`](templates/TEMPLATE.yaml); render with `uv run render-week-plan`. Leave prior weeks in place under `plans/`.
5. Durable profile facts (new PBs, lasting constraints, goal changes) are updated in `athletes/`.

### Weekly plan (YAML → markdown → Intervals)

```bash
# Edit plans/YYYY-MM-DD-week.yaml, then:
uv run render-week-plan
uv run update-weekly-plan          # optional calendar push
uv run update-weekly-plan --dry-run
```

### Intervals.icu monthly download

Requires `.env` with `INTERVALS_API_KEY=` (see [`.env.example`](.env.example)).

```bash
uv run fetch-activities 2026-07
uv run fetch-activities $(date -u +%Y-%m)
```

Writes `.cache/intervals/YYYY-MM/{meta.json,activities.json,month.md}`.

### Push weekly plan to Intervals.icu

Reads runnable `days` from the current `plans/*-week.yaml` (runs + simple `bike_min`/`bike_km` Rides) and upserts calendar workouts.

```bash
uv run update-weekly-plan
uv run update-weekly-plan --intervals-only
uv run update-weekly-plan --dry-run
uv run update-weekly-plan --demo-5x1km
```

Clears existing `running-repo:` calendar events from **today onward** in the week range before uploading (use `--no-clear` to skip). **Never updates or clears days before today**; a plan whose coverage/sessions are entirely in the past hard-errors. After upload, forces an Intervals→Garmin planned-workout re-upload (toggle; use `--no-garmin-sync` to skip). Day `description` should use Intervals workout syntax with **HR or Pace** targets (e.g. `Z2 HR`, `intensity=warmup`) so Garmin gets executable steps.

Requires Intervals → Garmin **Upload planned workouts**. After the script runs, sync the watch via the Garmin Connect app — Intervals cannot talk to the watch directly.

See [`AGENTS.md`](AGENTS.md) for agent rules.
