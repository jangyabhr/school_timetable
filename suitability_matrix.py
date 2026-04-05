# suitability_matrix.py

from constraints import (
    DAYS_PER_WEEK,
    PERIODS_PER_DAY,
    FIXED_SLOTS,
    LAB_BLOCK_SUBJECTS,
    LAB_ALLOWED_START_PERIODS,
)


def build_suitability_matrix(events, slot_lookup):
    """
    Returns a dict: event_idx → list of allowed slot_ids.

    Rules applied per subject type:
    - Fixed-slot subjects: only their exact (day, period) slots (none currently)
    - Lab subjects (Physics, Chemistry, Biology): LAB_ALLOWED_START_PERIODS only
    - All other subjects: all 6 teaching periods (all periods are teaching)
    Note: Free slots are filled by post_processor, not the solver.
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

        # ── Lab double-period subjects ───────────────────────────────────────
        elif subject in LAB_BLOCK_SUBJECTS:
            for day in range(DAYS_PER_WEEK):
                for period in LAB_ALLOWED_START_PERIODS:
                    key = (class_idx, day, period)
                    if key in slot_lookup:
                        allowed_slot_ids.append(slot_lookup[key])

        # ── All other subjects ───────────────────────────────────────────────
        else:
            for day in range(DAYS_PER_WEEK):
                for period in range(PERIODS_PER_DAY):
                    key = (class_idx, day, period)
                    if key in slot_lookup:
                        allowed_slot_ids.append(slot_lookup[key])

        suitability[i] = allowed_slot_ids

    return suitability
