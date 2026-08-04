# Training plan (readable view)

**Source of truth:** copy [`TEMPLATE.yaml`](TEMPLATE.yaml) to `plans/YYYY-MM-DD-week.yaml` (Monday date), edit that file, then render:

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

Do not hand-edit generated `*-week.md` — regenerate from YAML.

Schema notes (also in TEMPLATE.yaml comments):

- `run_kind`: `easy` | `long` | `interval` | `rest`
- `bike`: `none` | `commute` | `easy` (soft flag; optional)
- `bike_min` / `bike_km`: simple Ride length to upload (prefer minutes; no bike intervals)
- `run_total_km` must equal the sum of all `days[].run_km` (render/upload refuse mismatches)
- Intervals sessions = runs with `run_kind` in `{easy,long,interval}` and `run_km > 0`, plus rides when `bike_min` or `bike_km` > 0
- Use `{km}km 41-72% HR (no faster than 4:30 per km)` on easy/long (= **80–140 bpm** at Run max_hr 195; Intervals cannot parse absolute bpm — see research card).
