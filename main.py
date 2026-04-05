# main.py
# Full pipeline entry point for the school timetable solver.

import os
import sys

from event_generator    import generate_all_events, CLASS_ORDER, load_yaml
from slot_index         import build_slot_index
from period_generator   import (
    generate_period_assignments, validate_period_assignments,
    save_period_assignments, load_period_assignments,
)
from day_assigner       import assign_days
from post_processor     import run_post_processing
from lab_assigner       import assign_lab_periods
from exporter           import export_timetable
from html_exporter      import generate_html
from constraints        import NUM_CLASSES, DAYS_PER_WEEK, PERIODS_PER_DAY

PERIOD_ASSIGNMENTS_PATH = "period_assignments.yaml"


def main():
    print("=" * 50)
    print("  School Timetable Solver")
    print("=" * 50)

    # Step 1 — Slot index
    print("\n[1/7] Building slot index...")
    slots, slot_lookup = build_slot_index(NUM_CLASSES, DAYS_PER_WEEK, PERIODS_PER_DAY)
    print(f"      {len(slots)} slots  "
          f"({NUM_CLASSES} classes × {DAYS_PER_WEEK} days × {PERIODS_PER_DAY} periods)")

    # Step 2 — Events
    print("\n[2/7] Generating events...")
    events = generate_all_events(
        assignments_path="teacher_assignments.yaml",
        subject_load_path="subject_load.yaml",
    )
    print(f"      {len(events)} events generated")

    # Step 2.5 — Teacher capacity validation gate
    print("\n[2.5/7] Validating assignments...")
    from assignment_validator import validate_assignments
    try:
        teachers_data = load_yaml("teachers.yaml").get("teachers", {})
        result = validate_assignments(events, teachers_data)
        for w in result["warnings"]:
            print(f"  WARNING: {w}")
        for e in result["errors"]:
            print(f"  ERROR:   {e}")
        if not result["valid"]:
            print("\n  Aborting: fix assignment errors before running the solver.")
            sys.exit(1)
        elif not result["errors"] and not result["warnings"]:
            print("  All assignments valid.")
        else:
            print("  Assignments valid (see warnings above).")
    except FileNotFoundError:
        print("  WARNING: teachers.yaml not found — skipping capacity validation")

    # Step 2.6 — Apply teacher display titles (sir / ma'am)
    from teacher_titles import TEACHER_TITLES
    for event in events:
        if event.get("teacher"):
            event["teacher"] = TEACHER_TITLES.get(event["teacher"], event["teacher"])

    # Step 3 — Period assignments
    # Load from period_assignments.yaml if it exists and covers all events;
    # otherwise generate fresh and save.
    print(f"\n[3/7] Period assignments...")
    regen = True
    if os.path.exists(PERIOD_ASSIGNMENTS_PATH):
        print(f"      Loading {PERIOD_ASSIGNMENTS_PATH}...")
        period_assignments, teacher_period_load, class_period_load = \
            load_period_assignments(PERIOD_ASSIGNMENTS_PATH, events)
        if len(period_assignments) == len(events):
            violations = validate_period_assignments(
                events, period_assignments, teacher_period_load, class_period_load
            )
            if violations:
                print("      Violations in loaded file — regenerating:")
                for v in violations:
                    print(f"        {v}")
            else:
                print(f"      {len(period_assignments)} assignments loaded — valid.")
                regen = False
        else:
            missing = len(events) - len(period_assignments)
            print(f"      {missing} events missing from file — regenerating.")

    if regen:
        print("      Generating period assignments (backtracking CSP)...")
        period_assignments, teacher_period_load, class_period_load = \
            generate_period_assignments(events)
        violations = validate_period_assignments(
            events, period_assignments, teacher_period_load, class_period_load
        )
        if violations:
            print("      Period assignment violations:")
            for v in violations:
                print(f"        {v}")
            print("      WARNING: proceeding with violations — check data and rerun.")
        else:
            print(f"      {len(period_assignments)} events assigned — no violations.")
        save_period_assignments(period_assignments, events, PERIOD_ASSIGNMENTS_PATH)

    # Step 4 — Day assignment
    print(f"\n[4/7] Assigning days...")
    timetable_state = assign_days(events, period_assignments, slot_lookup)
    total_instances = sum(e["weekly_load"] for e in events)
    placed          = len(timetable_state)
    print(f"      {placed} / {total_instances} instances placed")

    # Per-class fill summary
    slots_per_class = DAYS_PER_WEEK * PERIODS_PER_DAY
    class_fill = {}
    for placement in timetable_state.values():
        cls = placement["class"]
        class_fill[cls] = class_fill.get(cls, 0) + 1
    row = ""
    for i, section in enumerate(CLASS_ORDER):
        row += f"  {section:>3} {class_fill.get(section, 0):>2}/{slots_per_class}"
        if (i + 1) % 4 == 0:
            print("  " + row)
            row = ""
    if row:
        print("  " + row)

    # Step 5 — Post-processing (duty teachers + Free periods)
    print("\n[5/7] Post-processing (duty assignments, Free periods)...")
    timetable_state = run_post_processing(
        timetable_state, events, CLASS_ORDER, DAYS_PER_WEEK, PERIODS_PER_DAY
    )

    # Step 6 — Lab annotation
    print("\n[6/7] Annotating lab periods...")
    timetable_state = assign_lab_periods(timetable_state)

    # Step 7 — Export
    print("\n[7/7] Exporting...")
    export_timetable(timetable_state, events, output_path="./timetable.xlsx")
    generate_html(timetable_state, events, output_path="./Timetable_Tools.html")

    print("\n" + "=" * 50)
    print("  Done.")
    print("=" * 50)


if __name__ == "__main__":
    main()
