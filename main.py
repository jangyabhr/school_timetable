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
    timetable_state, unplaced, _, stats = run_placer(
        events, slots, slot_lookup, suitability, conflict_map
    )

    # Solver summary
    phases_run = 1 + stats["phase2_ran"] + stats["phase3_ran"]
    total_slots = NUM_CLASSES * DAYS_PER_WEEK * PERIODS_PER_DAY
    placed = len(timetable_state)
    scores = stats["scores"]
    avg_score = sum(scores) / len(scores) if scores else 0

    from collections import defaultdict
    from event_generator import CLASS_ORDER
    class_fill = defaultdict(int)
    for placement in timetable_state.values():
        class_fill[placement["class"]] += 1
    slots_per_class = DAYS_PER_WEEK * PERIODS_PER_DAY

    print(f"\n   ── Solver Summary ──")
    print(f"   Phases run       : {phases_run} / 3")
    print(f"   Total placed     : {placed}  |  Unplaced: {len(unplaced)}")
    print(f"   Slot utilisation : {placed} / {total_slots}  ({placed/total_slots*100:.1f}%)")
    print(f"   Score stats      : avg {avg_score:.1f}  |  min {min(scores)}  |  max {max(scores)}")
    print(f"   Conflict pairs   : {total_conflicts}")
    if stats["phase2_ran"]:
        print(f"   Repair           : {stats['phase2_swaps']} swaps  |  {stats['phase2_repair_attempts']} slots tried")
    if stats["phase3_ran"]:
        print(f"   Backtrack        : {stats['phase3_undone']} placements undone")
    print(f"\n   Per-class fill (placed / {slots_per_class} slots):")
    row = ""
    for i, section in enumerate(CLASS_ORDER):
        row += f"  {section:>3} {class_fill[section]:>2}/{slots_per_class}"
        if (i + 1) % 4 == 0:
            print("  " + row)
            row = ""
    if row:
        print("  " + row)

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
