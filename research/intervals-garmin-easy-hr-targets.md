---
title: "Intervals.icu → Garmin easy-run HR targets (absolute bpm vs % HR)"
accessed_gmt: 2026-08-03T19:19:36Z
type: verification-notes
why_it_matters: Easy-run watch targets must use syntax Intervals parses into workout_doc, or Garmin gets no HR guidance.
research_used_urls:
  - https://forum.intervals.icu/t/workout-builder-syntax-quick-guide/123701
  - https://forum.intervals.icu/t/solved-write-min-and-max-heart-rate-in-workout/63267
  - https://forum.intervals.icu/t/hr-target-workouts-broken-on-edge-840-firmware-30-18-interpreted-as-hrmax-instead-of-bpm/130090
  - https://www.garminology.com/2025/02/12/tips-for-creating-custom-workouts-on-garmin-connect/
---

# Easy-run HR targets via Intervals → Garmin

## Verified 2026-08-03 (live Intervals parse on this athlete)

Posted temporary Run calendar events and inspected returned `workout_doc`:

| Description step | Parsed target |
|------------------|---------------|
| `- 2km 80-140 HR` | **No HR** (distance only) |
| `- 2km 80-140bpm HR` | **No HR** |
| `- 2km 40-70% HR` | `hr: {start:40, end:70, units:"%hr"}` |
| `- 2km Z1-Z2 HR` | `hr: {start:1, end:2, units:"hr_zone"}` |
| `- 2km 8:00-4:30/km Pace` | `pace: {start:480, end:270, units:"secs/km"}` |
| `- Cap 80-140 bpm  2km 8:00-4:30/km Pace` | Pace only; “Cap…” is **text cue** |

Conclusion: Intervals workout syntax does **not** support absolute bpm ranges. Staff confirmation on the forum: only `% HR` and `Zx HR` ([solved min/max HR thread](https://forum.intervals.icu/t/solved-write-min-and-max-heart-rate-in-workout/63267); [syntax guide](https://forum.intervals.icu/t/workout-builder-syntax-quick-guide/123701)).

## Athlete anchors (Run sport settings)

- `max_hr`: **195**
- Run `hr_zones` upper bounds: 149 / 158 / 167 / 176 / 181 / 186 / 195  
  → Intervals Z1 alone already goes to **149**, above the easy cap **140**, so **do not** use `Z1`/`Z2` for the easy cap.
- Map **80–140 bpm** → **41–72% HR** (80/195≈41%, 140/195≈72%).

## Garmin side

- Garmin Connect custom workouts support intensity via heart-rate zones / targets ([Garminology Connect workout tips](https://www.garminology.com/2025/02/12/tips-for-creating-custom-workouts-on-garmin-connect/)).
- Absolute-bpm `workout_doc` paths via Intervals→Garmin have been unreliable on some firmware (values treated as %HRmax) — see [Edge 840 HR-bpm bug report](https://forum.intervals.icu/t/hr-target-workouts-broken-on-edge-840-firmware-30-18-interpreted-as-hrmax-instead-of-bpm/130090). Prefer Intervals’ native **`% HR`** so the unit is explicit.

## Planning rule

Easy/long Intervals descriptions (updated 2026-08-09 — athlete: HR unsuitable for easy because it can stay low at ~4:10/km):

```text
- {km}km 8:00-4:40/km Pace
```

- Structured target: absolute **Pace** band (**4:40–8:00/km**; no faster than 4:40; floor updated 2026-08-10).
- **Garmin export:** Run sport settings must have **`threshold_pace`** set, or pace steps arrive on the watch as **“No Target”** even when `workout_doc` has pace (confirmed 2026-08-09; athlete Run id 2732126 set to **3:35/km** / `3.5833` MINS_KM). Forum: [pace targets lost without threshold](https://forum.intervals.icu/t/pace-targets-lost-in-garmin-export-for-api-created-running-workouts-steps-arrive-on-watch-as-no-target-parsed-correctly-in-workout-doc/130706).
- Optional legacy HR form (not current default): `{km}km 41-72% HR` ≈ 80–140 bpm at max_hr 195.
