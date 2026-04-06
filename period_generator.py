# period_generator.py
#
# Assigns each event to a fixed period (teacher-centric uniformity).
# Each subject for a class section always appears at the same period every day.
#
# Workflow:
#   generate_period_assignments(events)  → {event_idx: period}
#   validate_period_assignments(...)     → [violation strings]
#   save_period_assignments(...)         → writes period_assignments.yaml
#   load_period_assignments(...)         → reads period_assignments.yaml
#
# Period capacity constraint:
#   For any (teacher, period) or (class, period): sum(weekly_loads) ≤ DAYS_PER_WEEK
#   This guarantees the day assigner can always find a valid day for each instance.
#
# Algorithm:
#   Phase 1 — seed SECTION_PERIOD_LOCKS (hard assignments)
#   Phase 2 — backtracking CSP with MRV ordering for remaining events
#              (guarantees a solution is found if one exists; greedy alone
#               cannot handle tight teacher×class capacity interactions)

from collections import defaultdict

import yaml

from constraints import (
    DAYS_PER_WEEK,
    PERIODS_PER_DAY,
    LAB_BLOCK_SUBJECTS,
    SECTION_PERIOD_LOCKS,
    FLOATING_SINGLE_SUBJECTS,
    ANCHOR_SUBJECTS,
)
from event_generator import CLASS_ORDER


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _valid_periods(event, teacher_period_load, class_period_load):
    """Return list of period indices that satisfy all hard constraints for event."""
    load    = event["weekly_load"]
    subject = event["subject"]
    teacher = event.get("teacher")

    # With 4 periods/day, labs are single-period — all periods are valid starts
    upper = PERIODS_PER_DAY

    valid = []
    for p in range(upper):
        if teacher and teacher_period_load[(teacher, p)] + load > DAYS_PER_WEEK:
            continue
        if class_period_load[(event["class"], p)] + load > DAYS_PER_WEEK:
            continue
        valid.append(p)

    return valid


def _period_score(p, event, teacher_period_load, class_period_load):
    """
    Higher score = more preferred.
    Prefer morning for anchor subjects; avoid last period for core subjects;
    favour less-loaded periods to spread events evenly.
    """
    t      = event.get("teacher")
    tl     = teacher_period_load[(t, p)] if t else 0
    cl     = class_period_load[(event["class"], p)]
    crowd  = -(tl + cl)

    if p <= 2 and event["subject"] in ANCHOR_SUBJECTS:
        morning = 4
    elif p <= 2:
        morning = 2
    else:
        morning = 0

    last = -4 if p == PERIODS_PER_DAY - 1 else 0

    return morning + last + crowd


# ---------------------------------------------------------------------------
# Backtracking CSP
# ---------------------------------------------------------------------------

def _backtrack(pending, assignments, teacher_period_load, class_period_load):
    """
    Assign each event in `pending` to a period using MRV + chronological backtracking.

    pending — list of (event_idx, event) not yet assigned
    Modifies assignments, teacher_period_load, class_period_load in-place.
    Returns True on success, False if the sub-problem is infeasible.
    """
    if not pending:
        return True

    # MRV: pick the event with fewest valid period options
    pending = sorted(pending, key=lambda x: (
        len(_valid_periods(x[1], teacher_period_load, class_period_load)),
        -x[1]["weekly_load"],   # tie-break: higher load first
        -x[1]["class_idx"],     # tie-break: higher class_idx first
    ))

    event_idx, event = pending[0]
    rest = pending[1:]

    valid = _valid_periods(event, teacher_period_load, class_period_load)
    if not valid:
        return False    # dead end — no period can accommodate this event

    # Try periods best-score first
    valid.sort(key=lambda p: -_period_score(p, event, teacher_period_load, class_period_load))

    t    = event.get("teacher")
    cls  = event["class"]
    load = event["weekly_load"]

    for p in valid:
        # Assign
        assignments[event_idx] = p
        if t:
            teacher_period_load[(t, p)] += load
        class_period_load[(cls, p)] += load

        if _backtrack(rest, assignments, teacher_period_load, class_period_load):
            return True

        # Undo
        del assignments[event_idx]
        if t:
            teacher_period_load[(t, p)] -= load
        class_period_load[(cls, p)] -= load

    return False    # exhausted all options — caller must backtrack further


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

