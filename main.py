# main.py
# Full pipeline entry point for the school timetable solver.

from event_generator import generate_all_events
from slot_index      import build_slot_index
from conflict_builder import build_conflict_map
from suitability_matrix import build_suitability_matrix
from placer          import run_placer
from exporter        import export_timetable
from html_exporter   import generate_html
from constraints     import NUM_CLASSES, DAYS_PER_WEEK, PERIODS_PER_DAY


def main():
    print("=" * 50)
    print("  School Timetable Solver")
    print("=" * 50)

    # Step 1 — Slot index
    print("\n[1/7] Building slot index...")
    slots, slot_lookup = build_slot_index(NUM_CLASSES, DAYS_PER_WEEK, PERIODS_PER_DAY)
    print(f"      {len(slots)} slots created "
          f"({NUM_CLASSES} classes × {DAYS_PER_WEEK} days × {PERIODS_PER_DAY} periods)")

    # Step 2 — Events
    print("\n[2/7] Generating events...")
    events = generate_all_events(
        assignments_path="teacher_assignments.yaml",
        subject_load_path="subject_load.yaml",
    )
    print(f"      {len(events)} events generated")

    # Step 3 — Conflict map
    print("\n[3/7] Building conflict map...")
    conflict_map = build_conflict_map(events)
    total_conflicts = sum(len(v) for v in conflict_map.values()) // 2
    print(f"      {total_conflicts} conflict pairs found")

    # Step 4 — Suitability matrix
    print("\n[4/7] Building suitability matrix...")
    suitability = build_suitability_matrix(events, slot_lookup)
    print(f"      Suitability built for {len(suitability)} events")

    # Step 5 — Placement
    print("\n[5/7] Running placer...")
    timetable_state, unplaced, _ = run_placer(
        events, slots, slot_lookup, suitability, conflict_map
    )
    print(f"      Placed: {len(timetable_state)} | Unplaced: {len(unplaced)}")

    # Step 6 — Export to Excel
    print("\n[6/7] Exporting to Excel...")
    export_timetable(timetable_state, events, output_path="./timetable.xlsx")

    # Step 7 — Generate HTML tools
    print("\n[7/7] Generating HTML timetable tools...")
    generate_html(timetable_state, events, output_path="./Timetable_Tools.html")

    print("\n" + "=" * 50)
    print("  Done.")
    print("=" * 50)


if __name__ == "__main__":
    main()
