# constraints.py

# ---------------------------------------------------------------------------
# Timetable Scale Constants
# ---------------------------------------------------------------------------

NUM_CLASSES      = 12   # 6A, 6B, 7A, 7B, 8A, 8B, 9A, 9B, 10A, 10B, 11, 12
DAYS_PER_WEEK    = 6    # Monday=0 … Saturday=5
PERIODS_PER_DAY  = 8    # 8 display rows per day (see period map below)

# ---------------------------------------------------------------------------
# Period Map (April schedule)
# Index 0  — Drill/Yoga   07:00–07:30   non-teaching, no teacher
# Index 1  — P1           07:30–08:10   teaching
# Index 2  — P2           08:10–08:50   teaching
# Index 3  — Breakfast    08:50–09:40   non-teaching, break
# Index 4  — P3           09:40–10:20   teaching
# Index 5  — P4           10:20–11:00   teaching
# Index 6  — P5           11:00–11:40   teaching
# Index 7  — P6           11:40–12:20   teaching  (last)
# ---------------------------------------------------------------------------
DRILL_PERIOD         = 0
BREAK_PERIOD         = 3
NON_TEACHING_PERIODS = [DRILL_PERIOD, BREAK_PERIOD]   # never scheduled by solver
TEACHING_PERIODS     = [p for p in range(PERIODS_PER_DAY) if p not in NON_TEACHING_PERIODS]

PERIOD_NAMES_DISPLAY = ["Drill", "P1", "P2", "Break", "P3", "P4", "P5", "P6"]
PERIOD_TIMES = [
    "7:00–7:30",   # Drill
    "7:30–8:10",   # P1
    "8:10–8:50",   # P2
    "8:50–9:40",   # Breakfast
    "9:40–10:20",  # P3
    "10:20–11:00", # P4
    "11:00–11:40", # P5
    "11:40–12:20", # P6
]

# Subjects placed by post_processor as non-teachable markers (no duty teacher assigned)
NON_SUBJECT_MARKERS = ["Drill", "Breakfast"]

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
    "cca_saturday_last_two",  # CCA fixed to Saturday, periods 6 and 7
    "library_we_not_fixed",   # Library and WE can float but not on Tuesday or Saturday
]

# ---------------------------------------------------------------------------
# Soft Constraints  (score deltas used by scoring.py)
# ---------------------------------------------------------------------------

SOFT_CONSTRAINTS = {
    "morning_anchor":        +10,   # Anchor subjects prefer periods 0–2
    "avoid_subject_repeat":  -20,   # Same subject twice in a day for same class
    "teacher_gap":            -3,   # Teacher has back-to-back periods with no break
    "lab_morning_prefer":     +8,   # Lab double-periods prefer morning (periods 0–3)
    "avoid_monday_last":      -4,   # Avoid placing core subjects in last period Monday
    "period_repeat":         +18,   # Core subject lands on same period as existing instances
    "period_near_repeat":     +8,   # Core subject lands within 1 period of existing mode
    "avoid_last_period":     -10,   # Core subjects avoid period 7 (last period) any day
    "period_repeat_priority": +8,   # Math/Science get extra bonus for landing on their mode period
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

# Subjects that benefit from spaced-repetition across days
DAY_SPREAD_SUBJECTS = [
    "Math",
    "Science",
]

LAB_BLOCK_SUBJECTS = [
    "Physics",
    "Chemistry",
    "Biology",
]

# CCA placement is fully fixed by rule; Game is placed by post-processing
FIXED_SLOT_SUBJECTS = [
    "Game",     # Placed by post_processor (latest free period, any day)
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
    # Game is NOT listed here; it has no solver event and is placed by post_processor
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

# Lab subjects may only START on these periods so the consecutive second period
# does not land on a non-teaching slot or overflow the day.
# Valid teaching pairs: (1,2), (4,5), (5,6), (6,7) — period 3 (Breakfast) splits morning from afternoon.
LAB_ALLOWED_START_PERIODS = [1, 4, 5, 6]

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