def generate_period_assignments(events):
    """
    Assign every event to a fixed period.

    Returns:
        assignments         — {event_idx: period}
        teacher_period_load — {(teacher, period): total_weekly_load}
        class_period_load   — {(class_name, period): total_weekly_load}
    """
    assignments         = {}
    teacher_period_load = defaultdict(int)
    class_period_load   = defaultdict(int)

    # --- Phase 1: seed from SECTION_PERIOD_LOCKS ---
    for i, event in enumerate(events):
        key = (event["class"], event["subject"])
        if key in SECTION_PERIOD_LOCKS:
            p = SECTION_PERIOD_LOCKS[key][0]
            assignments[i] = p
            t = event.get("teacher")
            if t:
                teacher_period_load[(t, p)] += event["weekly_load"]
            class_period_load[(event["class"], p)] += event["weekly_load"]

    # --- Phase 2: backtracking CSP for remaining events ---
    # Floating subjects (Library) assigned separately in Phase 3 if present.
    pending = [
        (i, e) for i, e in enumerate(events)
        if i not in assignments and e["subject"] not in FLOATING_SINGLE_SUBJECTS
    ]

    ok = _backtrack(pending, assignments, teacher_period_load, class_period_load)
    if not ok:
        print("  PERIOD GEN ERROR: backtracking failed — no valid period assignment exists.")
        print("  Check teacher loads and class subject counts against DAYS_PER_WEEK capacity.")

    # --- Phase 3: floating events (Library) — assign to period with most remaining room ---
    for event_idx, event in enumerate(events):
        if event["subject"] not in FLOATING_SINGLE_SUBJECTS:
            continue
        if event_idx in assignments:
            continue

        best_p, best_remaining = None, -1
        for p in range(PERIODS_PER_DAY):
            remaining = DAYS_PER_WEEK - class_period_load[(event["class"], p)]
            if remaining >= event["weekly_load"] and remaining > best_remaining:
                best_remaining = remaining
                best_p = p

        if best_p is None:
            best_p = PERIODS_PER_DAY - 1
            print(f"  PERIOD GEN ERROR: No room for {event['subject']}/{event['class']}, "
                  f"forcing P{best_p + 1}")

        assignments[event_idx] = best_p
        class_period_load[(event["class"], best_p)] += event["weekly_load"]

    return assignments, teacher_period_load, class_period_load


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_period_assignments(events, assignments, teacher_period_load, class_period_load):
    """Return list of violation strings (empty = all good)."""
    violations = []

    for (t, p), load in teacher_period_load.items():
        if load > DAYS_PER_WEEK:
            violations.append(
                f"Teacher '{t}' over-capacity at P{p + 1}: "
                f"{load} instances > {DAYS_PER_WEEK} days"
            )

    for (cls, p), load in class_period_load.items():
        if load > DAYS_PER_WEEK:
            violations.append(
                f"Class {cls} over-capacity at P{p + 1}: "
                f"{load} instances > {DAYS_PER_WEEK} days"
            )

    # Labs are treated as single periods in the 4-period schedule; no start-period restriction.

    return violations


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_period_assignments(assignments, events, path="period_assignments.yaml"):
    """Write period assignments to YAML in a human-readable, hand-editable format."""
    records = []
    for class_section in CLASS_ORDER:
        for event_idx, event in enumerate(events):
            if event["class"] != class_section:
                continue
            p = assignments.get(event_idx)
            if p is None:
                continue

            is_locked = (event["class"], event["subject"]) in SECTION_PERIOD_LOCKS
            rec = {
                "class":       event["class"],
                "subject":     event["subject"],
                "period":      p,
                "period_name": f"P{p + 1}",
                "teacher":     event.get("teacher") or "",
                "weekly_load": event["weekly_load"],
            }
            if is_locked:
                rec["locked"] = True
            records.append(rec)

    with open(path, "w") as f:
        yaml.dump(
            {"period_assignments": records},
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    print(f"      Saved → {path}")


def load_period_assignments(path, events):
    """
    Read period_assignments.yaml and rebuild the three return values
    identical to generate_period_assignments().

    Returns (assignments, teacher_period_load, class_period_load).
    Prints a warning for any entry in the file that doesn't match a current event.
    """
    with open(path, "r") as f:
        data = yaml.safe_load(f)

    cs_to_idx = {(e["class"], e["subject"], e.get("teacher") or ""): i for i, e in enumerate(events)}

    assignments         = {}
    teacher_period_load = defaultdict(int)
    class_period_load   = defaultdict(int)

    for rec in data.get("period_assignments", []):
        key = (str(rec["class"]), rec["subject"], str(rec.get("teacher") or ""))
        idx = cs_to_idx.get(key)
        if idx is None:
            print(f"  WARNING: period_assignments.yaml entry {key} not found in events — skipped")
            continue
        p     = rec["period"]
        event = events[idx]
        assignments[idx] = p
        t = event.get("teacher")
        if t:
            teacher_period_load[(t, p)] += event["weekly_load"]
        class_period_load[(event["class"], p)] += event["weekly_load"]

    return assignments, teacher_period_load, class_period_load
