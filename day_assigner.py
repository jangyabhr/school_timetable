# day_assigner.py
#
# Given period_assignments {event_idx: period}, assigns specific days to each
# event instance so that:
#   • no teacher is in two places at the same (day, period)
#   • no class has two subjects at the same (day, period)
#   • Library events avoid FLOATING_EXCLUDED_DAYS (Tuesday, Saturday)
#
# Uses backtracking + MRV ordering to handle cases where greedy fails due to
# coupled teacher-class constraints (e.g. a teacher shared across two classes
# at the same period whose required day sets must partition the week).
#
# Feasibility is guaranteed by the period validation in period_generator.py
# (König's theorem: bipartite edge-coloring with Δ ≤ DAYS_PER_WEEK colors).
#
# Output format is identical to the old placer's timetable_state:
#   {(event_idx, instance): {"day", "period", "slot_id", "class",
#                             "class_idx", "subject", "teacher"}}

from collections import defaultdict

from constraints import DAYS_PER_WEEK, FLOATING_SINGLE_SUBJECTS, FLOATING_EXCLUDED_DAYS


def assign_days(events, period_assignments, slot_lookup):
    """
    Assign days to every event instance.

    Args:
        events            — list of event dicts (from event_generator)
        period_assignments — {event_idx: period}  (from period_generator)
        slot_lookup       — {(class_idx, day, period): slot_id}

    Returns:
        timetable_state — {(event_idx, instance): placement_dict}
    """
    timetable_state = {}

    # Group events by assigned period
    by_period = defaultdict(list)
    for event_idx, event in enumerate(events):
        p = period_assignments.get(event_idx)
        if p is not None:
            by_period[p].append((event_idx, event))

    for period, ev_list in sorted(by_period.items()):
        _assign_period(ev_list, period, timetable_state, slot_lookup)

    return timetable_state


def _assign_period(ev_list, period, timetable_state, slot_lookup):
    """
    Assign days for all event instances at a single period.

    Uses MRV-ordered backtracking so coupled teacher-class constraints
    (where greedy ordering would fail) are always resolved correctly.
    """
    # ----- Build instance list ------------------------------------------------
    # Each event's instances are independent; each needs exactly one day.
    excluded_floating = frozenset(FLOATING_EXCLUDED_DAYS)
    all_days = list(range(DAYS_PER_WEEK))

    event_lookup = {}
    instances = []   # (event_idx, inst_no, class_idx, teacher, day_pool)

    for event_idx, event in ev_list:
        event_lookup[event_idx] = event
        if event["subject"] in FLOATING_SINGLE_SUBJECTS:
            pool = [d for d in all_days if d not in excluded_floating]
        else:
            pool = all_days

        for inst in range(event["weekly_load"]):
            instances.append((event_idx, inst, event["class_idx"],
                              event.get("teacher"), pool))

    # ----- Backtracking state -------------------------------------------------
    teacher_days = defaultdict(set)   # teacher → days used at this period
    class_days   = defaultdict(set)   # class_idx → days used at this period
    assignment   = {}                 # (event_idx, inst) → day

    # ----- MRV helper ---------------------------------------------------------
    def count_avail(tup):
        _, _, ci, teacher, pool = tup
        return sum(
            1 for d in pool
            if (teacher is None or d not in teacher_days[teacher])
            and d not in class_days[ci]
        )

    # ----- Backtracking solver ------------------------------------------------
    def backtrack(remaining):
        if not remaining:
            return True

        # Pick most-constrained instance (fewest valid days)
        remaining = sorted(remaining, key=count_avail)
        tup       = remaining[0]
        rest      = remaining[1:]

        event_idx, inst_no, ci, teacher, pool = tup

        for d in pool:
            if teacher and d in teacher_days[teacher]:
                continue
            if d in class_days[ci]:
                continue

            # Assign day d
            assignment[(event_idx, inst_no)] = d
            if teacher:
                teacher_days[teacher].add(d)
            class_days[ci].add(d)

            if backtrack(rest):
                return True

            # Undo
            del assignment[(event_idx, inst_no)]
            if teacher:
                teacher_days[teacher].discard(d)
            class_days[ci].discard(d)

        return False   # dead end — caller must backtrack further

    # ----- Solve and record ---------------------------------------------------
    ok = backtrack(instances)
    if not ok:
        print(f"  WARNING day_assigner: backtracking exhausted at P{period + 1} "
              f"— some instances could not be placed")

    for (event_idx, inst_no), day in assignment.items():
        event = event_lookup[event_idx]
        ci    = event["class_idx"]
        timetable_state[(event_idx, inst_no)] = {
            "day":       day,
            "period":    period,
            "slot_id":   slot_lookup[(ci, day, period)],
            "class":     event["class"],
            "class_idx": ci,
            "subject":   event["subject"],
            "teacher":   event.get("teacher"),
        }
