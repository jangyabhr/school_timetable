# placer.py

from scoring import score_slot
from constraints import (
    DAYS_PER_WEEK,
    PERIODS_PER_DAY,
    LAB_BLOCK_SUBJECTS,
    FIXED_SLOT_SUBJECTS,
    FIXED_SLOTS,
)

MAX_REPAIR_ATTEMPTS = 20   # per unplaced event-instance
BACKTRACK_WINDOW    = 30   # how many recent placements to undo on backtrack


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conflict_count(event_idx, conflict_map):
    return len(conflict_map.get(event_idx, set()))


def _candidate_slots(event, event_idx, slots, slot_lookup,
                     suitability, conflict_map, timetable_state,
                     occupied):
    """
    Returns all slots that pass hard constraints for this event:
      1. slot_id is in suitability[event_idx]
      2. the class's (day, period) is not already occupied
      3. no conflicting event is placed at the same (day, period)
    """
    allowed = set(suitability.get(event_idx, []))
    candidates = []

    for slot_id in allowed:
        slot = slots[slot_id]
        day, period = slot["day"], slot["period"]

        # Class already has a subject this period
        if (event["class_idx"], day, period) in occupied:
            continue

        # Conflicting event placed at same (day, period)
        blocked = False
        for ci in conflict_map.get(event_idx, set()):
            p = timetable_state.get((ci, 0))   # first instance
            # check all instances of conflicting event
            for inst_key, placement in timetable_state.items():
                if inst_key[0] == ci:
                    if placement["day"] == day and placement["period"] == period:
                        blocked = True
                        break
            if blocked:
                break

        if not blocked:
            candidates.append(slot)

    return candidates


def _place(event_idx, instance, slot, event, timetable_state, occupied):
    """Record a placement in timetable_state and occupied set."""
    key = (event_idx, instance)
    timetable_state[key] = {
        "day":      slot["day"],
        "period":   slot["period"],
        "slot_id":  slot["slot_id"],
        "class":    event["class"],
        "class_idx":event["class_idx"],
        "subject":  event["subject"],
        "teacher":  event["teacher"],
    }
    occupied.add((event["class_idx"], slot["day"], slot["period"]))


def _unplace(event_idx, instance, timetable_state, occupied):
    """Remove a placement from timetable_state and occupied set."""
    key = (event_idx, instance)
    if key in timetable_state:
        p = timetable_state.pop(key)
        occupied.discard((p["class_idx"], p["day"], p["period"]))


# ---------------------------------------------------------------------------
# MRV Sort
# ---------------------------------------------------------------------------

def _teacher_total_load(events):
    """Returns dict: teacher_name → total weekly periods across all their events."""
    load = {}
    for event in events:
        t = event.get("teacher")
        if t:
            load[t] = load.get(t, 0) + event["weekly_load"]
    return load


_LAB_SUBJECT_PRIORITY = {"Physics": 2, "Chemistry": 1, "Biology": 0}


def _mrv_order(events, conflict_map, suitability):
    """
    Sort events into three groups, in this order:
      1. Fixed-slot subjects (CCA, Game) — must go first
      2. Lab subjects (Physics > Chemistry > Biology) — grouped by subject across all
         classes so that same-teacher lab events are placed consecutively; within each
         subject, higher class_idx first
      3. Regular subjects — sorted by teacher load DESC, class_idx DESC,
         fewest suitability slots first, highest conflict×load first, lower event_idx first
    """
    teacher_load = _teacher_total_load(events)
    indexed = list(enumerate(events))

    fixed   = [(i, e) for i, e in indexed if e["subject"] in FIXED_SLOT_SUBJECTS]
    labs    = [(i, e) for i, e in indexed if e["subject"] in LAB_BLOCK_SUBJECTS]
    regular = [(i, e) for i, e in indexed
               if e["subject"] not in FIXED_SLOT_SUBJECTS
               and e["subject"] not in LAB_BLOCK_SUBJECTS]

    # Fixed slots: higher class_idx first
    fixed.sort(key=lambda x: x[1]["class_idx"], reverse=True)

    # Labs: Physics first, then Chemistry, then Biology; within same subject higher class first
    labs.sort(
        key=lambda x: (_LAB_SUBJECT_PRIORITY.get(x[1]["subject"], 0), x[1]["class_idx"]),
        reverse=True,
    )

    # Regular: standard MRV keys
    regular.sort(
        key=lambda x: (
            teacher_load.get(x[1].get("teacher"), 0),
            x[1]["class_idx"],
            -len(suitability.get(x[0], [])),
            _conflict_count(x[0], conflict_map) * x[1]["weekly_load"],
            -x[0],
        ),
        reverse=True,
    )

    return fixed + labs + regular


