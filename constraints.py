# constraints.py

# ---------------------------------------------------------------------------
# Timetable Scale Constants
# ---------------------------------------------------------------------------

NUM_CLASSES      = 12   # 6A, 6B, 7A, 7B, 8A, 8B, 9A, 9B, 10A, 10B, 11, 12
DAYS_PER_WEEK    = 6    # Monday=0 … Saturday=5
PERIODS_PER_DAY  = 6    # 6 teaching periods per day (no Drill, no Breakfast)

# ---------------------------------------------------------------------------
# Period Map (April schedule — 6:40 to 10:10)
# Index 0  — P1   06:40–07:20   teaching  (40 min)
# Index 1  — P2   07:20–08:00   teaching  (40 min)
# Index 2  — P3   08:00–08:40   teaching  (40 min)
# Index 3  — P4   08:40–09:10   teaching  (30 min)
# Index 4  — P5   09:10–09:40   teaching  (30 min)
# Index 5  — P6   09:40–10:10   teaching  (30 min)  (last)
# ---------------------------------------------------------------------------
TEACHING_PERIODS = list(range(PERIODS_PER_DAY))   # [0, 1, 2, 3, 4, 5]

PERIOD_NAMES_DISPLAY = ["P1", "P2", "P3", "P4", "P5", "P6"]
PERIOD_TIMES = [
    "6:40–7:20",   # P1
    "7:20–8:00",   # P2
    "8:00–8:40",   # P3
    "8:40–9:10",   # P4
    "9:10–9:40",   # P5
    "9:40–10:10",  # P6
]

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
]

# ---------------------------------------------------------------------------
# Soft Constraints  (score deltas used by scoring.py)
# ---------------------------------------------------------------------------

SOFT_CONSTRAINTS = {
    "morning_anchor":        +10,   # Anchor subjects prefer periods 0–2 (40-min periods)
    "avoid_subject_repeat":  -20,   # Same subject twice in a day for same class
    "teacher_gap":            -3,   # Teacher has back-to-back periods with no break
    "lab_morning_prefer":     +8,   # Lab double-periods prefer morning (periods 0–1)
    "avoid_monday_last":      -4,   # Avoid placing core subjects in last period Monday
    "period_repeat":         +18,   # Core subject lands on same period as existing instances
    "period_near_repeat":     +8,   # Core subject lands within 1 period of existing mode
    "avoid_last_period":     -10,   # Core subjects avoid period 5 (last period) any day
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

# ---------------------------------------------------------------------------
# Fixed Slot Rules
# (CCA removed — no fixed-slot subjects remain in the solver)
# ---------------------------------------------------------------------------

FIXED_SLOTS = {}

# ---------------------------------------------------------------------------
# Lab Double-Period Rules
# (used by suitability_matrix.py and the placer)
# ---------------------------------------------------------------------------

# Lab subjects may only START on these periods so the consecutive second period
# does not overflow the day.
# All 6 periods are teaching periods; valid starts: 0–4 (period 5 has no period 6).
LAB_ALLOWED_START_PERIODS = [0, 1, 2, 3, 4]

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
