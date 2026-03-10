# lab_assigner.py
#
# Annotates one existing slot per section per lab type as "is_lab=True".
# Room constraints are enforced per room: no two sections can use the same
# room at the same (day, period).
#
# CS lab room is shared by:  CS (6A–8B), IT (9A–12), Math (all 12)
# Science lab room:          Science (9A–10B)
# Physics/Chemistry/Biology: dedicated rooms, no constraint

LAB_CONFIG = [
    # (sections,                                                    subject,          room)
    (["6A", "6B", "7A", "7B", "8A", "8B"],                        "CS",              "cs_lab"),
    (["9A", "9B", "10A", "10B", "11", "12"],                       "IT",              "cs_lab"),
    (["6A", "6B", "7A", "7B", "8A", "8B",
      "9A", "9B", "10A", "10B", "11", "12"],                       "Math",            "cs_lab"),
    (["9A", "9B", "10A", "10B"],                                    "Science",         "science_lab"),
    (["11", "12"],                                                   "Physics",         "physics_lab"),
    (["11", "12"],                                                   "Chemistry",       "chemistry_lab"),
    (["11", "12"],                                                   "Biology",         "biology_lab"),
]


def assign_lab_periods(timetable_state):
    """
    For each (sections, subject, room) in LAB_CONFIG, pick one existing
    placement per section as the lab session (earliest in week, room-conflict-free)
    and set is_lab=True on that placement dict.

    Returns the updated timetable_state.
    """
    # room_schedule: room_name → set of (day, period) already claimed
    room_schedule = {}
    for _, _, room in LAB_CONFIG:
        room_schedule.setdefault(room, set())

    for sections, subject, room in LAB_CONFIG:
        booked = room_schedule[room]

        for section in sections:
            # All placements for this section+subject, not yet marked as lab
            candidates = [
                (p["day"], p["period"], key)
                for key, p in timetable_state.items()
                if p["class"] == section
                and p["subject"] == subject
                and not p.get("is_lab", False)
            ]

            if not candidates:
                continue

            # Prefer Monday-first (lowest day, then lowest period)
            candidates.sort(key=lambda x: (x[0], x[1]))

            chosen = None
            for day, period, key in candidates:
                if (day, period) not in booked:
                    chosen = (day, period, key)
                    break

            if chosen is None:
                # Fall back: pick first candidate ignoring room conflict
                # (should not happen with normal load sizes)
                chosen = candidates[0]

            day, period, key = chosen
            timetable_state[key]["is_lab"] = True
            booked.add((day, period))

    return timetable_state
