# Solver Strategy

## Timetable Scale
- **Classes:** 9 (12, 10B, 10A, 9B, 9A, 8B, 8A, 7B, 7A — in CLASS_ORDER)
- **Days:** 6 per week (Monday=0 … Saturday=5)
- **Periods:** 6 per day (P1 06:40 – P6 10:10)
- **Total slots:** 9 × 6 × 6 = 324 per week


## Pipeline Overview

### Step 1 — Build Slot Index (`slot_index.py`)
`build_slot_index(num_classes=9, days_per_week=6, periods_per_day=6)`
- `slots`: flat list of 324 dicts `{slot_id, class_idx, day, period}`
- `slot_lookup`: `(class_idx, day, period)` → `slot_id`


### Step 2 — Generate Events (`event_generator.py`)
`generate_all_events(assignments_path, subject_load_path, class_groups_path)`

Loads all three YAMLs. Resolves per-section load via `group_defaults` + `section_overrides`.
Assignments for removed sections (6A, 6B, 11) are silently skipped.

Each event: `{class, class_idx, subject, teacher, weekly_load}`
Teacher names are bare at this point (titles applied in Step 2.6).


### Step 2.5 — Assignment Validation (`assignment_validator.py`)
Checks teacher capacity and subject qualification before the solver runs.
Aborts with a clear error message if any teacher is over-assigned.


### Step 2.6 — Apply Teacher Titles (`teacher_titles.py`)
Maps bare names → "sir" / "ma'am" display names (e.g. "ANIL" → "ANIL sir").
Applied once here; titled names propagate through all downstream steps.


### Step 3 — Build Conflict Map (`conflict_builder.py`)
Two events conflict if they share a teacher OR share a class section.
Library events (teacher=None) skip teacher-clash checks.
Result: `event_idx → set of conflicting event_idxs`


### Step 4 — Build Suitability Matrix (`suitability_matrix.py`)
Maps each event to its allowed slot_ids:

| Subject type               | Allowed slots                                      |
|----------------------------|----------------------------------------------------|
| Fixed-slot (none currently)| Exact (day, period) from FIXED_SLOTS               |
| Library                    | All periods except Tuesday and Saturday (floating) |
| Physics / Chemistry / Bio  | Periods 0–4 only (lab double-period fits)          |
| All others                 | All 36 slots for their class                       |

`SECTION_PERIOD_LOCKS` is applied as an additional hard filter on top of subject-type rules.
Current locks: Biology/12→P1, Math/9A→P1, English/9B→P1, Math/12→P2.


### Step 5 — Greedy Placement (`placer.py`)
Events sorted into five MRV priority tiers (most constrained first):

1. Fixed-slot subjects (currently none)
2. Period-locked events (SECTION_PERIOD_LOCKS) — fewest allowed slots first
3. Lab subjects — Physics > Chemistry > Biology
4. Bottleneck teachers (≥5 sections) — Subhasmita ma'am (6), Sanjukta ma'am (6), Srikant ma'am (5)
5. All others — teacher load DESC, class_idx DESC, fewest suitability slots, conflict×load DESC

For each event × weekly_load instances: score all candidate slots, place at best.
Falls back to Phase 2 (repair: displacing lower-scored events) and Phase 3 (limited backtrack: undo last 30, retry) if any events remain unplaced.


### Step 6 — Scoring (`scoring.py`)
`score_slot()` returns `None` for hard violations, numeric score otherwise.

| Soft constraint                                        | Weight |
|--------------------------------------------------------|--------|
| Anchor subject (Math/Sci/Eng/SST) in morning P1–P3     |    +10 |
| Lab subject starting in P1–P2                          |     +8 |
| Core subject at same period as existing instances      |    +18 |
| Core subject within ±1 period of mode                  |     +8 |
| Math/Science extra period-consistency bonus            |     +8 |
| Same subject twice in a day for same class             |    −20 |
| Core subject in last period (P6, any day)              |    −10 |
| Core subject in last period on Monday                  |     −4 |
| Teacher back-to-back periods                           |     −3 |


### Step 7 — Post-Processing (`post_processor.py`)
- Assigns a duty teacher to each Library slot (teacher=None → lowest-load available)
- Fills remaining empty slots as "Free" with a duty teacher


### Step 8 — Lab Annotation (`lab_assigner.py`)
Marks one instance per (section, subject) as `is_lab=True`.
Respects room conflicts: CS lab shared by CS (7A–8B), IT (9A–12), Math (all 9 sections).


### Step 9 — Export
- `exporter.py` → `timetable.xlsx` (one sheet per section + teacher load summary + dashboard)
- `html_exporter.py` → `Timetable_Tools.html` (Substitute Finder, Period Coverage,
  Master Timetable, Teacher Loads — all interactive)


## File Dependency Map
```
teacher_assignments.yaml ─┐
subject_load.yaml         ─┼─► event_generator.py ──► events (bare names)
class_groups.yaml         ─┘                              │
                                                          │ validate
teachers.yaml ──────────────► assignment_validator.py ◄──┤
                                                          │ apply titles
teacher_titles.py ──────────────────────────────────────► │
                                                          ▼
                                                   events (titled names)
constraints.py ──────────────────────────┐             │
                                         │             ▼
slot_index.py ──────────────────────► slot index ──► placer.py
                                         │           (+ conflict_builder,
                                         │             suitability_matrix,
                                         └──────────────scoring)
                                                          │
                                                    timetable_state
                                                          │
                                          post_processor → lab_assigner
                                                          │
                                              exporter → timetable.xlsx
                                           html_exporter → Tools.html
```
