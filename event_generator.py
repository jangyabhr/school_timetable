# event_generator.py

import yaml
from constraints import FIXED_SLOT_SUBJECTS, FLOATING_SINGLE_SUBJECTS

# Canonical class order — index in this list becomes class_idx.
# Sections 6A, 6B, and 11 have been removed.
CLASS_ORDER = ["12", "10B", "10A", "9B", "9A", "8B", "8A", "7B", "7A"]

CLASS_IDX = {section: i for i, section in enumerate(CLASS_ORDER)}

# CLASS_GROUP_MAP is no longer hardcoded — it is derived at runtime from
# class_groups.yaml via _build_group_map() inside generate_all_events().


def load_yaml(path):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _build_group_map(class_groups_data):
    """Build {section: group_name} from class_groups.yaml data."""
    group_map = {}
    for group_name, sections in class_groups_data.items():
        for section in sections:
            group_map[str(section)] = group_name
    return group_map


def resolve_section_loads(class_groups_data, group_defaults, section_overrides):
    """
    Returns {section: {subject: weekly_load}} for all sections in CLASS_ORDER.

    Each section starts from its group default (from group_defaults), then
    section_overrides[section] is merged on top — keys in the override ADD to
    or REPLACE the corresponding group-default values.
    """
    group_map = _build_group_map(class_groups_data)
    resolved = {}
    for section in CLASS_ORDER:
        group = group_map[section]
        load = dict(group_defaults.get(group, {}))       # copy group default
        load.update(section_overrides.get(section, {}))  # override wins
        resolved[section] = load
    return resolved


def generate_events(assignments, section_loads):
    """
    Generates one event per (section, subject) from teacher_assignments.yaml.
    Each event is placed weekly_load times by the placer.

    Assignments for sections not in CLASS_IDX (e.g. 6A, 6B, 11) are silently
    skipped — teacher_assignments.yaml does not need to be edited when sections
    are removed.

    Returns a list of event dicts:
      class       — section name e.g. "7A"
      class_idx   — integer index (0–8) for slot_lookup
      subject     — subject name
      teacher     — teacher name
      weekly_load — number of periods per week
    """
    events = []

    for row in assignments:
        section = str(row["section"])
        if section not in CLASS_IDX:          # skip removed sections
            continue
        subject = row["subject"]
        teacher = row.get("teacher", None)
        load    = section_loads[section].get(subject, 0)

        events.append({
            "class":       section,
            "class_idx":   CLASS_IDX[section],
            "subject":     subject,
            "teacher":     teacher,
            "weekly_load": load,
        })

    return events


def generate_cca_events(section_loads):
    """
    CCA has no teacher and no entry in teacher_assignments.yaml.
    Generate one CCA event per section directly from section_loads.
    """
    events = []

    for section in CLASS_ORDER:
        load = section_loads[section].get("CCA", 0)
        if load > 0:
            events.append({
                "class":       section,
                "class_idx":   CLASS_IDX[section],
                "subject":     "CCA",
                "teacher":     None,
                "weekly_load": load,
            })

    return events


def generate_floating_events(section_loads):
    """
    Library has no teacher and no entry in teacher_assignments.yaml.
    Generate one event per section per floating subject from section_loads.
    """
    events = []

    for section in CLASS_ORDER:
        for subject in FLOATING_SINGLE_SUBJECTS:
            load = section_loads[section].get(subject, 0)
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
    class_groups_path="class_groups.yaml",
):
    """
    Main entry point. Loads all three YAMLs, resolves per-section loads
    from group_defaults + section_overrides, and returns the full event list.
    """
    raw_assignments   = load_yaml(assignments_path)["assignments"]
    raw_load          = load_yaml(subject_load_path)
    raw_groups        = load_yaml(class_groups_path)["class_groups"]

    group_defaults    = raw_load["group_defaults"]
    # Normalize keys to strings — YAML parses bare integers (e.g. 12) as int
    section_overrides = {str(k): v for k, v in raw_load.get("section_overrides", {}).items()}

    section_loads = resolve_section_loads(raw_groups, group_defaults, section_overrides)

    events  = generate_events(raw_assignments, section_loads)
    events += generate_cca_events(section_loads)
    events += generate_floating_events(section_loads)

    return events
