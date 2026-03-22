# Solver Strategy

## Timetable Scale
- Classes: 12 (6A, 6B, 7A, 7B, 8A, 8B, 9A, 9B, 10A, 10B, 11, 12)
- Days: 6 per week (Monday=0 … Saturday=5)
- Periods: 8 per day (0–7)
- Total slots: 12 × 6 × 8 = 576 per week


## Pipeline Overview

### Step 1 — Build Slot Index (`slot_index.py`)
Call `build_slot_index(num_classes=12, days_per_week=6, periods_per_day=8)`.
Produces:
- `slots`: flat list of 576 slot dicts `{slot_id, class_idx, day, period}`
- `slot_lookup`: dict mapping `(class_idx, day, period)` → `slot_id`

Every event placement, conflict check, and suitability filter references slot_ids.


### Step 2 — Generate Events (`event_generator.py`)
Call `generate_all_events(assignments_path, subject_load_path)`.
Loads `teacher_assignments.yaml` and `subject_load.yaml`.

Each event is an atomic scheduling unit:
```
{ class, class_idx, subject, teacher, weekly_load }
```
- One event per (section, subject) pair from teacher_assignments.yaml
- CCA events generated separately via `generate_cca_events()` — teacher=None,
  weekly_load=2, placed on Saturday periods 6–7
- Each event is placed `weekly_load` times by the placer


### Step 3 — Build Conflict Map (`conflict_builder.py`)
Call `build_conflict_map(events)`.
Two events conflict if they share a teacher OR share a class section.
CCA events (teacher=None) are excluded from teacher-clash checks.
Result: `event_idx → set of conflicting event_idxs`


### Step 4 — Build Suitability Matrix (`suitability_matrix.py`)
Call `build_suitability_matrix(events, slot_lookup)`.
Maps each event to its list of allowed slot_ids:

| Subject type          | Allowed slots                                  |
|-----------------------|------------------------------------------------|
| Game                  | Tuesday period 7 only (fixed)                  |
| CCA                   | Saturday periods 6–7 only (fixed)              |
| Library, WE           | Any day except Tuesday and Saturday (floating) |
| Physics/Chemistry/Bio | Periods 0–6 only (lab double-period fits)      |
| All others            | All 48 slots for their class                   |

Suitability filters run before scoring — only passing slot_ids reach score_slot.


### Step 5 — Sort Events by Constraint Density (MRV Heuristic)
Sort events descending by: `conflict_count × weekly_load`
Most-constrained events placed first to minimise backtracking.

Highest-priority events:
- Nandini (Math, 6A+6B+7A+7B) — 4 sections, weekly_load=6
- JB (Math, 8A+8B+9A+9B) — 4 sections, weekly_load=6–7
- Snigdha (Hindi+Odia, 6A–8B) — 6 sections across 2 subjects
- Ganesh (Sanskrit+Odia, 6A–8B) — 6 sections across 2 subjects
- Sanjukta (CS, 6A–8B) — 6 sections
- Lab subjects for classes 11 and 12 (double-period constraint)


### Step 6 — Greedy Placement Loop
`timetable_state` is a dict: `(event_idx, instance)` → placement dict.
It is the single mutable structure updated throughout placement.

For each event (MRV order), repeat `weekly_load` times:
```
candidate_slots = [
    slot for slot in slots
    if slot_id in suitability[event_idx]
    and (class_idx, day, period) not in occupied
    and no conflicting event placed at (day, period)
]
scored = [(score_slot(...), slot) for slot in candidate_slots if score is not None]
best = max(scored, key=score)
place event at best; update timetable_state and occupied set
```


### Step 7 — Scoring (`scoring.py`)
`score_slot(event, slot, timetable_state, suitability, conflict_map, event_idx)`
Returns None for hard violations, numeric score for valid slots.

Hard checks (returns None):
- slot_id not in suitability[event_idx]
- A conflicting event is placed at the same (day, period)

Soft scoring (additive):
| Condition                                        | Weight |
|--------------------------------------------------|--------|
| Anchor subject in period 0–2                     |    +10 |
| Same subject already placed for class today      |     −5 |
| Teacher has back-to-back period (no gap)         |     −3 |
| Lab subject starting in period 0–3               |     +8 |
| Anchor subject in last period on Monday          |     −4 |

All weights defined in `constraints.SOFT_CONSTRAINTS`.


### Step 8 — Repair Pass
After greedy loop, for each unplaced event-instance:
1. Find valid candidate slots (suitability + no hard conflict)
2. Find a placed event in that slot with a lower score than ours
3. If found: displace it, place ours, re-queue the displaced event
4. Cap at 20 attempts per event to prevent infinite loops


### Step 9 — Limited Backtracking
Triggered only if repair pass leaves events unplaced.
Undo last 30 placements from placement stack and retry.
Do not use full exhaustive backtracking — won't terminate at this scale.


### Step 10 — Validation Report
Hard checks before export:
- [ ] No teacher in two places at same (day, period)
- [ ] No class in two places at same (day, period)
- [ ] Each event placed exactly weekly_load times
- [ ] No lab subject starting at period 7 (double overflow)
- [ ] Game placed only at Tuesday period 7
- [ ] CCA placed only at Saturday periods 6 and 7

Do not export if any violation exists.


### Step 11 — Excel Export (`exporter.py`)
One sheet per class section (12 sheets) + Legend sheet.
Rows = periods 0–7, Columns = Mon–Sat.
Cell value = "Subject\nTeacher" (teacher omitted for CCA).

Colour coding:
- Light blue  — Anchor subjects (Math, Science, English, SST)
- Light green — Lab subjects (Physics, Chemistry, Biology)
- Light yellow — Fixed slots (Game, CCA)
- Light orange — Floating singles (Library, WE)
- Light grey  — Empty period


## File Dependency Map
```
teacher_assignments.yaml ─┐
subject_load.yaml         ─┼─► event_generator.py ──► events list
class_groups.yaml         ─┘         (+ CCA events)       │
                                                           │
constraints.py ─────────────────────────────────────┐     │
                                                    │     ▼
slot_index.py ──────────────────────────────► slot index (576 slots)
                                                    │     │
conflict_builder.py ◄───────────────────────────────┼─────┤
suitability_matrix.py ◄─────────────────────────────┘     │
                                                           │
                     ┌─────────────────────────────────────┘
                     ▼
               MRV sort → greedy placer → timetable_state
                     │         (event_idx, instance) keys
               scoring.py (score_slot)
                     │
               repair pass → backtrack → validation → exporter.py → timetable.xlsx
```