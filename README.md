# Running

Generate high-quality, sports-science–grounded running training plans for myself and possibly others. Plans are tuned to dated feedback on how the body is handling training load.

## Folders

| Folder | Description |
|--------|-------------|
| [`library/`](library/) | Reference material: workout recipes, double-threshold notes, strength & conditioning, injury notes, club logistics. |
| [`research/`](research/) | Sports science evidence cards and notes ([INDEX](research/INDEX.md)); topic subfolders for intensity, load/injury, taper, strength, tendinopathy, cross-training. |
| [`athletes/`](athletes/) | Athlete profiles — durable goals, constraints, PBs, and training anchors for each person. |
| [`plans/`](plans/) | The **current** training plan lives here (plus [`TEMPLATE.md`](plans/TEMPLATE.md) and [`long-term-roadmap.md`](plans/long-term-roadmap.md)). |
| [`plans/archive/`](plans/archive/) | Superseded and historical plans, including material migrated from Obsidian. |
| [`history/`](history/) | Dated verbatim copies of running-related information the athlete provides (body feel, constraints, goals, adherence). |
| [`scripts/`](scripts/) | Small helpers (e.g. GMT date/time tagging for files). |

## How it works

1. Athlete provides how the body feels and related training context → saved under `history/` with a date.
2. Agent reads the athlete’s profile in `athletes/`, recent `history/`, the current plan in `plans/`, relevant `library/` notes, and `research/`.
3. If more sports science is needed, agent researches and saves sources into `research/`.
4. New or updated plan is written from `plans/TEMPLATE.md` into `plans/`; the previous plan moves to `plans/archive/`.
5. Durable profile facts (new PBs, lasting constraints, goal changes) are updated in `athletes/`.

See [`AGENTS.md`](AGENTS.md) for agent rules.
