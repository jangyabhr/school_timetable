# suitability_matrix.py

from constraints import (
    DAYS_PER_WEEK,
    PERIODS_PER_DAY,
    FIXED_SLOTS,
    FLOATING_EXCLUDED_DAYS,
    FLOATING_SINGLE_SUBJECTS,
    LAB_BLOCK_SUBJECTS,
    LAB_ALLOWED_START_PERIODS,
    NON_TEACHING_PERIODS,
)


def build_suitability_matrix(events, slot_lookup):
    """
    Returns a dict: event_idx → list of allowed slot_ids.

    Rules applied per subject type:
    - Fixed-slot subjects (CCA): only their exact (day, period) slots
    - Floating singles (Library, WE): all teaching periods except Tuesday and Saturday
    - Lab subjects (Physics, Chemistry, Biology): LAB_ALLOWED_START_PERIODS only
    - All other subjects: all teaching periods (NON_TEACHING_PERIODS excluded)
    Note: Game, Drill, and Breakfast have no solver events; placed by post_processor.
    """

    suitability = {}

    for i, event in enumerate(events):
        subject  = event["subject"]
        class_idx = event["class_idx"]   # integer index, set during event generation
        allowed_slot_ids = []

        # ── Fixed-slot subjects ──────────────────────────────────────────────
        if subject in FIXED_SLOTS:
            for (day, period) in FIXED_SLOTS[subject]:
                key = (class_idx, day, period)
                if key in slot_lookup:
                    allowed_slot_ids.append(slot_lookup[key])

        # ── Floating singles (Library, WE) ───────────────────────────────────
        elif subject in FLOATING_SINGLE_SUBJECTS:
            for day in range(DAYS_PER_WEEK):
                if day in FLOATING_EXCLUDED_DAYS:
                    continue
                for period in range(PERIODS_PER_DAY):
                    if period in NON_TEACHING_PERIODS:
                        continue
                    key = (class_idx, day, period)
                    if key in slot_lookup:
                        allowed_slot_ids.append(slot_lookup[key])

        # ── Lab double-period subjects ───────────────────────────────────────
        elif subject in LAB_BLOCK_SUBJECTS:
            for day in range(DAYS_PER_WEEK):
                for period in LAB_ALLOWED_START_PERIODS:   # periods 0–6
                    key = (class_idx, day, period)
                    if key in slot_lookup:
                        allowed_slot_ids.append(slot_lookup[key])

        # ── All other subjects ───────────────────────────────────────────────
        else:
            for day in range(DAYS_PER_WEEK):
                for period in range(PERIODS_PER_DAY):
                    if period in NON_TEACHING_PERIODS:
                        continue
                    key = (class_idx, day, period)
                    if key in slot_lookup:
                        allowed_slot_ids.append(slot_lookup[key])

        suitability[i] = allowed_slot_ids

    return suitability
