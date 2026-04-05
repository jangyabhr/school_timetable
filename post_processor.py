# post_processor.py
#
# Post-processing steps run after the solver:
#   A. Rebuild occupied set
#   B. Compute teaching loads + teacher availability
#   C. Mark remaining empty slots as "Free" with a duty teacher

from event_generator import CLASS_ORDER, CLASS_IDX


def run_post_processing(timetable_state, events, class_order,
                        days_per_week, periods_per_day):
    """
    Returns the updated timetable_state with:
      - Remaining empty slots filled as "Free" with a duty teacher
    """

    # ------------------------------------------------------------------
    # Step A — Rebuild occupied set
    # ------------------------------------------------------------------
    occupied = {
        (p["class_idx"], p["day"], p["period"])
        for p in timetable_state.values()
    }

    # Collect all teacher names from timetable_state (authoritative)
    all_teachers = sorted({
        p["teacher"]
        for p in timetable_state.values()
        if p.get("teacher")
    })

    # ------------------------------------------------------------------
    # Step B — Compute teaching loads and teacher availability
    # ------------------------------------------------------------------
    teaching_loads = {t: 0 for t in all_teachers}
    for p in timetable_state.values():
        t = p.get("teacher")
        if t and t in teaching_loads:
            teaching_loads[t] += 1

    teacher_busy = {
        (p["teacher"], p["day"], p["period"])
        for p in timetable_state.values()
        if p.get("teacher")
    }

    duty_loads = {t: 0 for t in all_teachers}

    # ------------------------------------------------------------------
    # Helper: pick lowest-load available teacher
    # ------------------------------------------------------------------
    def assign_duty(day, period):
        """Return best available teacher for (day, period), or None."""
        best = None
        best_total = 9999
        for t in all_teachers:
            if (t, day, period) in teacher_busy:
                continue
            total = teaching_loads[t] + duty_loads[t]
            if total >= 26:  # 36 teaching slots × ~0.72 — proportional cap
                continue
            if total < best_total:
                best_total = total
                best = t
        if best:
            duty_loads[best] += 1
            teacher_busy.add((best, day, period))
        return best

    # ------------------------------------------------------------------
    # Step C — Mark remaining empty slots as "Free" with duty teacher
    # ------------------------------------------------------------------
    BASE_FREE_IDX = len(events)
    counter = 0

    for class_idx_val, section in enumerate(class_order):
        for day in range(days_per_week):
            for period in range(periods_per_day):
                if (class_idx_val, day, period) not in occupied:
                    duty_teacher = assign_duty(day, period)
                    key = (BASE_FREE_IDX + counter, 0)
                    timetable_state[key] = {
                        "day":       day,
                        "period":    period,
                        "class":     section,
                        "class_idx": class_idx_val,
                        "subject":   "Free",
                        "teacher":   duty_teacher,
                    }
                    occupied.add((class_idx_val, day, period))
                    counter += 1

    return timetable_state
