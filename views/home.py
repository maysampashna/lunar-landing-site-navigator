"""Home — a quick ranking of the sites for a chosen date, then two ways in for the details."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from engine import finder
from engine.metrics import ScoreWeights
from engine.power import PowerParams
import ui_common as ui

ui.setup_page()
names = ui.names()

st.markdown(f'<div class="lln-banner lln-hero"><div class="row">{ui.mi("rocket_launch", 46, "#F2F8FA")}'
            '<div><h1>Lunar Landing Site Navigator</h1><div class="sub">Compare lunar south-pole landing sites by '
            'sunlight, Earth visibility, communication and mission timing — computed from NASA data.</div>'
            f'<div style="margin-top:12px">{ui.validated_pill()}</div></div></div></div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ quick ranking
with st.container(key="card_quick"):
    ui.card_title("leaderboard", "Quick site ranking", "pick sites and a landing date")
    c1, c2, c3 = st.columns([2.4, 1, 1])
    chosen = c1.multiselect("Sites", list(names), format_func=names.get, key="m_sites")
    c2.date_input("Landing date (UTC)", min_value=pd.Timestamp("2026-01-02").date(),
                  max_value=pd.Timestamp("2031-02-10").date(), key="m_date")
    dur = c3.slider("Surface stay (days)", 1.0, 14.0, step=0.5, key="m_dur")
    if not chosen:
        st.info("Pick at least one site.")
    else:
        start = ui.mission_start()
        vis = {s: ui.site_vis_hourly(s) for s in chosen}
        try:
            table, best = finder.shift_compare(vis, start, duration_h=dur * 24, shifts_h=(0, 24, 48),
                                               weights=ScoreWeights(), power=PowerParams(),
                                               terrain_real={s: ui.terrain_status(s) == "real" for s in chosen})
        except finder.DateRangeError:
            st.warning("Choose an earlier date or a shorter stay.")
            st.stop()
        base = table[table.shift_h == 0].set_index("site_id")
        worst = base["worst_case_score"]
        order = sorted(chosen, key=lambda s: (-round(worst[s]), -base.loc[s, "pct_both"], names[s].casefold()))
        top = round(worst[order[0]])
        winners = [s for s in order if round(worst[s]) == top]
        left, right = st.columns([1.7, 1], gap="medium")
        with left:
            rows = []
            for sid in order:
                r = base.loc[sid]
                lab, col = ui.rating(r.worst_case_score)
                rank = 1 + sum(round(worst[x]) > round(worst[sid]) for x in order)
                tied = sum(round(worst[x]) == round(worst[sid]) for x in order) > 1
                rows.append(
                    f'<tr class="{"top" if sid in winners else ""}"><td>{rank}{"=" if tied else ""}</td>'
                    f'<td><b>{names[sid]}</b></td><td class="n">{r.pct_sunlit:.0f}%</td>'
                    f'<td class="n">{r.pct_dte:.0f}%</td><td class="n"><span class="lln-bar" style="width:'
                    f'{max(3, 0.6 * r.worst_case_score):.0f}px;background:{ui.TEAL}"></span>&nbsp;'
                    f'<b>{r.worst_case_score:.0f}</b></td><td>{ui.chip(lab, col)}</td></tr>')
            st.markdown(
                '<table class="lln-table"><tr><th>#</th><th>Site</th>'
                '<th class="n" title="Share of the stay with sunlight for power">Sunlight</th>'
                '<th class="n" title="Share of the stay with Earth in view and a DSN complex seeing the Moon">'
                'Earth contact</th><th class="n" title="Lowest score if landing slips 0, +24 or +48 h">'
                'Score (worst case)</th><th>Rating</th></tr>' + "".join(rows) + "</table>", unsafe_allow_html=True)
            best_txt = " & ".join(names[s] for s in winners)
            st.markdown(
                f'<div style="margin-top:10px;font-size:0.98rem">{ui.mi("flag", 20, ui.AMBER)} '
                f'<b style="color:{ui.AMBER}">{"Tied best" if len(winners) > 1 else "Best"}: {best_txt}</b>'
                f'<span style="color:#9FB4C0"> · {dur:g}-day stay from {start:%Y-%m-%d %H:%M} UTC. '
                'Modeled comparison, not a landing-safety assessment.</span></div>', unsafe_allow_html=True)
        with right:
            st.plotly_chart(ui.south_pole_map(chosen, worst.to_dict(), height=330, highlight=winners[0]),
                            width="stretch", config=ui.MAP_CONFIG)

# ------------------------------------------------------------------ two ways into the details
st.markdown('<div class="lln-sec" style="color:#7FF0DD;font-size:1.05rem">Want the details?</div>',
            unsafe_allow_html=True)
e, m = st.columns(2, gap="medium")
with e:
    with st.container(key="card_explorer"):
        st.markdown(f'<div class="lln-mode">{ui.mi("groups", 36, ui.TEAL)}<h3>Explorer Mode</h3>'
                    '<p>Stand at a site in 3D and watch the Sun and Earth move over the real terrain.</p></div>',
                    unsafe_allow_html=True)
        st.page_link("views/sky_view.py", label="Start exploring", icon=":material/arrow_forward:")
with m:
    with st.container(key="amber_missioncontrol"):
        st.markdown(f'<div class="lln-mode">{ui.mi("tune", 36, ui.AMBER)}<h3>Mission Control Mode</h3>'
                    '<p>Mission clock, DSN geometry, schedule risk, power and every control.</p></div>',
                    unsafe_allow_html=True)
        st.page_link("views/overview.py", label="Open Mission Control", icon=":material/arrow_forward:")

for col, (page, label, icon) in zip(st.columns(4, gap="medium"), [
        ("views/overview.py", "Mission Overview", ":material/bar_chart:"),
        ("views/sky_view.py", "Sky View", ":material/landscape:"),
        ("views/date_finder.py", "Date Finder", ":material/calendar_month:"),
        ("views/validation.py", "Validation & Sources", ":material/fact_check:")]):
    with col:
        with st.container(key=f"card_nav_{label.split()[0]}"):
            st.page_link(page, label=label, icon=icon)

ui.footer(link=False)
