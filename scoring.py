# scoring.py

from constraints import SOFT_CONSTRAINTS, ANCHOR_SUBJECTS, LAB_BLOCK_SUBJECTS, MONDAY, LAB_ALLOWED_START_PERIODS


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

    # Soft: anchor subjects prefer morning periods (period 0–2)
    if event["subject"] in ANCHOR_SUBJECTS:
        if period <= 2:
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

    # Soft: lab subjects prefer early start after 2nd period (period 2–3)
    if event["subject"] in LAB_BLOCK_SUBJECTS:
        if 2 <= period <= 3:
            score += SOFT_CONSTRAINTS["lab_morning_prefer"]

    # Soft: avoid placing core subjects in last period on Monday
    if day == MONDAY and period == 7:
        if event["subject"] in ANCHOR_SUBJECTS:
            score += SOFT_CONSTRAINTS["avoid_monday_last"]

    return score