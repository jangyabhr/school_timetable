# html_exporter.py
#
# Generates Timetable_Tools.html from the solver's timetable_state.
# Accepts the same inputs as exporter.py (timetable_state, events).
# No external dependencies beyond Python stdlib (json, pathlib).

import json
from pathlib import Path
from event_generator import CLASS_ORDER

# ── Constants ─────────────────────────────────────────────────────────────────

DAYS    = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
PERIODS = ['P1', 'P2', 'P3', 'P4']
TIMES   = [
    '7:10–7:50',  '7:50–8:30',  '8:40–9:20',  '9:20–10:00',
]
SPECIALS     = {'Free', 'Library'}
LAB_SUBJECTS = {'CS', 'IT', 'Math', 'Science', 'Biology', 'Physics', 'Chemistry'}

SUBJ_COLORS = {
    'Math':      '#D4E6F1', 'Science':   '#D5F5E3', 'English':   '#FAD7A0',
    'SST':       '#F9E79F', 'Hindi':     '#FADBD8', 'Odia':      '#F5CBA7',
    'Sanskrit':  '#D2B4DE', 'CS':        '#AED6F1', 'IT':        '#85C1E9',
    'Biology':   '#A8D8A8', 'Physics':   '#A9CCE3', 'Chemistry': '#A9DFBF',
    'Free':      '#ECECEC', 'Library':   '#D5D8DC',
}
SUBJ_TEXT = {
    'Free':    '#888888', 'Library': '#555555',
}

_SEP = (',', ':')

# ── Data builders ─────────────────────────────────────────────────────────────

def _build_structures(timetable_state, events=None):
    """
    Transforms the solver's timetable_state into the data structures
    expected by the HTML template.

    timetable_state keys : (event_idx, instance)
    timetable_state values: {'class', 'day' (int 0-5), 'period' (int 0-5), 'subject', 'teacher'}
    events : list of event dicts (used for teacher load detail breakdown)
    """

    # ── class_timetable ───────────────────────────────────────────────────────
    # class_timetable[cls][day] = list of len(PERIODS) dicts {s, t, l}
    n_periods = len(PERIODS)
    class_timetable = {
        cls: {day: [{'s': '', 't': '', 'l': False} for _ in range(n_periods)] for day in DAYS}
        for cls in CLASS_ORDER
    }

    for p in timetable_state.values():
        cls    = p['class']
        day    = DAYS[p['day']]
        period = p['period']
        subj   = p['subject']
        teacher = p.get('teacher') or ''
        if cls in class_timetable and 0 <= period < n_periods:
            class_timetable[cls][day][period] = {
                's': subj,
                't': teacher,
                'l': p.get('is_lab', False),
            }

    # ── all_teachers (sorted) ────────────────────────────────────────────────
    all_teachers = sorted({
        p['teacher'] for p in timetable_state.values() if p.get('teacher')
    })

    # ── teacher_sched & teacher_view ──────────────────────────────────────────
    # teacher_sched[t][day][pi] = {'class': cls, 'subject': subj} or None
    # teacher_view[t][day][pi]  = {'cls': cls, 's': subj, 'l': bool} or None
    teacher_sched = {
        t: {day: [None] * n_periods for day in DAYS}
        for t in all_teachers
    }
    teacher_view = {
        t: {day: [None] * n_periods for day in DAYS}
        for t in all_teachers
    }
    for p in timetable_state.values():
        t = p.get('teacher')
        if not t:
            continue
        day    = DAYS[p['day']]
        period = p['period']
        subj   = p['subject']
        cls    = p['class']
        if 0 <= period < n_periods:
            teacher_sched[t][day][period] = {'class': cls, 'subject': subj}
            teacher_view[t][day][period]  = {'cls': cls, 's': subj, 'l': p.get('is_lab', False)}

    # ── wk_load ───────────────────────────────────────────────────────────────
    wk_load = {t: 0 for t in all_teachers}
    for p in timetable_state.values():
        t = p.get('teacher')
        if t:
            wk_load[t] += 1

    # ── special_counts ────────────────────────────────────────────────────────
    special_counts = {
        cls: {s: 0 for s in SPECIALS}
        for cls in CLASS_ORDER
    }
    for p in timetable_state.values():
        subj = p['subject']
        cls  = p['class']
        if subj in SPECIALS and cls in special_counts:
            special_counts[cls][subj] += 1

    # ── coverage ──────────────────────────────────────────────────────────────
    # coverage[cls][day] = list of slot dicts for specials
    # Each slot: {period, time, type, free: [{name, day_load, wk_load}]}
    coverage = {}
    for cls in CLASS_ORDER:
        coverage[cls] = {}
        for day in DAYS:
            cov_list = []
            for pi, slot in enumerate(class_timetable[cls][day]):
                subj = slot['s']
                if subj in SPECIALS:
                    free_teachers = sorted(
                        [
                            {
                                'name':     t,
                                'day_load': sum(1 for s in teacher_sched[t][day] if s is not None),
                                'wk_load':  wk_load[t],
                            }
                            for t in all_teachers
                            if teacher_sched[t][day][pi] is None
                        ],
                        key=lambda x: (x['day_load'], x['wk_load']),
                    )
                    cov_list.append({
                        'period': PERIODS[pi],
                        'time':   TIMES[pi],
                        'type':   subj,
                        'free':   free_teachers,
                    })
            coverage[cls][day] = cov_list

    # ── teacher_load_detail ───────────────────────────────────────────────────
    # teacher_load_detail[teacher] = sorted list of
    #   {subject, classes (sorted), per_class, subtotal}
    from collections import defaultdict as _dd
    _tld = _dd(lambda: _dd(list))  # teacher → (subject, load) → [classes]
    if events:
        for ev in events:
            t = ev.get('teacher')
            if t:
                _tld[t][(ev['subject'], ev['weekly_load'])].append(ev['class'])

    teacher_load_detail = {}
    for t in all_teachers:
        rows = []
        for (subj, load), classes in sorted(_tld[t].items(), key=lambda x: x[0][0]):
            classes_sorted = sorted(classes)
            rows.append({
                'subject':   subj,
                'classes':   ', '.join(classes_sorted),
                'per_class': load,
                'subtotal':  load * len(classes_sorted),
            })
        teacher_load_detail[t] = rows

    return (
        class_timetable, teacher_sched, teacher_view,
        coverage, wk_load, special_counts, all_teachers,
        teacher_load_detail,
    )


# ── HTML template ─────────────────────────────────────────────────────────────

def _build_html(
    class_timetable, teacher_sched, teacher_view,
    coverage, wk_load, special_counts, all_teachers,
    teacher_load_detail,
):
    sched_json          = json.dumps(teacher_sched,        ensure_ascii=False, separators=_SEP)
    class_json          = json.dumps(class_timetable,      ensure_ascii=False, separators=_SEP)
    teacher_view_json   = json.dumps(teacher_view,         ensure_ascii=False, separators=_SEP)
    coverage_json       = json.dumps(coverage,             ensure_ascii=False, separators=_SEP)
    wk_load_json        = json.dumps(wk_load,              ensure_ascii=False, separators=_SEP)
    spec_counts_json    = json.dumps(special_counts,       ensure_ascii=False, separators=_SEP)
    tld_json            = json.dumps(teacher_load_detail,  ensure_ascii=False, separators=_SEP)
    days_json           = json.dumps(DAYS)
    periods_json        = json.dumps(PERIODS)
    times_json          = json.dumps(TIMES)
    classes_json        = json.dumps(CLASS_ORDER)
    teachers_json       = json.dumps(all_teachers)
    colors_json         = json.dumps(SUBJ_COLORS,          ensure_ascii=False, separators=_SEP)
    text_colors_json    = json.dumps(SUBJ_TEXT,            ensure_ascii=False, separators=_SEP)
    n_teachers          = len(all_teachers)
    n_classes           = len(CLASS_ORDER)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Timetable Tool from Excel</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,400;0,500;0,700;0,800;1,400&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<style>
