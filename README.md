# School Timetable Solver

A Python-based constraint satisfaction solver that automatically generates weekly timetables for a school serving classes 6–12.

## Overview

The solver generates a weekly school timetable across **12 class sections**, **6 days** (Mon–Sat), and **8 periods per day** — 576 total slots. It uses a greedy placement algorithm with MRV (Most Restricted Variable) heuristics, soft scoring, repair passes, and limited backtracking to satisfy scheduling constraints.

**Output**: Color-coded Excel workbook + interactive HTML viewer.

## Project Structure

```
school_timetable/
├── main.py                   # Entry point — orchestrates the 9-step pipeline
├── constraints.py            # All hard/soft constraints and subject categories
├── slot_index.py             # Builds 576-slot enumeration
├── event_generator.py        # Converts YAML config → scheduling events
├── conflict_builder.py       # Detects teacher/class conflicts
├── suitability_matrix.py     # Filters eligible slots per event
├── placer.py                 # Greedy placement + repair + backtracking
├── scoring.py                # Scores candidate slots (hard + soft weights)
├── post_processor.py         # Adds Game, duty teachers, free periods
├── lab_assigner.py           # Annotates double-period lab slots
├── exporter.py               # Excel (.xlsx) export with color coding
├── html_exporter.py          # Interactive HTML viewer with JavaScript
├── teacher_assignments.yaml  # (section, subject) → teacher mappings
├── subject_load.yaml         # Weekly periods per subject per class
└── class_groups.yaml         # Class groupings (6–8, 9–10, 11–12)
```

## Prerequisites

- Python 3.8+
- `openpyxl` — Excel file generation
- `pyyaml` — YAML config parsing

```bash
pip install openpyxl pyyaml
```

## Usage

```bash
python main.py
```

The solver runs a 9-step pipeline and produces two output files:

| File | Description |
|------|-------------|
| `timetable.xlsx` | 12 class sheets + Legend + Dashboard, color-coded by subject type |
| `Timetable_Tools.html` | Interactive viewer — filter by class/teacher, view stats |

## Configuration

### `teacher_assignments.yaml`
Maps each (class section, subject) pair to a teacher:
```yaml
assignments:
  - section: 6A
    subject: Math
    teacher: Nandini
```

### `subject_load.yaml`
Specifies how many periods per week each subject gets per class:
- Classes 6–8: 6 periods for anchor subjects (Math, Science, English, SST)
- Classes 9–10: 7 periods for core subjects
- Classes 11–12: 7 periods for Science/Math streams
- Special subjects: Game (1), Library (1), WE (1), CCA (2)

### `class_groups.yaml`
Groups classes into tiers for applying shared rules:
- `class_6_8`: 6A, 6B, 7A, 7B, 8A, 8B
- `class_9_10`: 9A, 9B, 10A, 10B
- `class_11_12`: 11, 12

## Solver Algorithm

1. **Slot Index** — Enumerate all 576 slots (class × day × period)
2. **Event Generation** — Convert teacher+load config into ~200 atomic events
3. **Conflict Map** — Identify events that cannot share the same time slot
4. **Suitability Matrix** — Filter valid slots per event (e.g., CCA → Saturday only)
5. **MRV Sort** — Order events by constraint density (most constrained first)
6. **Greedy Placement** — Assign each event to the highest-scoring valid slot
7. **Repair Pass** — Displace lower-priority placed events to accommodate unplaced ones
8. **Backtracking** — Undo last 30 placements if events remain unplaced (max 3 phases)
9. **Export** — Validate, then generate Excel + HTML output

## Constraints

**Hard constraints** (must not be violated):
- No teacher or class assigned to two periods at the same time
- Weekly period load must match `subject_load.yaml`
- Lab subjects occupy consecutive double periods
- Fixed slots for Game, CCA, and other special subjects

**Soft constraints** (scored and minimized):
- Morning preference for anchor subjects (+10 bonus)
- Avoid same subject repeated on consecutive days (−20 penalty)
- Minimize teacher gaps between periods (−3 penalty per gap)
- Spread subjects evenly across the week

## Subject Categories

| Category | Subjects |
|----------|----------|
| Anchor | Math, Science, English, SST |
| Language | Hindi, Odia, Sanskrit |
| Lab | Physics, Chemistry, Biology |
| Tech | ComputerScience, IT |
| Fixed | Game, CCA |
| Floating | Library, WE |

## Output

### Excel (`timetable.xlsx`)
- One sheet per class section (12 total) + Legend + Dashboard
- Color coding: Blue (anchor), Green (lab), Yellow (fixed), Orange (floating)
- Each cell shows subject + teacher name

### HTML (`Timetable_Tools.html`)
- Standalone file — no server required, open in any browser
- Filter and search timetables by class or teacher
- Embedded solver statistics and constraint violation report
