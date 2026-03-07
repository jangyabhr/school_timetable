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

def _mrv_order(events, conflict_map, suitability):
    """
    Sort events by descending constraint density (true MRV):
      - Fixed-slot subjects (CCA, Game) are placed first (fewest available slots)
      - Then by suitability size ascending (fewer allowed slots = more constrained)
      - Then by conflict_count × weekly_load
    Most constrained events are placed first.
    """
    indexed = list(enumerate(events))
    indexed.sort(
        key=lambda x: (
            1 if x[1]["subject"] in FIXED_SLOT_SUBJECTS else 0,
            -len(suitability.get(x[0], [])),   # fewer slots = less negative = higher priority
            _conflict_count(x[0], conflict_map) * x[1]["weekly_load"],
        ),
        reverse=True
    )
    return indexed   # list of (event_idx, event)


# ---------------------------------------------------------------------------
# Greedy Placement
# ---------------------------------------------------------------------------

def _greedy_place(events, slots, slot_lookup, suitability,
                  conflict_map, timetable_state, occupied):
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
            best_slot = scored[0][1]
            _place(event_idx, instance, best_slot, event,
                   timetable_state, occupied)

    return unplaced


# ---------------------------------------------------------------------------
# Repair Pass
# ---------------------------------------------------------------------------

def _repair(unplaced, events, slots, slot_lookup, suitability,
            conflict_map, timetable_state, occupied):
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
                # Re-queue the displaced event
                still_unplaced.append((v_idx, v_inst, events[v_idx]))
                placed = True
                break

            attempts += 1

        if not placed:
            still_unplaced.append((event_idx, instance, event))

    return still_unplaced


# ---------------------------------------------------------------------------
# Limited Backtracking
# ---------------------------------------------------------------------------

def _backtrack(unplaced, events, slots, slot_lookup, suitability,
               conflict_map, timetable_state, occupied, placement_stack):
    """
    Undo the last BACKTRACK_WINDOW placements and retry.
    Only called when repair has failed.
    Returns final unplaced list.
    """
    # Undo recent placements
    for _ in range(min(BACKTRACK_WINDOW, len(placement_stack))):
        if placement_stack:
            key = placement_stack.pop()
            event_idx, instance = key
            unplaced.append((event_idx, instance, events[event_idx]))
            _unplace(event_idx, instance, timetable_state, occupied)

    # Re-sort by MRV priority before retrying (true MRV: fewest allowed slots first)
    unplaced.sort(
        key=lambda x: (
            1 if x[2]["subject"] in FIXED_SLOT_SUBJECTS else 0,
            -len(suitability.get(x[0], [])),
            _conflict_count(x[0], conflict_map) * x[2]["weekly_load"],
        ),
        reverse=True,
    )

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
            _place(event_idx, instance, best_slot, event,
                   timetable_state, occupied)
            placement_stack.append((event_idx, instance))
        else:
            retry_unplaced.append((event_idx, instance, event))

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
    """
    timetable_state = {}
    occupied        = set()   # (class_idx, day, period) already filled
    placement_stack = []

    print("── Phase 1: Greedy placement ──")
    unplaced = _greedy_place(
        events, slots, slot_lookup, suitability,
        conflict_map, timetable_state, occupied
    )
    print(f"   Unplaced after greedy: {len(unplaced)}")

    if unplaced:
        print("── Phase 2: Repair pass ──")
        unplaced = _repair(
            unplaced, events, slots, slot_lookup, suitability,
            conflict_map, timetable_state, occupied
        )
        print(f"   Unplaced after repair: {len(unplaced)}")

    if unplaced:
        print("── Phase 3: Limited backtracking ──")
        # Build placement_stack from current state for backtracker
        placement_stack = list(timetable_state.keys())
        unplaced = _backtrack(
            unplaced, events, slots, slot_lookup, suitability,
            conflict_map, timetable_state, occupied, placement_stack
        )
        print(f"   Unplaced after backtrack: {len(unplaced)}")

    if unplaced:
        print("── WARNING: Some events could not be placed ──")
        for event_idx, instance, event in unplaced:
            print(f"   [{event_idx}] {event['class']} {event['subject']}"
                  f" (instance {instance})")
    else:
        print("── All events placed successfully ──")

    return timetable_state, unplaced, placement_stack
