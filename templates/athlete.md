# Athlete profile template

Copy to `$RUNNING_DATA_DIR/athletes/<slug>.md`. Update when durable facts change (goals, constraints, PBs, zone anchors). Week-to-week body feel belongs in `history/`, not here.

Machine-readable Pace bands live in the sibling **`athletes/<slug>.json`** (copy [`templates/athlete.json`](athlete.json)). Render and Intervals upload read the JSON, not this markdown.

Replace the heading with the athlete’s name.

# Name

Primary / secondary athlete. Prefers km or miles.

## Overview

- Training context (amateur / club / commute / S&C cadence)
- Typical week shape

## Goals

- A-race / current phase
- Medium-term volume or performance target
- Link the long-term roadmap: `plans/roadmap.md`

## Known performances

| Date | Event | Result |
|------|-------|--------|
| YYYY-MM-DD | e.g. 5k | time |

## Recent load context

- Last few weeks of run km and notable sessions
- Point at history files for detail

## Training preferences and anchors

- Easy-run policy (conversation / feel)
- **Easy Pace band** for Intervals/Garmin lives in `athletes/<slug>.json` (`easy_pace_ceiling` / `easy_pace_floor`)
- Threshold / quality anchors if set
- Deload cadence; S&C days

## Constraints and red flags

- Injuries, medical flags, overreach patterns
- Links to `library/` notes in the Running repo when relevant

## Related material

- History, roadmap, library paths
