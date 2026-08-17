# Running

Generate high-quality, sports-science–grounded running training plans. Plans are tuned to dated feedback on how the body is handling training load.

Live athlete notes and week plans live under **`$RUNNING_DATA_DIR`** (typically `~/OneDrive/PersonalData/running/`), not in this git tree. Set it in gitignored `.env` (see [`.env.example`](.env.example)). Intervals API dumps stay in local `.cache/`.

## Setup

Requires [uv](https://github.com/astral-sh/uv). From the repo root:

```bash
uv sync
uv sync --extra dev   # pytest for workout-syntax and week JSON tests
```

Copy [`.env.example`](.env.example) to `.env`. Set `RUNNING_DATA_DIR` and, for Intervals, `INTERVALS_API_KEY`.

## Folders

| Folder | Description |
|--------|-------------|
| [`library/`](library/) | Reference material: workout recipes, double-threshold notes, strength & conditioning, injury notes, club logistics. |
| [`research/`](research/) | Sports science evidence cards and notes ([INDEX](research/INDEX.md)); new cards from [`templates/research.md`](templates/research.md). Stays in git (generic, not PersonalData). |
| [`templates/`](templates/) | Scaffolds: [`week.json`](templates/week.json) (code dataset), markdown for [`athlete`](templates/athlete.md) / [`history`](templates/history.md) / [`roadmap`](templates/roadmap.md) / [`research`](templates/research.md). |
| [`schemas/`](schemas/) | JSON Schema for week plans ([`week.schema.json`](schemas/week.schema.json), draft 2020-12). |
| [`examples/athletes/sample/`](examples/athletes/sample/) | Fictional athlete + history + roadmap (not live data). Weeks use [`templates/week.json`](templates/week.json) / [`schemas/week.schema.json`](schemas/week.schema.json). |
| [`running/`](running/) | Installable Python package (Intervals helpers, week JSON render/push, workout syntax). Run via `uv run …`. |
| [`tests/`](tests/) | Pytest suite: Intervals syntax, week totals/schema, path roots, upload past-day safety, Pace/stride contracts. `uv sync --extra dev && uv run pytest`. |
| [`.cache/`](.cache/) | Local-only (gitignored). Monthly Intervals digests under `.cache/intervals/YYYY-MM/` (`month.md`, JSON). |

Live personal data (`$RUNNING_DATA_DIR`):

| Folder | Description |
|--------|-------------|
| `athletes/` | Athlete profiles — durable goals, constraints, PBs, and training anchors. |
| `history/` | Dated verbatim copies of running-related information the athlete provides. |
| `plans/` | Week plans flat: **`YYYY-MM-DD-week.json`** (source of truth) + generated `.md`; also `roadmap.md`. Current week = newest `*-week.json` by date. |
| `plans/archive/` | Leftover vault / reference notes only — not part of the weekly workflow. |

`data_root()` reads `RUNNING_DATA_DIR` unless an explicit `root=` is passed (tests use a fixture tree and never write to OneDrive).

## How it works

1. Athlete provides how the body feels and related training context → saved under `$RUNNING_DATA_DIR/history/` with a date.
2. Agent reads the athlete’s profile in `$RUNNING_DATA_DIR/athletes/`, recent `history/`, the current plan in `$RUNNING_DATA_DIR/plans/`, relevant in-repo `library/` notes, and `research/`.
3. If more sports science is needed, agent researches and saves sources into in-repo `research/`.
4. New or updated week is written as `$RUNNING_DATA_DIR/plans/YYYY-MM-DD-week.json` from [`templates/week.json`](templates/week.json); render with `uv run render-week-plan`. Leave prior weeks in place under `plans/`.
5. Durable profile facts (new PBs, lasting constraints, goal changes) are updated in `$RUNNING_DATA_DIR/athletes/`.

### Weekly plan (JSON → markdown → Intervals)

```bash
# Edit $RUNNING_DATA_DIR/plans/YYYY-MM-DD-week.json, then:
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

Reads runnable `days` from the current `$RUNNING_DATA_DIR/plans/*-week.json` (runs + simple `bike_min`/`bike_km` Rides) and upserts calendar workouts.

```bash
uv run update-weekly-plan
uv run update-weekly-plan --intervals-only
uv run update-weekly-plan --dry-run
```

Clears existing `running-repo:` calendar events from **today onward** in the week range before uploading (use `--no-clear` to skip). **Never updates or clears days before today**; a plan whose coverage/sessions are entirely in the past hard-errors. After upload, forces an Intervals→Garmin planned-workout re-upload (toggle; use `--no-garmin-sync` to skip). Day `description` should use Intervals workout syntax with **HR or Pace** targets (e.g. `Z2 HR`, `intensity=warmup`) so Garmin gets executable steps.

Requires Intervals → Garmin **Upload planned workouts**. After the script runs, sync the watch via the Garmin Connect app — Intervals cannot talk to the watch directly.

See [`AGENTS.md`](AGENTS.md) for agent rules.
