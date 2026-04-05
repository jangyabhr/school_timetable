# assignment_validator.py
#
# Validates teacher assignments before the solver runs.
# Called from main.py after event generation — aborts the pipeline if any
# teacher is over capacity, warns on missing registry entries or unqualified
# subject assignments.


def validate_assignments(events, teachers_data):
    """
    Checks:
      1. Capacity  — teacher's total weekly_load <= declared capacity  (ERROR → abort)
      2. Missing   — teacher in events but absent from teachers.yaml   (WARNING)
      3. Qualified — teacher assigned a subject not in their list      (WARNING)

    Args:
        events        : list of event dicts from generate_all_events()
        teachers_data : dict loaded from teachers.yaml["teachers"]

    Returns:
        {"valid": bool, "errors": [str], "warnings": [str]}
    """
    errors   = []
    warnings = []

    # Aggregate weekly load and subjects per teacher across all events
    teacher_loads    = {}
    teacher_subjects = {}
    for event in events:
        teacher = event.get("teacher")
        if teacher is None:       # Library / CCA — duty assigned later, skip
            continue
        teacher_loads[teacher] = teacher_loads.get(teacher, 0) + event["weekly_load"]
        teacher_subjects.setdefault(teacher, set()).add(event["subject"])

    for teacher, total in sorted(teacher_loads.items()):
        if teacher not in teachers_data:
            warnings.append(
                f"Teacher '{teacher}' is assigned {total} periods "
                f"but has no entry in teachers.yaml"
            )
            continue

        capacity = teachers_data[teacher]["capacity"]
        if total > capacity:
            errors.append(
                f"Teacher '{teacher}' over capacity: {total} periods assigned, "
                f"capacity is {capacity} — reduce by {total - capacity}"
            )

        qualified = teachers_data[teacher].get("subjects", [])
        if qualified:
            for subj in sorted(teacher_subjects.get(teacher, [])):
                if subj not in qualified:
                    warnings.append(
                        f"Teacher '{teacher}' assigned '{subj}' "
                        f"but qualified subjects are: {qualified}"
                    )

    return {
        "valid":    len(errors) == 0,
        "errors":   errors,
        "warnings": warnings,
    }
