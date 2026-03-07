# slot_index.py


def build_slot_index(num_classes, days_per_week, periods_per_day):
    """
    Returns a list of all slots and a lookup dict.
    slot = (class_index, day, period)
    slot_id = integer index into the flat list
    """
    slots = []
    slot_lookup = {}  # (class_idx, day, period) -> slot_id

    for c in range(num_classes):
        for d in range(days_per_week):
            for p in range(periods_per_day):
                slot_id = len(slots)
                slot = {"slot_id": slot_id, "class_idx": c, "day": d, "period": p}
                slots.append(slot)
                slot_lookup[(c, d, p)] = slot_id

    return slots, slot_lookup