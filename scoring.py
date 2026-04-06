# scoring.py

from constraints import (
    SOFT_CONSTRAINTS, ANCHOR_SUBJECTS, LAB_BLOCK_SUBJECTS, MONDAY,
    DAY_SPREAD_SUBJECTS as PERIOD_PRIORITY_SUBJECTS,
    PERIODS_PER_DAY,
)

# Subjects for which period-repetition is enforced
_REPETITION_SUBJECTS = (
    ANCHOR_SUBJECTS
    + LAB_BLOCK_SUBJECTS
    + ["IT", "Hindi", "Odia", "Sanskrit", "CS"]
)


def score_slot(event, slot, timetable_state, suitability, conflict_map, event_idx):
    """
    Returns a numeric score. Higher = better placement.
    Returns None if slot is infeasible (hard constraint violation).

    timetable_state keys are (event_idx, instance) tuples.
    """

    # Hard constraint: slot must be in suitability list
    if slot["slot_id"] not in suitability.get(event_idx, []):
        return None

    # Hard constraint: no conflicting event already placed here
    day, period = slot["day"], slot["period"]
    for conflicting_event_idx in conflict_map.get(event_idx, set()):
        for (e_idx, instance), placement in timetable_state.items():
            if e_idx == conflicting_event_idx:
                if placement["day"] == day and placement["period"] == period:
                    return None  # Hard block

    score = 0

    # Soft: anchor subjects prefer first two periods (P1–P2, indices 0–1)
    if event["subject"] in ANCHOR_SUBJECTS:
        if period in [0, 1]:
            score += SOFT_CONSTRAINTS["morning_anchor"]

    # Soft: penalise same subject appearing twice in a day for same class
    same_day_subjects = [
        placement["subject"]
        for (e_idx, instance), placement in timetable_state.items()
        if placement["day"] == day
        and placement["class"] == event["class"]
    ]
    if event["subject"] in same_day_subjects:
        score += SOFT_CONSTRAINTS["avoid_subject_repeat"]

    # Soft: penalise teacher having back-to-back periods with no gap
    if event["teacher"]:
        teacher_periods_today = sorted([
            placement["period"]
            for (e_idx, instance), placement in timetable_state.items()
            if placement.get("teacher") == event["teacher"]
            and placement["day"] == day
        ])
        if teacher_periods_today and (period - 1) in teacher_periods_today:
            score += SOFT_CONSTRAINTS["teacher_gap"]

    # Soft: lab subjects prefer early morning start (period 0 = P1→P2, or period 1 = P2→P3)
    if event["subject"] in LAB_BLOCK_SUBJECTS:
        if period in [0, 1]:
            score += SOFT_CONSTRAINTS["lab_morning_prefer"]

    # Soft: avoid placing core subjects in last period (any day)
    if period == PERIODS_PER_DAY - 1 and event["subject"] in _REPETITION_SUBJECTS:
        score += SOFT_CONSTRAINTS["avoid_last_period"]
    if day == MONDAY and period == PERIODS_PER_DAY - 1 and event["subject"] in ANCHOR_SUBJECTS:
        score += SOFT_CONSTRAINTS["avoid_monday_last"]

    # Soft: reward placing core subjects at the same period as existing instances
    # (drives "Math always at P1" style repetition).
    # Math/Science get an extra bonus on top to strengthen their period lock.
    if event["subject"] in _REPETITION_SUBJECTS:
        existing_periods = [
            p["period"]
            for (e_idx, _inst), p in timetable_state.items()
            if e_idx == event_idx
        ]
        if existing_periods:
            mode_period = max(set(existing_periods), key=existing_periods.count)
            if period == mode_period:
                score += SOFT_CONSTRAINTS["period_repeat"]
                if event["subject"] in PERIOD_PRIORITY_SUBJECTS:
                    score += SOFT_CONSTRAINTS["period_repeat_priority"]
            elif abs(period - mode_period) == 1:
                score += SOFT_CONSTRAINTS["period_near_repeat"]

    return score
