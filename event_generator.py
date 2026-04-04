# event_generator.py

import yaml
from constraints import FIXED_SLOT_SUBJECTS, FLOATING_SINGLE_SUBJECTS

# Canonical class order — index in this list becomes class_idx
CLASS_ORDER = ["6A", "6B", "7A", "7B", "8A", "8B",
               "9A", "9B", "10A", "10B", "11", "12"]

CLASS_IDX = {section: i for i, section in enumerate(CLASS_ORDER)}

# Which subject_load group each section belongs to
CLASS_GROUP_MAP = {
    "6A": "class_6_8",  "6B": "class_6_8",
    "7A": "class_6_8",  "7B": "class_6_8",
    "8A": "class_6_8",  "8B": "class_6_8",
    "9A": "class_9_10", "9B": "class_9_10",
    "10A": "class_9_10","10B": "class_9_10",
    "11":  "class_11_12","12": "class_11_12",
}


def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def generate_events(assignments, subject_load_by_group):
    """
    Generates one event per (section, subject) from teacher_assignments.yaml.
    Each event is placed weekly_load times by the placer.

    Returns a list of event dicts:
      class       — section name e.g. "6A"
      class_idx   — integer index (0–11) for slot_lookup
      subject     — subject name
      teacher     — teacher name or None (for CCA)
      weekly_load — number of periods per week
    """
    events = []

    for row in assignments:
        section = str(row["section"])
        subject  = row["subject"]
        teacher  = row.get("teacher", None)

        group = CLASS_GROUP_MAP[section]
        load  = subject_load_by_group[group].get(subject, 0)

        events.append({
            "class":       section,
            "class_idx":   CLASS_IDX[section],
            "subject":     subject,
            "teacher":     teacher,
            "weekly_load": load,
        })

    return events


def generate_cca_events(subject_load_by_group):
    """
    CCA has no teacher and no entry in teacher_assignments.yaml.
    Generate one CCA event per section directly from subject_load.
    weekly_load = 2 (Saturday periods 6 and 7).
    """
    events = []

    for section in CLASS_ORDER:
        group = CLASS_GROUP_MAP[section]
        load  = subject_load_by_group[group].get("CCA", 0)
        if load > 0:
            events.append({
                "class":       section,
                "class_idx":   CLASS_IDX[section],
                "subject":     "CCA",
                "teacher":     None,
                "weekly_load": load,
            })

    return events


def generate_floating_events(subject_load_by_group):
    """
    Library and WE have no teacher and no entry in teacher_assignments.yaml.
    Generate one event per section per floating subject from subject_load.
    weekly_load = 1 per subject per section.
    """
    events = []

    for section in CLASS_ORDER:
        group = CLASS_GROUP_MAP[section]
        for subject in FLOATING_SINGLE_SUBJECTS:
            load = subject_load_by_group[group].get(subject, 0)
            if load > 0:
                events.append({
                    "class":       section,
                    "class_idx":   CLASS_IDX[section],
                    "subject":     subject,
                    "teacher":     None,
                    "weekly_load": load,
                })

    return events


def generate_all_events(
    assignments_path="teacher_assignments.yaml",
    subject_load_path="subject_load.yaml",
):
    """
    Main entry point. Loads both YAMLs and returns the full event list
    (teacher-assigned subjects + Library + WE).
    """
    raw_assignments  = load_yaml(assignments_path)["assignments"]
    raw_subject_load = load_yaml(subject_load_path)["class_groups"]

    events  = generate_events(raw_assignments, raw_subject_load)
    events += generate_cca_events(raw_subject_load)
    events += generate_floating_events(raw_subject_load)

    return events
