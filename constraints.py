# constraints.py

# ---------------------------------------------------------------------------
# Timetable Scale Constants
# ---------------------------------------------------------------------------

NUM_CLASSES      = 12   # 6A, 6B, 7A, 7B, 8A, 8B, 9A, 9B, 10A, 10B, 11, 12
DAYS_PER_WEEK    = 6    # Monday=0 … Saturday=5
PERIODS_PER_DAY  = 8    # Periods 0–7

# Day index aliases
MONDAY    = 0
TUESDAY   = 1
WEDNESDAY = 2
THURSDAY  = 3
FRIDAY    = 4
SATURDAY  = 5

# ---------------------------------------------------------------------------
# Hard Constraints
# ---------------------------------------------------------------------------

HARD_CONSTRAINTS = [
    "teacher_no_parallel",    # Teacher cannot be in two classes at the same (day, period)
    "class_no_parallel",      # Class cannot have two subjects at the same (day, period)
    "weekly_load_match",      # Each subject must be placed exactly weekly_load times
    "lab_must_be_double",     # Lab subjects must occupy two consecutive periods on the same day
    "games_tuesday_last",     # Games fixed to Tuesday, last period (period 7)
    "cca_saturday_last_two",  # CCA fixed to Saturday, periods 6 and 7
    "library_we_not_fixed",   # Library and WE can float but not on Tuesday or Saturday
]

# ---------------------------------------------------------------------------
# Soft Constraints  (score deltas used by scoring.py)
# ---------------------------------------------------------------------------

SOFT_CONSTRAINTS = {
    "morning_anchor":        +10,   # Anchor subjects prefer periods 0–2
    "avoid_subject_repeat":   -5,   # Same subject twice in a day for same class
    "teacher_gap":            -3,   # Teacher has back-to-back periods with no break
    "lab_morning_prefer":     +8,   # Lab double-periods prefer morning (periods 0–3)
    "avoid_monday_last":      -4,   # Avoid placing core subjects in last period Monday
}

# ---------------------------------------------------------------------------
# Subject Categories
# ---------------------------------------------------------------------------

ANCHOR_SUBJECTS = [
    "Math",
    "Science",
    "English",
    "SST",
]

LAB_BLOCK_SUBJECTS = [
    "Physics",
    "Chemistry",
    "Biology",
]

# Must each appear exactly once per week; placement is fully fixed by rule
FIXED_SLOT_SUBJECTS = [
    "Game",     # Tuesday, period 7 (last period)
    "CCA",      # Saturday, periods 6–7 (last two periods)
]

# Float freely but excluded from Tuesday and Saturday
FLOATING_SINGLE_SUBJECTS = [
    "Library",
    "WE",
]

# ---------------------------------------------------------------------------
# Fixed Slot Rules
# (used by suitability_matrix.py to lock subjects to exact slots)
# ---------------------------------------------------------------------------

FIXED_SLOTS = {
    # subject → list of (day, period) tuples it is allowed to occupy
    "Game": [
        (TUESDAY, 7),           # All classes: Tuesday last period
    ],
    "CCA": [
        (SATURDAY, 6),          # All classes: Saturday second-to-last period
        (SATURDAY, 7),          # All classes: Saturday last period
    ],
}

# Days on which Library and WE may NOT be placed
FLOATING_EXCLUDED_DAYS = [TUESDAY, SATURDAY]

# ---------------------------------------------------------------------------
# Lab Double-Period Rules
# (used by suitability_matrix.py and the placer)
# ---------------------------------------------------------------------------

# Lab subjects may only START on these periods so the consecutive
# second period does not overflow the day (max start = PERIODS_PER_DAY - 2)
LAB_ALLOWED_START_PERIODS = list(range(2, PERIODS_PER_DAY - 1))  # 2–6 (after 2nd period, 1-indexed)

# ---------------------------------------------------------------------------
# Validation Helper  (used by the validation report step)
# ---------------------------------------------------------------------------

def validate_fixed_slots(timetable_state, events):
    """
    Returns a list of violation strings for any fixed-slot subject
    placed outside its allowed (day, period) positions.
    """
    violations = []
    for event_idx, placement in timetable_state.items():
        subject = events[event_idx]["subject"]
        if subject in FIXED_SLOTS:
            allowed = FIXED_SLOTS[subject]
            actual = (placement["day"], placement["period"])
            if actual not in allowed:
                violations.append(
                    f"Event {event_idx} ({subject}, class "
                    f"{events[event_idx]['class']}) placed at "
                    f"day={placement['day']} period={placement['period']} "
                    f"— expected one of {allowed}"
                )
    return violations