/* ── TOKENS ── */
:root{{
  --ink:#12202e;--ink2:#3d5166;--ink3:#7a8fa3;
  --paper:#f3f7fb;--white:#fff;--border:#dde5ee;
  --navy:#0f2744;--blue:#1a5fa8;--blue2:#2980d4;--sky:#dbeeff;
  --green:#166534;--green2:#22a75c;--mint:#dcfce7;
  --red:#9b1c1c;--red2:#e63946;--blush:#fde8e8;
  --amber:#92400e;--amber2:#f59e0b;--cream:#fef3c7;
  --purple:#4c1d95;--purple2:#7c3aed;--lavender:#ede9fe;
  --teal:#0f766e;--teal2:#14b8a6;--ice:#ccfbf1;
  --r:10px;--rlg:14px;
  --sh:0 2px 16px rgba(15,39,68,.10);
  --shm:0 4px 24px rgba(15,39,68,.14);
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{font-family:'DM Sans',sans-serif;background:var(--paper);color:var(--ink);min-height:100vh;font-size:14px}}
.mono{{font-family:'JetBrains Mono',monospace}}

/* ── HEADER + TABS ── */
.site-header{{
  background:var(--navy);color:#fff;padding:0 28px;
  display:flex;align-items:stretch;
  position:sticky;top:0;z-index:300;
  box-shadow:0 2px 20px rgba(0,0,0,.35);
  min-height:54px;
}}
.tab-nav{{display:flex;align-items:stretch;flex:1;overflow-x:auto}}
.tab-btn{{
  display:flex;align-items:center;gap:7px;padding:0 18px;
  border:none;background:transparent;color:rgba(255,255,255,.5);
  font-family:'DM Sans',sans-serif;font-size:.79rem;font-weight:700;
  cursor:pointer;border-bottom:3px solid transparent;transition:all .14s;
  white-space:nowrap;
}}
.tab-btn:hover{{color:rgba(255,255,255,.82);background:rgba(255,255,255,.05)}}
.tab-btn.active{{color:#fff;border-bottom-color:var(--blue2);background:rgba(255,255,255,.07)}}
.tbadge{{background:rgba(255,255,255,.13);border-radius:4px;font-size:.62rem;
  padding:1px 5px;font-weight:800}}
.tab-btn.active .tbadge{{background:var(--blue2)}}

/* ── PAGES ── */
.page{{display:none}}.page.active{{display:block}}
.inner{{max-width:1300px;margin:0 auto;padding:22px 18px}}

/* ── SPLIT LAYOUT ── */
.split{{display:grid;grid-template-columns:278px 1fr;gap:16px;align-items:start}}
@media(max-width:820px){{
  .split{{grid-template-columns:1fr}}
  .master-controls{{padding:8px 10px;gap:6px}}
  .search-wrap{{max-width:none;flex:1 1 100%}}
  .stats-bar{{margin-left:0;width:100%;justify-content:flex-start;flex-wrap:wrap}}
  .filter-group{{flex-wrap:wrap;gap:4px}}
  /* ── master timetable: fixed-layout, all 4 periods in viewport ── */
  .tt-table{{table-layout:fixed!important;width:100%!important;min-width:0!important}}
  .tt-table thead th{{padding:4px 2px;font-size:.68rem;white-space:nowrap;overflow:hidden}}
  .tt-table thead th:first-child{{width:42px!important;min-width:42px!important}}
  .tt-table thead th:nth-child(2){{width:32px!important;min-width:32px!important;left:42px!important}}
  .tt-table thead th .ph-time{{display:none!important}}
  .col-cls{{width:42px!important;min-width:42px!important;max-width:42px!important;font-size:.66rem;padding:0 2px}}
  .col-day{{left:42px!important;width:32px!important;min-width:32px!important;max-width:32px!important;font-size:.62rem;padding:0 2px}}
  .tt-cell{{padding:2px;overflow:hidden}}
  .cell-inner{{min-height:36px;padding:3px 4px;overflow:hidden;gap:1px}}
  .cell-subj{{font-size:.67rem;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}}
  .cell-teacher{{display:block!important;font-size:.57rem;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--ink2)}}
  .cell-lab{{display:none!important}}
  .cls-header-row td{{padding:4px 8px;font-size:.72rem}}
}}

/* ── CARD ── */
.card{{background:var(--white);border-radius:var(--rlg);box-shadow:var(--sh);
  overflow:hidden;border:1px solid var(--border)}}
.ch{{padding:12px 16px;font-size:.8rem;font-weight:800;
  display:flex;align-items:center;gap:7px}}
.ch-navy{{background:var(--navy);color:#fff}}
.ch-green{{background:var(--green);color:#fff}}
.ch-teal{{background:var(--teal);color:#fff}}
.ch-indigo{{background:#312e81;color:#fff}}
.cb{{padding:14px 16px}}

/* ── FORM ATOMS ── */
.slabel{{font-size:.65rem;font-weight:800;text-transform:uppercase;
  letter-spacing:.8px;color:var(--ink3);margin:13px 0 5px}}
.slabel:first-child{{margin-top:0}}
.day-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:4px}}
.cls-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:4px}}
.pill-btn{{
  padding:7px 2px;border:2px solid var(--border);border-radius:7px;
  background:var(--paper);font-family:'DM Sans',sans-serif;
  font-size:.73rem;font-weight:700;cursor:pointer;
  transition:all .12s;color:var(--ink2);text-align:center;
}}
.pill-btn:hover{{border-color:var(--blue2);background:var(--sky);color:var(--blue)}}
.pill-btn.active{{border-color:var(--blue);background:var(--blue);color:#fff}}
.pill-btn.sat.active{{background:var(--amber);border-color:var(--amber)}}
.pill-btn.cls-active{{border-color:var(--teal);background:var(--teal);color:#fff}}
.t-list{{display:flex;flex-direction:column;gap:3px;max-height:360px;overflow-y:auto;padding-right:2px}}
.t-item{{display:flex;align-items:center;gap:7px;padding:5px 8px;border-radius:7px;
  cursor:pointer;border:1.5px solid transparent;transition:all .11s;user-select:none}}
.t-item:hover{{background:var(--blush);border-color:#f2c4c4}}
.t-item.absent{{background:var(--blush);border-color:var(--red2)}}
.t-item input{{width:13px;height:13px;accent-color:var(--red2);cursor:pointer;flex-shrink:0}}
.t-name{{font-size:.78rem;font-weight:500;flex:1}}
.t-item.absent .t-name{{color:var(--red);font-weight:700}}
.lpill{{font-size:.62rem;font-weight:800;padding:1px 6px;border-radius:8px;color:#fff;
  white-space:nowrap;font-family:'JetBrains Mono',monospace}}
.lp-hi{{background:var(--red2)}}.lp-mid{{background:var(--amber2)}}.lp-lo{{background:var(--green2)}}

/* ── BUTTONS ── */
.btn{{width:100%;margin-top:12px;padding:10px;border:none;border-radius:var(--r);
  font-family:'DM Sans',sans-serif;font-size:.83rem;font-weight:800;cursor:pointer;
  transition:all .13s;display:flex;align-items:center;justify-content:center;gap:6px}}
.btn-green{{background:linear-gradient(135deg,var(--green2),var(--green));color:#fff}}
.btn-teal{{background:linear-gradient(135deg,var(--teal2),var(--teal));color:#fff}}
.btn-indigo{{background:linear-gradient(135deg,#4f46e5,#312e81);color:#fff}}
.btn:hover:not(:disabled){{transform:translateY(-1px);box-shadow:var(--shm)}}
.btn:disabled{{background:#ccd6df;cursor:not-allowed;transform:none}}
.btn-reset{{width:100%;margin-top:4px;padding:7px;border:2px solid var(--border);
  border-radius:var(--r);background:var(--white);font-family:'DM Sans',sans-serif;
  font-size:.75rem;font-weight:700;color:var(--ink3);cursor:pointer;transition:all .11s}}
.btn-reset:hover{{border-color:var(--red2);color:var(--red);background:var(--blush)}}

/* ── EMPTY ── */
.empty{{text-align:center;padding:55px 20px;color:var(--ink3)}}
.empty .eico{{font-size:2.8rem;margin-bottom:10px;opacity:.38}}
.empty p{{font-size:.84rem;line-height:1.7}}

/* ── SUMMARY ── */
.summary{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;
  padding:9px 13px;background:var(--cream);border:1px solid #f0d060;
  border-radius:var(--r);margin-bottom:14px;font-size:.76rem}}
.sdot{{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:3px;flex-shrink:0}}
.legend{{margin-left:auto;display:flex;gap:9px;flex-wrap:wrap;font-size:.67rem;color:var(--ink3)}}
.legend span{{display:flex;align-items:center;gap:3px}}

/* ── PERIOD BLOCK (sub) ── */
.pblock{{border:1px solid var(--border);border-radius:var(--r);margin-bottom:11px;overflow:hidden}}
.pblock-head{{display:flex;align-items:center;gap:9px;padding:8px 13px;
  background:linear-gradient(90deg,var(--navy),var(--blue));color:#fff;
  font-size:.82rem;font-weight:800}}
.ph-time{{font-size:.68rem;font-weight:400;opacity:.74}}
.ph-gap{{margin-left:auto;font-size:.63rem;padding:2px 8px;
  background:rgba(255,255,255,.16);border-radius:7px}}
.pblock-body{{padding:9px 11px;display:flex;flex-direction:column;gap:7px}}
.arow{{display:grid;grid-template-columns:68px 1fr;gap:9px;align-items:start;
  padding:8px 10px;background:#fff9f9;border:1px solid #f5d0d0;border-radius:7px}}
.badge-stack{{display:flex;flex-direction:column;align-items:center;gap:3px}}
.cls-badge{{background:var(--red2);color:#fff;font-size:.66rem;font-weight:900;
  padding:3px 8px;border-radius:5px;white-space:nowrap}}
.subj-badge{{font-size:.6rem;font-weight:700;padding:2px 6px;border-radius:4px;
  background:var(--blush);color:var(--red);white-space:nowrap}}
.absent-lbl{{font-size:.74rem;color:var(--red);font-weight:700;margin-bottom:4px}}
.absent-lbl em{{color:var(--ink3);font-style:normal;font-weight:400}}
.subs-list{{display:flex;flex-direction:column;gap:2px}}
.sub-row{{display:flex;align-items:center;gap:7px;padding:4px 8px;border-radius:5px;font-size:.76rem}}
.sr-free{{background:var(--mint);border:1px solid #a7f3d0}}
.sr-light{{background:var(--cream);border:1px solid #fcd34d}}
.sr-busy{{background:var(--paper);border:1px solid var(--border);opacity:.7}}
.ld{{width:7px;height:7px;border-radius:50%;flex-shrink:0}}
.ld-free{{background:var(--green2)}}.ld-light{{background:var(--amber2)}}.ld-busy{{background:#aaa}}
.sub-name{{font-weight:700;color:var(--ink);flex:1}}
.sub-name.dim{{color:var(--ink2)}}
.sub-today{{font-size:.67rem;color:var(--ink3)}}
.sub-wk{{font-size:.63rem;color:var(--ink3);font-family:'JetBrains Mono',monospace}}
.tag{{font-size:.6rem;font-weight:800;padding:1px 6px;border-radius:4px;color:#fff;white-space:nowrap}}
.tag-free{{background:var(--green2)}}.tag-light{{background:var(--amber2);color:var(--ink)}}
.tag-busy{{background:#999}}
.no-avail{{font-size:.74rem;color:var(--red2);font-style:italic;padding:2px 0}}

/* ── COVERAGE ── */
.spec-pills{{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:3px}}
.spec-pill{{padding:4px 12px;border-radius:18px;font-size:.72rem;font-weight:800;
  border:2px solid transparent;cursor:pointer;transition:all .12s;
  display:flex;align-items:center;gap:4px}}
.spec-pill:hover{{opacity:.8}}
.sp-all{{background:var(--paper);border-color:var(--border);color:var(--ink2)}}
.sp-free{{background:#f1f5f9;border-color:#cbd5e1;color:#475569}}
.sp-game{{background:#e8fdf0;border-color:#6ee7b7;color:#065f46}}
.sp-library{{background:#e0f2fe;border-color:#7dd3fc;color:#0369a1}}
.sp-we{{background:#faf5ff;border-color:#c4b5fd;color:#5b21b6}}
.sp-all.active{{background:var(--ink2);border-color:var(--ink2);color:#fff}}
.sp-free.active{{background:#64748b;border-color:#64748b;color:#fff}}
.sp-game.active{{background:#059669;border-color:#059669;color:#fff}}
.sp-library.active{{background:#0284c7;border-color:#0284c7;color:#fff}}
.sp-we.active{{background:var(--purple2);border-color:var(--purple2);color:#fff}}
.cov-slot{{border:1px solid var(--border);border-radius:var(--r);overflow:hidden;margin-bottom:9px}}
.cov-head{{display:flex;align-items:center;gap:9px;padding:8px 12px;
  font-size:.8rem;font-weight:800;color:#fff}}
.ch-f{{background:linear-gradient(90deg,#374151,#4b5563)}}
.ch-g{{background:linear-gradient(90deg,#065f46,#059669)}}
.ch-l{{background:linear-gradient(90deg,#0c4a6e,#0284c7)}}
.ch-w{{background:linear-gradient(90deg,var(--purple),var(--purple2))}}
.cov-body{{padding:9px 12px}}
.chip-grid{{display:flex;flex-wrap:wrap;gap:5px;margin-top:3px}}
.chip{{display:flex;align-items:center;gap:5px;padding:4px 9px;border-radius:18px;
  font-size:.73rem;font-weight:600;border:1.5px solid}}
.chip-free{{background:var(--mint);border-color:#6ee7b7;color:#065f46}}
.chip-light{{background:var(--cream);border-color:#fcd34d;color:#92400e}}
.chip-busy{{background:var(--paper);border-color:var(--border);color:var(--ink3);opacity:.72}}
.chip-dot{{width:6px;height:6px;border-radius:50%;flex-shrink:0}}
.chip-wk{{font-size:.6rem;font-family:'JetBrains Mono',monospace;opacity:.68}}
.no-cov{{font-size:.74rem;color:var(--red2);font-style:italic}}
.spec-tag{{display:inline-block;padding:1px 6px;border-radius:3px;
  font-size:.62rem;font-weight:800;margin:1px 2px;white-space:nowrap}}
.st-free{{background:var(--paper);border:1px solid var(--border);color:var(--ink3)}}
.st-game{{background:#dcfce7;color:#166534}}
.st-library{{background:#e0f2fe;color:#0369a1}}
.st-we{{background:var(--lavender);color:var(--purple)}}
.notice{{display:flex;align-items:flex-start;gap:9px;padding:9px 13px;
  background:var(--sky);border:1px solid #90cdf4;border-radius:var(--r);
  margin-bottom:13px;font-size:.76rem;color:var(--blue)}}

/* ════════════════════════════════════════════════════════
   MASTER TIMETABLE TAB
════════════════════════════════════════════════════════ */
.master-layout{{display:grid;grid-template-rows:auto 1fr;height:calc(100vh - 54px)}}
.master-controls{{
  background:var(--white);border-bottom:1px solid var(--border);
  padding:10px 20px;display:flex;flex-wrap:wrap;align-items:center;gap:10px;
  position:sticky;top:54px;z-index:200;
  box-shadow:0 2px 8px rgba(15,39,68,.07);
}}
.mode-toggle{{display:flex;border:2px solid var(--border);border-radius:8px;overflow:hidden}}
.mode-btn{{
  padding:6px 14px;border:none;background:transparent;
  font-family:'DM Sans',sans-serif;font-size:.76rem;font-weight:700;
  cursor:pointer;color:var(--ink3);transition:all .12s;
}}
.mode-btn.active{{background:var(--navy);color:#fff}}
.filter-group{{display:flex;align-items:center;gap:6px}}
.filter-label{{font-size:.68rem;font-weight:800;text-transform:uppercase;
  letter-spacing:.6px;color:var(--ink3);white-space:nowrap}}
.filter-select{{
  padding:6px 10px;border:2px solid var(--border);border-radius:7px;
  font-family:'DM Sans',sans-serif;font-size:.78rem;font-weight:600;
  color:var(--ink);background:var(--paper);cursor:pointer;
  transition:all .12s;min-width:120px;
}}
.filter-select:focus{{outline:none;border-color:var(--blue2)}}
.search-wrap{{display:flex;align-items:center;gap:6px;flex:1;max-width:240px}}
.search-input{{
  flex:1;padding:6px 10px;border:2px solid var(--border);border-radius:7px;
  font-family:'DM Sans',sans-serif;font-size:.78rem;color:var(--ink);
  background:var(--white);transition:all .12s;
}}
.search-input:focus{{outline:none;border-color:var(--blue2)}}
.search-input::placeholder{{color:var(--ink3)}}
.stats-bar{{margin-left:auto;display:flex;gap:12px;font-size:.68rem;color:var(--ink3)}}
.stats-bar strong{{color:var(--ink);font-size:.76rem}}
.clear-btn{{
  padding:5px 10px;border:1.5px solid var(--border);border-radius:6px;
  background:var(--white);font-family:'DM Sans',sans-serif;
  font-size:.72rem;font-weight:700;color:var(--ink3);cursor:pointer;
  transition:all .11s;white-space:nowrap;
}}
.clear-btn:hover{{border-color:var(--red2);color:var(--red);background:var(--blush)}}
.tt-scroll{{overflow:auto;max-height:calc(100vh - 54px - 62px);}}
.tt-table{{
  border-collapse:separate;border-spacing:0;
  font-size:.76rem;min-width:900px;
}}
.tt-table thead th{{
  position:sticky;top:0;z-index:100;
  background:var(--navy);color:#fff;
  padding:8px 6px;text-align:center;
  font-weight:800;font-size:.76rem;
  border-right:1px solid rgba(255,255,255,.12);
  white-space:nowrap;
}}
.tt-table thead th:first-child{{left:0;z-index:110;min-width:70px}}
.tt-table thead th:nth-child(2){{
  position:sticky;left:70px;z-index:110;
  min-width:48px;
}}
.tt-table thead th .ph-time{{font-size:.62rem;font-weight:400;opacity:.68;display:block;margin-top:1px}}
.col-cls{{
  position:sticky;left:0;z-index:50;
  background:var(--navy);color:#fff;
  padding:0 10px;font-weight:800;font-size:.8rem;
  text-align:center;min-width:70px;
  border-right:2px solid rgba(255,255,255,.2);
  border-bottom:1px solid rgba(255,255,255,.1);
  white-space:nowrap;
}}
.col-day{{
  position:sticky;left:70px;z-index:50;
  background:#1a3a5c;color:rgba(255,255,255,.9);
  padding:0 10px;font-weight:700;font-size:.74rem;
  text-align:center;min-width:48px;
  border-right:2px solid rgba(255,255,255,.15);
  border-bottom:1px solid rgba(255,255,255,.08);
  white-space:nowrap;
}}
.col-day.sat-day{{background:#7a5c00;color:#fff}}
.cls-header-row td{{
  background:linear-gradient(90deg,var(--navy) 0%,#1f4068 100%);
  color:#fff;padding:7px 14px;
  font-weight:800;font-size:.84rem;
  border-top:3px solid var(--blue2);
  border-bottom:1px solid rgba(255,255,255,.1);
  letter-spacing:.2px;
}}
.tt-cell{{
  padding:4px 5px;
  border-right:1px solid var(--border);
  border-bottom:1px solid var(--border);
  min-width:102px;max-width:102px;width:102px;
  vertical-align:top;
  transition:background .15s,opacity .15s;
}}
.tt-cell:last-child{{border-right:none}}
.cell-inner{{
  padding:4px 6px;border-radius:5px;
  min-height:46px;display:flex;flex-direction:column;
  justify-content:space-between;gap:1px;
  position:relative;
}}
.cell-subj{{font-weight:800;font-size:.74rem;line-height:1.2}}
.cell-teacher{{font-size:.65rem;color:var(--ink2);line-height:1.2;
  font-style:italic;margin-top:1px}}
.cell-lab{{
  position:absolute;top:3px;right:4px;
  font-size:.6rem;font-weight:800;color:var(--blue);
  line-height:1;
}}
.sp-free-cell .cell-inner{{background:#f1f5f9;}}
.sp-free-cell .cell-subj{{color:#64748b;font-style:italic;font-weight:600}}
.sp-game-cell .cell-inner{{background:#dcfce7;}}
.sp-game-cell .cell-subj{{color:#166534;font-weight:800}}
.sp-library-cell .cell-inner{{background:#e0f2fe;}}
.sp-library-cell .cell-subj{{color:#0369a1;font-weight:800}}
.sp-we-cell .cell-inner{{background:#ede9fe;}}
.sp-we-cell .cell-subj{{color:#5b21b6;font-weight:800}}
.sp-cca-cell .cell-inner{{background:var(--lavender);}}
.sp-cca-cell .cell-subj{{color:var(--purple);font-weight:800}}
.gap-break{{border-left:3px solid #1a5fa8!important}}
.gap-lunch{{border-left:3px solid #8b4513!important}}
.sat-col{{background:#fffbf0!important}}
.tt-table.filter-cls .cls-row{{opacity:.2;pointer-events:none}}
.tt-table.filter-cls .cls-row.cls-match{{opacity:1;pointer-events:auto}}
.tt-table.filter-day .cls-row{{opacity:.2;pointer-events:none}}
.tt-table.filter-day .cls-row.day-match{{opacity:1;pointer-events:auto}}
.tt-table.filter-cls .cls-header-row,
.tt-table.filter-day .cls-header-row{{opacity:1!important}}
.tt-table.filter-teacher .tt-cell{{opacity:.15}}
.tt-table.filter-teacher .tt-cell.t-match{{opacity:1;outline:2px solid var(--blue2);outline-offset:-1px}}
.tt-cell.s-match .cell-inner{{outline:2px solid var(--amber2);outline-offset:-1px}}
.tt-cell.t-free .cell-inner{{background:#f8fafc;}}
.t-free-lbl{{font-size:.65rem;color:#aaa;font-style:italic}}
.legend-strip{{
  display:flex;flex-wrap:wrap;gap:6px;align-items:center;
  padding:7px 14px;background:var(--white);
  border-top:1px solid var(--border);
  font-size:.68rem;
}}
.lchip{{
  display:inline-flex;align-items:center;gap:4px;
  padding:2px 8px;border-radius:4px;font-weight:700;
  font-size:.65rem;
}}
::-webkit-scrollbar{{width:5px;height:5px}}
::-webkit-scrollbar-track{{background:var(--paper)}}
::-webkit-scrollbar-thumb{{background:var(--border);border-radius:3px}}
::-webkit-scrollbar-thumb:hover{{background:var(--ink3)}}
</style>
</head>
<body>

<!-- ═══ HEADER ═══ -->
<header class="site-header">
  <nav class="tab-nav">
    <button class="tab-btn active" onclick="switchTab('sub')" id="tab-sub">
      🔍 Substitute Finder <span class="tbadge">{n_teachers} teachers</span>
    </button>
    <button class="tab-btn" onclick="switchTab('cov')" id="tab-cov">
      📋 Period Coverage <span class="tbadge">Free·Library</span>
    </button>
    <button class="tab-btn" onclick="switchTab('master')" id="tab-master">
      📊 Master Timetable <span class="tbadge">{n_classes} classes</span>
    </button>
    <button class="tab-btn" onclick="switchTab('tload')" id="tab-tload">
      📚 Teacher Loads <span class="tbadge">{n_teachers} teachers</span>
    </button>
  </nav>
</header>

<!-- TAB 1: SUBSTITUTE FINDER -->
<div class="page active" id="page-sub">
<div class="inner"><div class="split">
  <div class="card">
    <div class="ch ch-navy">📅 &nbsp;Setup</div>
    <div class="cb">
      <div class="slabel">1 · Select the day</div>
      <div class="day-grid" id="sub-day-grid"></div>
      <div class="slabel">2 · Mark absent teacher(s)</div>
      <div class="t-list" id="sub-t-list"></div>
      <button class="btn btn-green" id="sub-find-btn" onclick="findSubs()" disabled>
        🔍 &nbsp;Find Available Substitutes
      </button>
      <button class="btn-reset" onclick="resetSub()">↺ Reset</button>
    </div>
  </div>
  <div class="card">
    <div class="ch ch-green" id="sub-res-head">📋 &nbsp;Results</div>
    <div class="cb" id="sub-res-body">
      <div class="empty"><div class="eico">🔍</div>
        <p>Select a day and mark absent teacher(s),<br>then click <strong>Find Available Substitutes</strong>.</p>
      </div>
    </div>
  </div>
</div></div>
</div>

<!-- TAB 2: PERIOD COVERAGE -->
<div class="page" id="page-cov">
<div class="inner">
  <div class="notice">💡 <span>Select a <strong>class</strong> and <strong>day</strong> to see all non-teaching slots and which teachers are free to supervise each one.</span></div>
  <div class="split">
    <div class="card">
      <div class="ch ch-teal">⚙️ &nbsp;Select Class &amp; Day</div>
      <div class="cb">
        <div class="slabel">1 · Class</div>
        <div class="cls-grid" id="cov-cls-grid"></div>
        <div class="slabel">2 · Day</div>
        <div class="day-grid" id="cov-day-grid"></div>
        <div class="slabel">3 · Filter type</div>
        <div class="spec-pills" id="cov-type-pills">
          <button class="spec-pill sp-all active" data-type="all"     onclick="setTypeFilter('all')">All</button>
          <button class="spec-pill sp-free"        data-type="Free"    onclick="setTypeFilter('Free')">— Free</button>
          <button class="spec-pill sp-library"     data-type="Library" onclick="setTypeFilter('Library')">📚 Library</button>
        </div>
        <button class="btn btn-teal" id="cov-find-btn" onclick="findCoverage()" disabled>
          📋 &nbsp;Show Available Teachers
        </button>
        <button class="btn-reset" onclick="resetCov()">↺ Reset</button>
      </div>
    </div>
    <div class="card">
      <div class="ch ch-teal" id="cov-res-head">📋 &nbsp;Coverage Results</div>
      <div class="cb" id="cov-res-body">
        <div class="empty"><div class="eico">📋</div>
          <p>Select a class and day to see which teachers<br>are available for each non-teaching period.</p>
        </div>
      </div>
    </div>
  </div>
</div>
</div>

<!-- TAB 3: MASTER TIMETABLE -->
<div class="page" id="page-master">
  <div class="master-controls" id="master-controls">
    <div class="mode-toggle">
      <button class="mode-btn active" id="mode-cls" onclick="setMode('class')">Class View</button>
      <button class="mode-btn"        id="mode-tch" onclick="setMode('teacher')">Teacher View</button>
    </div>
    <div class="filter-group" id="fg-class">
      <span class="filter-label">Class</span>
      <select class="filter-select" id="sel-class" onchange="applyFilters()">
        <option value="">All classes</option>
      </select>
    </div>
    <div class="filter-group" id="fg-teacher">
      <span class="filter-label" id="fg-teacher-lbl">Highlight teacher</span>
      <select class="filter-select" id="sel-teacher" onchange="applyFilters()">
        <option value="">— none —</option>
      </select>
    </div>
    <div class="filter-group">
      <span class="filter-label">Day</span>
      <select class="filter-select" id="sel-day" onchange="applyFilters()">
        <option value="">All days</option>
      </select>
    </div>
    <div class="search-wrap">
      <input class="search-input" id="search-subj" type="text"
             placeholder="🔎  Search subject…" oninput="applyFilters()">
    </div>
    <button class="clear-btn" onclick="clearFilters()">✕ Clear filters</button>
    <div class="stats-bar" id="master-stats"></div>
  </div>
  <div class="tt-scroll" id="tt-scroll">
    <table class="tt-table" id="tt-table">
      <thead id="tt-thead"></thead>
      <tbody id="tt-tbody"></tbody>
    </table>
  </div>
  <div class="legend-strip" id="legend-strip"></div>
</div>

<!-- DATA + LOGIC -->
<script>
const SCHED        = {sched_json};
const CLASS_TT     = {class_json};
const TEACHER_VIEW = {teacher_view_json};
const COVERAGE     = {coverage_json};
const WK_LOAD      = {wk_load_json};
const TLD          = {tld_json};
const SPEC_COUNTS  = {spec_counts_json};
const DAYS         = {days_json};
const PERIODS      = {periods_json};
const TIMES        = {times_json};
const CLASSES      = {classes_json};
const TEACHERS     = {teachers_json};
const SUBJ_COLORS  = {colors_json};
const SUBJ_TEXT    = {text_colors_json};
const LIGHT_MAX    = 2;
const LAB_SUBJS    = new Set(['CS','IT','Math','Science','Biology','Physics','Chemistry']);

function switchTab(id) {{
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('page-'+ id).classList.add('active');
  document.getElementById('tab-' + id).classList.add('active');
  if (id === 'master' && !masterBuilt) buildMaster();
}}

const dayLoad = (t, day) => (SCHED[t]?.[day]||[]).filter(Boolean).length;
const isFree  = (t, day, pi) => !SCHED[t]?.[day]?.[pi];
function subRow(rCls, dCls, tCls, tTxt, t, dl) {{
  const wl = WK_LOAD[t]||'?';
  return `<div class="sub-row ${{rCls}}"><span class="ld ${{dCls}}"></span>
    <span class="sub-name${{rCls==='sr-busy'?' dim':''}}">${{t}}</span>
    <span class="sub-today">${{dl===0?'Free all day':dl+' cls today'}}</span>
    <span class="sub-wk">${{wl}}/wk</span>
    <span class="tag ${{tCls}}">${{tTxt}}</span></div>`;
}}
function chipHtml(t, dl) {{
  const c  = dl===0?'chip-free':dl<=LIGHT_MAX?'chip-light':'chip-busy';
  const bg = dl===0?'var(--green2)':dl<=LIGHT_MAX?'var(--amber2)':'#aaa';
  return `<div class="chip ${{c}}"><span class="chip-dot" style="background:${{bg}}"></span>
    <span>${{t}}</span><span class="chip-wk">${{dl===0?'free':dl+'cls'}}·${{WK_LOAD[t]||'?'}}/wk</span></div>`;
}}

/* ── TAB 1: SUBSTITUTE FINDER ── */
let subDay=null, absent=new Set();
function initSub() {{
  const dg=document.getElementById('sub-day-grid');
  DAYS.forEach(d=>{{
    const b=document.createElement('button');
    b.className='pill-btn'+(d==='Sat'?' sat':'');
    b.textContent=d; b.id='sdb-'+d; b.onclick=()=>pickSubDay(d); dg.appendChild(b);
  }});
  const tl=document.getElementById('sub-t-list');
  Object.keys(SCHED).sort().forEach(t=>{{
    const wl=WK_LOAD[t]||0;
    const pc=wl>=30?'lp-hi':wl>=27?'lp-mid':'lp-lo';
    const el=document.createElement('label');
    el.className='t-item'; el.id='sti-'+t;
    el.innerHTML=`<input type="checkbox" id="schk-${{t}}" onchange="toggleAbsent('${{t}}')">
      <span class="t-name">${{t}}</span><span class="lpill ${{pc}}">${{wl}}/wk</span>`;
    tl.appendChild(el);
  }});
}}
function pickSubDay(d){{subDay=d;DAYS.forEach(x=>document.getElementById('sdb-'+x).classList.toggle('active',x===d));checkSubReady();}}
function toggleAbsent(t){{const c=document.getElementById('schk-'+t);c.checked?absent.add(t):absent.delete(t);document.getElementById('sti-'+t).classList.toggle('absent',c.checked);checkSubReady();}}
function checkSubReady(){{document.getElementById('sub-find-btn').disabled=!(subDay&&absent.size>0);}}
function findSubs() {{
  if (!subDay||absent.size===0) return;
  const ALL=Object.keys(SCHED), byP={{}};
  absent.forEach(t=>(SCHED[t]?.[subDay]||[]).forEach((sl,pi)=>sl&&(byP[pi]=byP[pi]||[]).push({{absTeacher:t,cls:sl.class,subj:sl.subject}})));
  document.getElementById('sub-res-head').textContent=`📋  Results — ${{subDay}} · ${{absent.size}} absent teacher${{absent.size>1?'s':''}}`;
  const piK=Object.keys(byP).map(Number).sort((a,b)=>a-b);
  if(!piK.length){{document.getElementById('sub-res-body').innerHTML=`<div class="empty"><div class="eico">🎉</div><p>No classes on ${{subDay}}. No cover needed!</p></div>`;return;}}
  const tot=piK.reduce((s,pi)=>s+byP[pi].length,0);
  let html=`<div class="summary"><span><span class="sdot" style="background:var(--red2)"></span><strong>${{absent.size}}</strong> absent</span><span><span class="sdot" style="background:var(--amber2)"></span><strong>${{tot}}</strong> class${{tot>1?'es':''}} need cover</span><span><span class="sdot" style="background:var(--green2)"></span>Day: <strong>${{subDay}}</strong></span><span class="legend"><span><span class="sdot" style="background:var(--green2)"></span>Free all day</span><span><span class="sdot" style="background:var(--amber2)"></span>Light (≤${{LIGHT_MAX}})</span><span><span class="sdot" style="background:#aaa"></span>Busy</span></span></div>`;
  piK.forEach(pi=>{{
    html+=`<div class="pblock"><div class="pblock-head"><span>${{PERIODS[pi]}}</span><span class="ph-time">${{TIMES[pi]}}</span></div><div class="pblock-body">`;
    byP[pi].forEach(({{absTeacher:aT,cls,subj}})=>{{
      const fN=ALL.filter(t=>!absent.has(t)&&isFree(t,subDay,pi));
      const byWk=a=>[...a].sort((x,y)=>(WK_LOAD[x]||0)-(WK_LOAD[y]||0));
      const tF=byWk(fN.filter(t=>dayLoad(t,subDay)===0));
      const tL=byWk(fN.filter(t=>{{const dl=dayLoad(t,subDay);return dl>0&&dl<=LIGHT_MAX;}}));
      const tB=byWk(fN.filter(t=>dayLoad(t,subDay)>LIGHT_MAX));
      html+=`<div class="arow"><div class="badge-stack"><div class="cls-badge">Cls ${{cls}}</div><div class="subj-badge">${{subj}}</div></div><div><div class="absent-lbl">✖ ${{aT}} <em>is absent</em></div><div class="subs-list">`;
      if(!fN.length) html+=`<div class="no-avail">⚠ No free teachers this period</div>`;
      else{{tF.forEach(t=>html+=subRow('sr-free','ld-free','tag-free','🟢 Free today',t,0));tL.forEach(t=>html+=subRow('sr-light','ld-light','tag-light','🟡 Light',t,dayLoad(t,subDay)));tB.forEach(t=>html+=subRow('sr-busy','ld-busy','tag-busy','⬜ Busy',t,dayLoad(t,subDay)));}}
      html+=`</div></div></div>`;
    }});
    html+=`</div></div>`;
  }});
  document.getElementById('sub-res-body').innerHTML=html;
}}
function resetSub(){{subDay=null;absent.clear();DAYS.forEach(d=>document.getElementById('sdb-'+d)?.classList.remove('active'));Object.keys(SCHED).forEach(t=>{{const c=document.getElementById('schk-'+t),i=document.getElementById('sti-'+t);if(c)c.checked=false;if(i)i.classList.remove('absent');}});document.getElementById('sub-find-btn').disabled=true;document.getElementById('sub-res-head').textContent='📋 \u00a0Results';document.getElementById('sub-res-body').innerHTML=`<div class="empty"><div class="eico">🔍</div><p>Select a day and mark absent teacher(s),<br>then click <strong>Find Available Substitutes</strong>.</p></div>`;}}

/* ── TAB 2: PERIOD COVERAGE ── */
let covCls=null,covDay=null,covType='all';
function initCov(){{
  const cg=document.getElementById('cov-cls-grid');
  CLASSES.forEach(cls=>{{const b=document.createElement('button');b.className='pill-btn';b.textContent=cls;b.id='ccls-'+cls;b.onclick=()=>pickCovCls(cls);cg.appendChild(b);}});
  const dg=document.getElementById('cov-day-grid');
  DAYS.forEach(d=>{{const b=document.createElement('button');b.className='pill-btn'+(d==='Sat'?' sat':'');b.textContent=d;b.id='cdb-'+d;b.onclick=()=>pickCovDay(d);dg.appendChild(b);}});
}}
function pickCovCls(cls){{covCls=cls;CLASSES.forEach(c=>{{const b=document.getElementById('ccls-'+c);b.classList.toggle('active',c===cls);}});checkCovReady();}}
function pickCovDay(d){{covDay=d;DAYS.forEach(x=>document.getElementById('cdb-'+x).classList.toggle('active',x===d));checkCovReady();}}
function setTypeFilter(type){{covType=type;document.querySelectorAll('#cov-type-pills .spec-pill').forEach(b=>b.classList.toggle('active',b.dataset.type===type));if(covCls&&covDay)findCoverage();}}
function checkCovReady(){{document.getElementById('cov-find-btn').disabled=!(covCls&&covDay);}}
function findCoverage(){{
  if(!covCls||!covDay)return;
  document.getElementById('cov-res-head').textContent=`📋  Class ${{covCls}} — ${{covDay}}`;
  const slots=(COVERAGE[covCls]?.[covDay]||[]).filter(s=>covType==='all'||s.type===covType);
  if(!slots.length){{document.getElementById('cov-res-body').innerHTML=`<div class="empty"><div class="eico">🎉</div><p>No ${{covType==='all'?'special':covType}} periods for Class ${{covCls}} on ${{covDay}}.</p></div>`;return;}}
  const allSl=COVERAGE[covCls]?.[covDay]||[],tC={{}};
  allSl.forEach(s=>tC[s.type]=(tC[s.type]||0)+1);
  const tO=['Free','Library'],tCss={{Free:'st-free',Library:'st-library'}},tIco={{Free:'—',Library:'📚'}};
  let html=`<div class="summary"><span>Class <strong>${{covCls}}</strong> on <strong>${{covDay}}</strong>:</span>${{tO.filter(t=>tC[t]).map(t=>`<span class="spec-tag ${{tCss[t]}}">${{tIco[t]}} ${{tC[t]}}× ${{t}}</span>`).join('')}}<span class="legend"><span><span class="sdot" style="background:var(--green2)"></span>Free all day</span><span><span class="sdot" style="background:var(--amber2)"></span>Light day</span></span></div>`;
  slots.forEach(sl=>{{
    const hC=`ch-${{sl.type==='Free'?'f':'l'}}`;
    html+=`<div class="cov-slot"><div class="cov-head ${{hC}}"><span>${{tIco[sl.type]||''}} ${{sl.type}}</span><span style="font-weight:400;font-size:.7rem;opacity:.8">${{sl.period}} · ${{sl.time}}</span></div><div class="cov-body">`;
    if(!sl.free.length) html+=`<div class="no-cov">⚠ No teachers free this period</div>`;
    else{{
      const byWk=[...sl.free].sort((a,b)=>a.wk_load-b.wk_load);
      html+=`<div class="chip-grid">${{byWk.map(f=>chipHtml(f.name,f.day_load)).join('')}}</div>`;
      const nF=sl.free.filter(f=>f.day_load===0).length,nL=sl.free.filter(f=>f.day_load>0&&f.day_load<=LIGHT_MAX).length,nB=sl.free.filter(f=>f.day_load>LIGHT_MAX).length;
      html+=`<div style="margin-top:7px;font-size:.66rem;color:var(--ink3)">${{sl.free.length}} teacher${{sl.free.length>1?'s':''}} free &nbsp;·&nbsp;${{nF?`<span style="color:var(--green)">${{nF}} fully free</span>&nbsp;`:''}}${{nL?`<span style="color:var(--amber)">${{nL}} light</span>&nbsp;`:''}}${{nB?`<span style="color:#888">${{nB}} busy</span>`:''}}</div>`;
    }}
    html+=`</div></div>`;
  }});
  document.getElementById('cov-res-body').innerHTML=html;
}}
function resetCov(){{covCls=null;covDay=null;covType='all';CLASSES.forEach(c=>document.getElementById('ccls-'+c)?.classList.remove('active'));DAYS.forEach(d=>document.getElementById('cdb-'+d)?.classList.remove('active'));document.querySelectorAll('#cov-type-pills .spec-pill').forEach(b=>b.classList.toggle('active',b.dataset.type==='all'));document.getElementById('cov-find-btn').disabled=true;document.getElementById('cov-res-head').textContent='📋 \u00a0Coverage Results';document.getElementById('cov-res-body').innerHTML=`<div class="empty"><div class="eico">📋</div><p>Select a class and day to see which teachers<br>are available for each non-teaching period.</p></div>`;}}

/* ── TAB 3: MASTER TIMETABLE ── */
let masterBuilt = false;
let masterMode  = 'class';

function buildMaster() {{
  populateMasterSelects();
  renderTable();
  buildLegend();
  masterBuilt = true;
}}

function populateMasterSelects() {{
  const sc = document.getElementById('sel-class');
  const st = document.getElementById('sel-teacher');
  const sd = document.getElementById('sel-day');
  CLASSES.forEach(c => {{ const o=document.createElement('option'); o.value=c; o.textContent='Class '+c; sc.appendChild(o); }});
  TEACHERS.forEach(t => {{ const o=document.createElement('option'); o.value=t; o.textContent=t; st.appendChild(o); }});
  DAYS.forEach(d => {{ const o=document.createElement('option'); o.value=d; o.textContent=d; sd.appendChild(o); }});
}}

function setMode(mode) {{
  masterMode = mode;
  document.getElementById('mode-cls').classList.toggle('active', mode==='class');
  document.getElementById('mode-tch').classList.toggle('active', mode==='teacher');
  document.getElementById('fg-teacher-lbl').textContent = mode==='class' ? 'Highlight teacher' : 'Select teacher';
  document.getElementById('sel-teacher').value = '';
  renderTable();
  updateStats();
}}

function renderTable() {{
  const thead = document.getElementById('tt-thead');
  const tbody = document.getElementById('tt-tbody');
  let hRow = '<tr>';
  hRow += `<th style="min-width:70px">Class</th>`;
  hRow += `<th style="min-width:48px;position:sticky;left:70px;z-index:110;background:var(--navy)">Day</th>`;
  PERIODS.forEach((p, i) => {{
    hRow += `<th>${{p}}<span class="ph-time">${{TIMES[i]}}</span></th>`;
  }});
  hRow += '</tr>';
  thead.innerHTML = hRow;
  tbody.innerHTML = masterMode === 'class' ? buildClassBody() : buildTeacherBody();
  applyFilters();
}}

function cellStyle(subj) {{
  const bg  = SUBJ_COLORS[subj] || '#f8f9fa';
  const txt = SUBJ_TEXT[subj]   || '';
  return `background:${{bg}};${{txt?'color:'+txt+';':''}}`;
}}

function specialCellClass(subj) {{
  const map = {{Free:'sp-free-cell',Library:'sp-library-cell'}};
  return map[subj] || '';
}}

function specialLabel(subj) {{
  const map = {{Free:'— Free',Library:'📚 Library'}};
  return map[subj] || subj;
}}

function buildClassBody() {{
  let rows = '';
  CLASSES.forEach(cls => {{
    rows += `<tr class="cls-header-row" data-cls="${{cls}}"><td colspan="10">CLASS ${{cls}}</td></tr>`;
    DAYS.forEach(day => {{
      const isSat = day === 'Sat';
      rows += `<tr class="cls-row" data-cls="${{cls}}" data-day="${{day}}">`;
      rows += `<td class="col-cls">${{cls}}</td>`;
      rows += `<td class="col-day${{isSat?' sat-day':''}}">${{day}}</td>`;
      const daySlots = CLASS_TT[cls][day];
      daySlots.forEach((slot, pi) => {{
        const subj    = slot.s || '';
        const teacher = slot.t || '';
        const isLab   = slot.l && subj;
        const specCls = specialCellClass(subj);
        const gapCls  = pi===0 ? ' gap-drill' : pi===3 ? ' gap-break' : '';
        const satCls  = isSat ? ' sat-col' : '';
        const tAttr   = teacher ? ` data-teacher="${{teacher}}"` : '';
        const sAttr   = subj    ? ` data-subj="${{subj}}"`       : '';
        rows += `<td class="tt-cell${{specCls?' '+specCls:''}}${{gapCls}}${{satCls}}"${{tAttr}}${{sAttr}}>`;
        if (!subj) {{
          rows += `<div class="cell-inner"></div>`;
        }} else if (specCls) {{
          rows += `<div class="cell-inner"><span class="cell-subj">${{specialLabel(subj)}}</span></div>`;
        }} else {{
          rows += `<div class="cell-inner" style="${{cellStyle(subj)}}">`;
          rows += `<span class="cell-subj">${{subj}}</span>`;
          if (teacher) rows += `<span class="cell-teacher">${{teacher}}</span>`;
          if (isLab)   rows += `<span class="cell-lab">★</span>`;
          rows += `</div>`;
        }}
        rows += `</td>`;
      }});
      rows += `</tr>`;
    }});
  }});
  return rows;
}}

function buildTeacherBody() {{
  const selTeacher = document.getElementById('sel-teacher').value;
  const teachersToShow = selTeacher ? [selTeacher] : TEACHERS;
  let rows = '';
  teachersToShow.forEach(teacher => {{
    rows += `<tr class="cls-header-row" data-teacher="${{teacher}}">
      <td colspan="10">${{teacher}} &nbsp;<span style="font-weight:400;font-size:.76rem;opacity:.7">${{WK_LOAD[teacher]||0}} periods/week</span></td></tr>`;
    DAYS.forEach(day => {{
      const isSat = day === 'Sat';
      rows += `<tr class="cls-row" data-teacher="${{teacher}}" data-day="${{day}}">`;
      rows += `<td class="col-cls">${{teacher.split(' ')[0]}}</td>`;
      rows += `<td class="col-day${{isSat?' sat-day':''}}">${{day}}</td>`;
      const daySlots = TEACHER_VIEW[teacher][day];
      daySlots.forEach((slot, pi) => {{
        const gapCls = pi===2 ? ' gap-break' : pi===4 ? ' gap-lunch' : '';
        const satCls = isSat ? ' sat-col' : '';
        if (!slot) {{
          rows += `<td class="tt-cell t-free${{gapCls}}${{satCls}}"><div class="cell-inner"><span class="t-free-lbl">free</span></div></td>`;
        }} else {{
          const subj = slot.s || '', cls = slot.cls || '';
          rows += `<td class="tt-cell${{gapCls}}${{satCls}}" data-subj="${{subj}}" data-cls="${{cls}}">`;
          rows += `<div class="cell-inner" style="${{cellStyle(subj)}}">`;
          rows += `<span class="cell-subj">${{subj}}</span>`;
          rows += `<span class="cell-teacher">Cls ${{cls}}</span>`;
          if (slot.l) rows += `<span class="cell-lab">★</span>`;
          rows += `</div></td>`;
        }}
      }});
      rows += `</tr>`;
    }});
  }});
  return rows;
}}

function applyFilters() {{
  const table      = document.getElementById('tt-table');
  const selCls     = document.getElementById('sel-class').value;
  const selTeacher = document.getElementById('sel-teacher').value;
  const selDay     = document.getElementById('sel-day').value;
  const search     = document.getElementById('search-subj').value.trim().toLowerCase();
  table.className = 'tt-table';
  const rows = table.querySelectorAll('tr.cls-row');
  if (masterMode === 'class') {{
    if (selCls || selDay) {{
      table.classList.add(selCls ? 'filter-cls' : 'filter-day');
      rows.forEach(row => {{
        const clsOk = !selCls || row.dataset.cls === selCls;
        const dayOk = !selDay || row.dataset.day === selDay;
        if (clsOk && dayOk) row.classList.add(selCls ? 'cls-match' : 'day-match');
        else row.classList.remove('cls-match','day-match');
      }});
    }}
    if (selTeacher) {{
      table.classList.add('filter-teacher');
      table.querySelectorAll('.tt-cell').forEach(cell => {{
        cell.classList.toggle('t-match', cell.dataset.teacher === selTeacher);
      }});
    }}
  }} else {{
    if (selDay) {{
      table.classList.add('filter-day');
      rows.forEach(row => {{
        if (row.dataset.day === selDay) row.classList.add('day-match');
        else row.classList.remove('day-match');
      }});
    }}
  }}
  table.querySelectorAll('.tt-cell').forEach(cell => {{
    if (search) {{
      cell.classList.toggle('s-match', (cell.dataset.subj||'').toLowerCase().includes(search));
    }} else {{
      cell.classList.remove('s-match');
    }}
  }});
  updateStats();
}}

function clearFilters() {{
  document.getElementById('sel-class').value   = '';
  document.getElementById('sel-teacher').value = '';
  document.getElementById('sel-day').value     = '';
  document.getElementById('search-subj').value = '';
  if (masterMode === 'teacher') renderTable();
  else applyFilters();
}}

function updateStats() {{
  const selCls = document.getElementById('sel-class').value;
  const selT   = document.getElementById('sel-teacher').value;
  const selDay = document.getElementById('sel-day').value;
  const search = document.getElementById('search-subj').value.trim();
  let parts = [];
  if (masterMode === 'class') {{
    if (selCls) parts.push(`Class <strong>${{selCls}}</strong>`);
    if (selT)   parts.push(`Highlighting <strong>${{selT}}</strong>`);
    if (selDay) parts.push(`Day <strong>${{selDay}}</strong>`);
  }} else {{
    if (selT)   parts.push(`Teacher <strong>${{selT}}</strong>`);
    if (selDay) parts.push(`Day <strong>${{selDay}}</strong>`);
  }}
  if (search) parts.push(`Search: <strong>${{search}}</strong>`);
  const el = document.getElementById('master-stats');
  el.innerHTML = parts.length ? parts.join(' &nbsp;·&nbsp; ') :
    (masterMode==='class'
      ? `Showing all <strong>${{CLASSES.length}}</strong> classes × <strong>6</strong> days`
      : `Showing all <strong>${{TEACHERS.length}}</strong> teachers × <strong>6</strong> days`);
}}

function buildLegend() {{
  const strip = document.getElementById('legend-strip');
  const subjects = ['Math','Science','English','SST','Hindi','Odia','Sanskrit','CS','IT','Biology','Physics','Chemistry'];
  const specials = ['Free','Library'];
  let html = '<span style="font-size:.68rem;font-weight:800;color:var(--ink3);margin-right:4px">SUBJECTS:</span>';
  subjects.forEach(s => {{
    const bg = SUBJ_COLORS[s]||'#eee', txt = SUBJ_TEXT[s]||'inherit';
    html += `<span class="lchip" style="background:${{bg}};color:${{txt}}">${{s}}</span>`;
  }});
  html += '<span style="font-size:.68rem;font-weight:800;color:var(--ink3);margin:0 4px 0 10px">SPECIALS:</span>';
  specials.forEach(s => {{
    const bg = SUBJ_COLORS[s]||'#eee', txt = SUBJ_TEXT[s]||'inherit';
    html += `<span class="lchip" style="background:${{bg}};color:${{txt}}">${{s}}</span>`;
  }});
  html += '<span class="lchip" style="background:var(--sky);color:var(--blue);margin-left:10px">★ = Lab/Practical</span>';
  strip.innerHTML = html;
}}

/* ── TAB 4: TEACHER LOADS ── */
function renderTeacherLoads() {{
  const container = document.getElementById('tload-body');
  const filter = (document.getElementById('tload-search').value||'').toLowerCase();
  const teachers = Object.keys(TLD).sort().filter(t => !filter || t.toLowerCase().includes(filter));
  let html = '';
  teachers.forEach(t => {{
    const rows = TLD[t];
    const total = rows.reduce((s,r) => s+r.subtotal, 0);
    html += `<div class="tl-block">
      <div class="tl-header">
        <span class="tl-name">${{t}}</span>
        <span class="tl-total">${{total}} periods / week</span>
      </div>
      <table class="tl-table">
        <thead><tr><th>Subject</th><th>Classes</th><th>Periods/Class</th><th>Subtotal</th></tr></thead>
        <tbody>`;
    rows.forEach(r => {{
      html += `<tr>
        <td style="background:${{SUBJ_COLORS[r.subject]||'#f9f9f9'}}">${{r.subject}}</td>
        <td>${{r.classes}}</td>
        <td style="text-align:center">${{r.per_class}}</td>
        <td style="text-align:center;font-weight:700">${{r.subtotal}}</td>
      </tr>`;
    }});
    html += `<tr class="tl-total-row"><td colspan="3" style="text-align:right;font-weight:700">Total</td>
      <td style="text-align:center;font-weight:800">${{total}}</td></tr>`;
    html += `</tbody></table></div>`;
  }});
  container.innerHTML = html || '<p style="padding:20px;color:#888">No teachers match.</p>';
}}

initSub();
initCov();
renderTeacherLoads();
</script>

<!-- TAB 4: TEACHER LOADS PAGE -->
<div class="page" id="page-tload">
<div class="inner">
  <div class="card" style="margin-bottom:16px">
    <div class="ch ch-indigo">📚 &nbsp;Teacher Subject Loads — Periods per Week</div>
    <div class="cb" style="padding:10px 16px">
      <input id="tload-search" type="search" placeholder="Filter by teacher name…"
        oninput="renderTeacherLoads()"
        style="width:280px;padding:6px 10px;border:1px solid var(--border);border-radius:6px;font-size:.85rem">
    </div>
  </div>
  <div id="tload-body" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:16px"></div>
</div>
</div>

<style>
.tl-block{{background:var(--white);border-radius:var(--rlg);box-shadow:var(--sh);border:1px solid var(--border);overflow:hidden}}
.tl-header{{background:var(--navy);color:#fff;padding:10px 16px;display:flex;justify-content:space-between;align-items:center}}
.tl-name{{font-weight:800;font-size:.95rem}}
.tl-total{{font-size:.8rem;opacity:.8;font-weight:600}}
.tl-table{{width:100%;border-collapse:collapse;font-size:.8rem}}
.tl-table th{{background:var(--paper);padding:6px 10px;text-align:left;font-size:.72rem;font-weight:800;color:var(--ink2);border-bottom:1px solid var(--border)}}
.tl-table td{{padding:5px 10px;border-bottom:1px solid var(--border)}}
.tl-table tr:last-child td{{border-bottom:none}}
.tl-total-row td{{background:var(--sky);color:var(--blue)}}
</style>

</body>
</html>"""


# ── Public entry point ────────────────────────────────────────────────────────

def generate_html(timetable_state, events, output_path='Timetable_Tools.html'):
    """
    Generate the interactive Timetable_Tools.html from solver output.

    Parameters
    ----------
    timetable_state : dict
        Keys: (event_idx, instance) tuples.
        Values: {'class', 'day' (int 0-5), 'period' (int 0-5), 'subject', 'teacher'}.
    events : list
        Event dicts — used for teacher load detail breakdown.
    output_path : str
        Destination file path.
    """
    (
        class_timetable, teacher_sched, teacher_view,
        coverage, wk_load, special_counts, all_teachers,
        teacher_load_detail,
    ) = _build_structures(timetable_state, events)

    html = _build_html(
        class_timetable, teacher_sched, teacher_view,
        coverage, wk_load, special_counts, all_teachers,
        teacher_load_detail,
    )

    Path(output_path).write_text(html, encoding='utf-8')
    size_kb = Path(output_path).stat().st_size / 1024
    print(f"      HTML written to {output_path}  ({size_kb:.1f} KB)")
    print("      Tabs: 🔍 Substitute Finder | 📋 Period Coverage | 📊 Master Timetable | 📚 Teacher Loads")
