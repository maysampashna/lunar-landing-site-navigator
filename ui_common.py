"""Shared UI helpers for the Streamlit pages."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from engine import data, visibility
from engine.metrics import ScoreWeights

SUN, EARTH, BOTH, GREY = "#F5A623", "#4A90E2", "#7ED321", "#8A8F98"
ROOT = Path(__file__).resolve().parent
DEFAULT_WEIGHTS = ScoreWeights()


@st.cache_data
def sites_df() -> pd.DataFrame:
    return data.load_sites()


@st.cache_data
def ephem(site_id: str) -> pd.DataFrame:
    return data.load_ephem(site_id)


def horizon(site_id: str):
    return data.load_horizon(site_id)


def terrain_status(site_id: str) -> str:
    """'real' | 'synthetic' | 'missing'"""
    if data.load_horizon(site_id) is None:
        return "missing"
    return "synthetic" if data.is_synthetic(site_id) else "real"


def names() -> dict[str, str]:
    s = sites_df()
    return dict(zip(s.site_id, s.name))


@st.cache_data
def hourly_vis(site_id: str, thr: float, mask: float, area: float, eff: float, load: float) -> pd.DataFrame:
    from engine.power import PowerParams
    p = visibility.VisParams(sunlit_threshold=thr, earth_mask_deg=mask,
                             power=PowerParams(array_area_m2=area, efficiency=eff, load_w=load))
    return visibility.compute(ephem(site_id), horizon(site_id), p)


def data_banners(site_ids) -> dict[str, list[str]]:
    """Show warnings about non-final data. Returns {'synthetic': [...], 'missing': [...], 'provisional': [...]}"""
    nm = names()
    s = sites_df().set_index("site_id")
    out = {"synthetic": [], "missing": [], "provisional": []}
    for sid in site_ids:
        st_ = terrain_status(sid)
        if st_ != "real":
            out[st_].append(nm[sid])
        if str(s.loc[sid, "provisional"]).lower() == "true":
            out["provisional"].append(nm[sid])
    if out["synthetic"] or out["missing"]:
        st.error("🧪 **DEMONSTRATION RESULTS — not a recommendation.** "
                 + (f"Synthetic terrain: {', '.join(out['synthetic'])}. " if out["synthetic"] else "")
                 + (f"No terrain data: {', '.join(out['missing'])}. " if out["missing"] else "")
                 + "Confident rankings require real LOLA terrain horizons.")
    if out["provisional"]:
        st.warning(f"Provisional site coordinates (to be replaced from the USGS region data): "
                   f"{', '.join(out['provisional'])}")
    return out


def validation_report() -> dict | None:
    p = ROOT / "data" / "validation.json"
    return json.loads(p.read_text()) if p.exists() else None


def weights_sidebar() -> ScoreWeights:
    with st.expander("Score weights (your preferences)"):
        w = ScoreWeights(st.slider("Sunlight", 0.0, 1.0, DEFAULT_WEIGHTS.w_sun),
                         st.slider("Earth visibility", 0.0, 1.0, DEFAULT_WEIGHTS.w_dte),
                         st.slider("Both at once", 0.0, 1.0, DEFAULT_WEIGHTS.w_both),
                         st.slider("Penalty: longest dark gap", 0.0, 0.5, DEFAULT_WEIGHTS.w_gap_dark),
                         st.slider("Penalty: longest no-Earth gap", 0.0, 0.5, DEFAULT_WEIGHTS.w_gap_dte))
        if not w.is_valid():
            st.warning("Sunlight, Earth visibility and Both cannot all be zero — using the default weights.")
            w = DEFAULT_WEIGHTS
        st.caption("Positive weights are rescaled to sum to 1. The score is a preference calculation, not a "
                   "safety rating.")
    return w


LIMITATIONS = ("Geometric line of sight only. Not assessed: landing hazards, slopes, thermal environment, RF link "
               "budget, antenna scheduling. Power/storage values are illustrative estimates, not a flight design. "
               "Surface-start shifts assume arrival moves by exactly the shift (sensitivity analysis, not a "
               "trajectory model). Sites are representative points, not NASA-designated landing sites. 8 of the 9 Artemis III "
               "regions are included: the USGS download for Mons Mouton Plateau failed during the event.")
