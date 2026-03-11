# analyze_repetition.py
# Dry-run the solver and check period repetition for Math and Science.

from collections import defaultdict
from event_generator    import generate_all_events, CLASS_ORDER
from slot_index         import build_slot_index
from conflict_builder   import build_conflict_map
from suitability_matrix import build_suitability_matrix
from placer             import run_placer
from constraints        import NUM_CLASSES, DAYS_PER_WEEK, PERIODS_PER_DAY, PERIOD_NAMES_DISPLAY

TARGET_SUBJECTS = {"Math", "Science"}

def analyze():
    slots, slot_lookup = build_slot_index(NUM_CLASSES, DAYS_PER_WEEK, PERIODS_PER_DAY)
    events = generate_all_events(
        assignments_path="teacher_assignments.yaml",
        subject_load_path="subject_load.yaml",
    )
    conflict_map = build_conflict_map(events)
    suitability  = build_suitability_matrix(events, slot_lookup)

    print("Running solver (dry run — no export) …\n")
    timetable_state, unplaced, _, stats = run_placer(
        events, slots, slot_lookup, suitability, conflict_map
    )

    print(f"\nUnplaced events: {len(unplaced)}")

    # -------------------------------------------------------------------
    # Build per-(class, subject) list of (day, period) placements
    # -------------------------------------------------------------------
    # event_idx → event
    ev_map = {i: e for i, e in enumerate(events)}

    placements_by_class_subj = defaultdict(list)  # (class, subject) → [(day, period), …]
    for (event_idx, instance), placement in timetable_state.items():
        subj = placement["subject"]
        if subj in TARGET_SUBJECTS:
            placements_by_class_subj[(placement["class"], subj)].append(
                (placement["day"], placement["period"])
            )

    DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    print("\n" + "=" * 60)
    print(f"  Period Repetition Report — Math & Science")
    print("=" * 60)

    all_repetitive = True

    for section in CLASS_ORDER:
        for subj in ["Math", "Science"]:
            key = (section, subj)
            entries = placements_by_class_subj.get(key)
            if not entries:
                continue

            periods = [p for _, p in entries]
            days    = [d for d, _ in entries]
            mode_p  = max(set(periods), key=periods.count)
            on_mode = sum(1 for p in periods if p == mode_p)
            total   = len(periods)
            pct     = on_mode / total * 100

            # Build readable per-day string
            day_map = {d: PERIOD_NAMES_DISPLAY[p] for d, p in entries}
            detail  = "  ".join(
                f"{DAY_NAMES[d]}:{PERIOD_NAMES_DISPLAY[p]}"
                for d, p in sorted(entries)
            )

            unique_periods = set(periods)
            is_repetitive  = (len(unique_periods) == 1)

            status = "OK  (same period)" if is_repetitive else "VARY (mixed periods)"
            if not is_repetitive:
                all_repetitive = False

            print(f"\n  {section:>3} {subj:<8}  [{status}]")
            print(f"    Placements : {detail}")
            print(f"    Mode period: {PERIOD_NAMES_DISPLAY[mode_p]}  "
                  f"({on_mode}/{total} instances = {pct:.0f}%)")
            if not is_repetitive:
                print(f"    Unique periods seen: "
                      + ", ".join(PERIOD_NAMES_DISPLAY[p] for p in sorted(unique_periods)))

    print("\n" + "=" * 60)
    if all_repetitive:
        print("  RESULT: All Math & Science instances are 100% repetitive.")
    else:
        print("  RESULT: Some Math/Science instances vary across days.")
        print("  → Consider increasing BACKTRACK_WINDOW in placer.py.")
    print("=" * 60)

if __name__ == "__main__":
    analyze()