# ---------------------------------------------------------------------------
# Greedy Placement
# ---------------------------------------------------------------------------

def _greedy_place(events, slots, slot_lookup, suitability,
                  conflict_map, timetable_state, occupied, stats):
    """
    Place all event instances greedily in MRV order.
    Returns list of (event_idx, instance, event) tuples that could not be placed.
    """
    unplaced = []
    order = _mrv_order(events, conflict_map, suitability)

    for event_idx, event in order:
        for instance in range(event["weekly_load"]):

            candidates = _candidate_slots(
                event, event_idx, slots, slot_lookup,
                suitability, conflict_map, timetable_state, occupied
            )

            if not candidates:
                unplaced.append((event_idx, instance, event))
                continue

            # Score all candidates, pick best
            scored = []
            for slot in candidates:
                s = score_slot(event, slot, timetable_state,
                               suitability, conflict_map, event_idx)
                if s is not None:
                    scored.append((s, slot))

            if not scored:
                unplaced.append((event_idx, instance, event))
                continue

            scored.sort(key=lambda x: x[0], reverse=True)
            best_score = scored[0][0]
            best_slot  = scored[0][1]
            stats["scores"].append(best_score)
            stats["phase1_placed"] += 1
            _place(event_idx, instance, best_slot, event,
                   timetable_state, occupied)

    stats["phase1_unplaced"] = len(unplaced)
    return unplaced


# ---------------------------------------------------------------------------
# Repair Pass
# ---------------------------------------------------------------------------

def _repair(unplaced, events, slots, slot_lookup, suitability,
            conflict_map, timetable_state, occupied, stats):
    """
    For each unplaced event-instance, try to displace a lower-priority
    placed event to make room.
    Returns still-unplaced list after repair attempts.
    """
    still_unplaced = []

    for event_idx, instance, event in unplaced:
        placed = False
        attempts = 0

        candidates = _candidate_slots(
            event, event_idx, slots, slot_lookup,
            suitability, conflict_map, timetable_state, occupied
        )

        for slot in candidates:
            if attempts >= MAX_REPAIR_ATTEMPTS:
                break

            day, period = slot["day"], slot["period"]

            # Find a placed event in this slot for the same class that
            # has a lower score than our event would score here
            victim_key = None
            victim_score = None
            my_score = score_slot(event, slot, timetable_state,
                                  suitability, conflict_map, event_idx)
            if my_score is None:
                attempts += 1
                stats["phase2_repair_attempts"] += 1
                continue

            for key, placement in list(timetable_state.items()):
                if (placement["class_idx"] == event["class_idx"]
                        and placement["day"] == day
                        and placement["period"] == period):
                    v_idx, v_inst = key
                    v_score = score_slot(
                        events[v_idx], slot, timetable_state,
                        suitability, conflict_map, v_idx
                    )
                    if v_score is not None and v_score < my_score:
                        victim_key = key
                        victim_score = v_score
                    break

            if victim_key:
                v_idx, v_inst = victim_key
                _unplace(v_idx, v_inst, timetable_state, occupied)
                _place(event_idx, instance, slot, event,
                       timetable_state, occupied)
                stats["phase2_swaps"] += 1
                stats["scores"].append(my_score)
                # Re-queue the displaced event
                still_unplaced.append((v_idx, v_inst, events[v_idx]))
                placed = True
                break

            attempts += 1
            stats["phase2_repair_attempts"] += 1

        if not placed:
            still_unplaced.append((event_idx, instance, event))

    stats["phase2_unplaced"] = len(still_unplaced)
    return still_unplaced


# ---------------------------------------------------------------------------
# Limited Backtracking
# ---------------------------------------------------------------------------

