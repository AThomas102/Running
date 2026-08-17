# Training plan (readable view)

**Source of truth:** copy [`week.json`](week.json) to `$RUNNING_DATA_DIR/plans/YYYY-MM-DD-week.json` (Monday date), edit that file, then render:

```bash
uv sync   # once per clone / when deps change
uv run render-week-plan
uv run render-week-plan 2026-08-03
```

Push runnable days to Intervals/Garmin:

```bash
uv run update-weekly-plan
uv run update-weekly-plan --intervals-only
```

Do not hand-edit generated `*-week.md` — regenerate from JSON.

Schema notes (contract in [`../schemas/week.schema.json`](../schemas/week.schema.json)):

- `run_kind`: `easy` | `long` | `interval` | `rest`
- `bike`: `none` | `commute` | `easy` (soft flag; optional)
- `bike_min` / `bike_km`: simple Ride length to upload (prefer minutes; no bike intervals)
- `run_total_km` must equal the sum of all `days[].run_km` (render/upload refuse mismatches)
- Intervals sessions = runs with `run_kind` in `{easy,long,interval}` and `run_km > 0`, plus rides when `bike_min` or `bike_km` > 0
- Easy/long Pace band comes from the **athlete profile**, not a repo-wide default in this template
- Strides after easy: open ``Press lap … intensity=rest`` bridge (lap to continue), then `4x` / `20s intensity=active` / `90s intensity=rest`
