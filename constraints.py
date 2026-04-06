# constraints.py

# ---------------------------------------------------------------------------
# Timetable Scale Constants
# ---------------------------------------------------------------------------

NUM_CLASSES      = 9    # 7A, 7B, 8A, 8B, 9A, 9B, 10A, 10B, 12
DAYS_PER_WEEK    = 6    # Monday=0 … Saturday=5
PERIODS_PER_DAY  = 4    # 4 teaching periods per day

# ---------------------------------------------------------------------------
# Period Map (schedule — 7:10 to 10:00)
# Index 0  — P1   07:10–07:50   teaching  (40 min)
# Index 1  — P2   07:50–08:30   teaching  (40 min)
# Index 2  — P3   08:40–09:20   teaching  (40 min)  [after 10-min break]
# Index 3  — P4   09:20–10:00   teaching  (40 min)  (last)
# ---------------------------------------------------------------------------
TEACHING_PERIODS = list(range(PERIODS_PER_DAY))   # [0, 1, 2, 3]

PERIOD_NAMES_DISPLAY = ["P1", "P2", "P3", "P4"]
PERIOD_TIMES = [
    "7:10–7:50",   # P1
    "7:50–8:30",   # P2
    "8:40–9:20",   # P3
    "9:20–10:00",  # P4
]

# Day index aliases
MONDAY    = 0
TUESDAY   = 1
WEDNESDAY = 2
THURSDAY  = 3
FRIDAY    = 4
SATURDAY  = 5

# ---------------------------------------------------------------------------
# Hard Constraints  (enforced in suitability_matrix.py, placer.py, scoring.py)
# ---------------------------------------------------------------------------
# • teacher_no_parallel  — same teacher cannot be in two classes at same (day, period)
# • class_no_parallel    — same class cannot have two subjects at same (day, period)
# • weekly_load_match    — each event must be placed exactly weekly_load times
# • library_not_fixed    — Library floats freely but not on Tuesday or Saturday
# • section_period_lock  — (section, subject) pairs in SECTION_PERIOD_LOCKS are
#                          restricted to their declared period index (see below)

# ---------------------------------------------------------------------------
# Soft Constraints  (score deltas used by scoring.py)
# ---------------------------------------------------------------------------

SOFT_CONSTRAINTS = {
    "morning_anchor":        +10,   # Anchor subjects prefer periods 0–1 (first two of four)
    "avoid_subject_repeat":  -20,   # Same subject twice in a day for same class
    "teacher_gap":            -3,   # Teacher has back-to-back periods with no break
    "lab_morning_prefer":     +8,   # Lab double-periods prefer morning (periods 0–1)
    "avoid_monday_last":      -4,   # Avoid placing core subjects in last period Monday
    "period_repeat":         +18,   # Core subject lands on same period as existing instances
    "period_near_repeat":     +8,   # Core subject lands within 1 period of existing mode
    "avoid_last_period":     -10,   # Core subjects avoid period 3 (last period) any day
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

FIXED_SLOT_SUBJECTS = []   # No fixed-slot subjects currently

# Library has been removed from the schedule; no floating subjects remain.
FLOATING_SINGLE_SUBJECTS = []

# ---------------------------------------------------------------------------
# Fixed Slot Rules
# (CCA removed — no fixed-slot subjects remain in the solver)
# ---------------------------------------------------------------------------

FIXED_SLOTS = {}

# Per-(section, subject) period restrictions applied in suitability_matrix.py.
# Key: (section_name, subject_name) → list of allowed period indices (0-based).
# Period 0 = P1 (07:10–07:50), period 1 = P2 (07:50–08:30), etc.
SECTION_PERIOD_LOCKS = {
    ("12",  "Biology"): [0],   # Biology class 12 always in P1
    ("9A",  "Math"):    [0],   # Math 9A always in P1
    ("9B",  "English"): [0],   # English 9B always in P1
    ("12",  "Math"):    [1],   # Math class 12 always in P2
}

# Days on which Library and WE may NOT be placed
FLOATING_EXCLUDED_DAYS = [TUESDAY, SATURDAY]

# ---------------------------------------------------------------------------
# Lab Double-Period Rules
# (used by suitability_matrix.py and the placer)
# ---------------------------------------------------------------------------

# Lab subjects may only START on these periods so the consecutive second period
# does not overflow the day.
# All 4 periods are teaching periods; valid starts: 0–2 (period 3 has no period 4).
LAB_ALLOWED_START_PERIODS = [0, 1, 2]

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