def _backtrack(unplaced, events, slots, slot_lookup, suitability,
               conflict_map, timetable_state, occupied, placement_stack, stats):
    """
    Undo the last BACKTRACK_WINDOW placements and retry.
    Only called when repair has failed.
    Returns final unplaced list.
    """
    # Undo recent placements
    n_undo = min(BACKTRACK_WINDOW, len(placement_stack))
    stats["phase3_undone"] = n_undo
    for _ in range(n_undo):
        if placement_stack:
            key = placement_stack.pop()
            event_idx, instance = key
            unplaced.append((event_idx, instance, events[event_idx]))
            _unplace(event_idx, instance, timetable_state, occupied)

    # Re-sort by MRV priority before retrying (same three-group order as _mrv_order)
    _tload = _teacher_total_load(events)
    fixed_u   = [(ei, ins, ev) for ei, ins, ev in unplaced if ev["subject"] in FIXED_SLOT_SUBJECTS]
    labs_u    = [(ei, ins, ev) for ei, ins, ev in unplaced if ev["subject"] in LAB_BLOCK_SUBJECTS]
    regular_u = [(ei, ins, ev) for ei, ins, ev in unplaced
                 if ev["subject"] not in FIXED_SLOT_SUBJECTS
                 and ev["subject"] not in LAB_BLOCK_SUBJECTS]
    fixed_u.sort(key=lambda x: x[2]["class_idx"], reverse=True)
    labs_u.sort(key=lambda x: (_LAB_SUBJECT_PRIORITY.get(x[2]["subject"], 0), x[2]["class_idx"]), reverse=True)
    regular_u.sort(
        key=lambda x: (
            _tload.get(x[2].get("teacher"), 0),
            x[2]["class_idx"],
            -len(suitability.get(x[0], [])),
            _conflict_count(x[0], conflict_map) * x[2]["weekly_load"],
            -x[0],
        ),
        reverse=True,
    )
    unplaced = fixed_u + labs_u + regular_u

    # Retry greedily on the freed events
    retry_unplaced = []
    for event_idx, instance, event in unplaced:
        candidates = _candidate_slots(
            event, event_idx, slots, slot_lookup,
            suitability, conflict_map, timetable_state, occupied
        )
        scored = []
        for slot in candidates:
            s = score_slot(event, slot, timetable_state,
                           suitability, conflict_map, event_idx)
            if s is not None:
                scored.append((s, slot))

        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            best_slot = scored[0][1]
            stats["scores"].append(scored[0][0])
            _place(event_idx, instance, best_slot, event,
                   timetable_state, occupied)
            placement_stack.append((event_idx, instance))
        else:
            retry_unplaced.append((event_idx, instance, event))

    stats["phase3_unplaced"] = len(retry_unplaced)
    return retry_unplaced


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def run_placer(events, slots, slot_lookup, suitability, conflict_map):
    """
    Full placement pipeline:
      1. Greedy (MRV order)
      2. Repair pass
      3. Limited backtracking (if repair still leaves unplaced events)

    Returns:
      timetable_state  — dict: (event_idx, instance) → placement dict
      unplaced         — list of event-instances that could not be placed
      placement_stack  — ordered list of placed keys (for audit/debug)
      stats            — solver statistics dict
    """
    timetable_state = {}
    occupied        = set()   # (class_idx, day, period) already filled
    placement_stack = []

    stats = {
        "phase1_placed":          0,
        "phase1_unplaced":        0,
        "phase2_ran":             False,
        "phase2_repair_attempts": 0,
        "phase2_swaps":           0,
        "phase2_unplaced":        0,
        "phase3_ran":             False,
        "phase3_undone":          0,
        "phase3_unplaced":        0,
        "scores":                 [],
    }

    print("── Phase 1: Greedy placement ──")
    unplaced = _greedy_place(
        events, slots, slot_lookup, suitability,
        conflict_map, timetable_state, occupied, stats
    )
    print(f"   Placed: {stats['phase1_placed']}  |  Unplaced: {len(unplaced)}")

    if unplaced:
        stats["phase2_ran"] = True
        print("── Phase 2: Repair pass ──")
        unplaced = _repair(
            unplaced, events, slots, slot_lookup, suitability,
            conflict_map, timetable_state, occupied, stats
        )
        print(f"   Swaps: {stats['phase2_swaps']}  |  Slots tried: {stats['phase2_repair_attempts']}  |  Still unplaced: {len(unplaced)}")

    if unplaced:
        stats["phase3_ran"] = True
        print("── Phase 3: Limited backtracking ──")
        placement_stack = list(timetable_state.keys())
        unplaced = _backtrack(
            unplaced, events, slots, slot_lookup, suitability,
            conflict_map, timetable_state, occupied, placement_stack, stats
        )
        print(f"   Undone: {stats['phase3_undone']}  |  Unplaced after backtrack: {len(unplaced)}")

    if unplaced:
        print("── WARNING: Some events could not be placed ──")
        for event_idx, instance, event in unplaced:
            print(f"   [{event_idx}] {event['class']} {event['subject']}"
                  f" (instance {instance})")
    else:
        print("── All events placed successfully ──")

    return timetable_state, unplaced, placement_stack, stats
