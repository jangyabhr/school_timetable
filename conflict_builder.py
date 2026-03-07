# conflict_builder.py

def build_conflict_map(events):
    """
    Two events conflict if they share a teacher OR share a class section.
    CCA events (teacher=None) are excluded from teacher-clash checks.
    Returns dict: event_idx → set of conflicting event_idxs.
    """
    conflict_map = {i: set() for i in range(len(events))}

    for i in range(len(events)):
        for j in range(i + 1, len(events)):

            e1 = events[i]
            e2 = events[j]

            # Teacher clash — guard against None == None (CCA events)
            if e1["teacher"] and e2["teacher"] and e1["teacher"] == e2["teacher"]:
                conflict_map[i].add(j)
                conflict_map[j].add(i)

            # Class clash — same section can't have two subjects at once
            if e1["class"] == e2["class"]:
                conflict_map[i].add(j)
                conflict_map[j].add(i)

    return conflict_map