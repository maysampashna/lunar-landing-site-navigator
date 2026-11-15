"""Window metrics and the site score.

score = 100 * clip( w_sun*f_sun + w_dte*f_dte + w_both*f_both - w_gd*g_dark - w_ge*g_dte, 0, 1 )
  positive weights are always renormalised to sum to 1;
  g_dark = min(longest_dark_h / T_win, 1); g_dte = min(longest_no_dte_h / T_win, 1)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .power import PowerParams, energy_summary


@dataclass
class ScoreWeights:
    w_sun: float = 0.35
    w_dte: float = 0.35
    w_both: float = 0.30
    w_gap_dark: float = 0.15
    w_gap_dte: float = 0.15

    def is_valid(self) -> bool:
        return min(self.w_sun, self.w_dte, self.w_both, self.w_gap_dark, self.w_gap_dte) >= 0 and \
            (self.w_sun + self.w_dte + self.w_both) > 0

    def normalized(self) -> "ScoreWeights":
        s = self.w_sun + self.w_dte + self.w_both
        if s <= 0:
            raise ValueError("At least one positive score weight must be > 0")
        return ScoreWeights(self.w_sun / s, self.w_dte / s, self.w_both / s, self.w_gap_dark, self.w_gap_dte)


def longest_run_hours(mask, dt_h: float) -> float:
    """Longest run of consecutive True values, in hours."""
    m = np.asarray(mask, dtype=bool)
    if not m.any():
        return 0.0
    padded = np.concatenate([[False], m, [False]])
    edges = np.flatnonzero(np.diff(padded.astype(int)))
    return float((edges[1::2] - edges[0::2]).max() * dt_h)


def score_from(f_sun, f_dte, f_both, longest_dark_h, longest_no_dte_h, window_h, w: ScoreWeights) -> float:
    w = w.normalized()
    g_dark = min(longest_dark_h / window_h, 1.0)
    g_dte = min(longest_no_dte_h / window_h, 1.0)
    raw = w.w_sun * f_sun + w.w_dte * f_dte + w.w_both * f_both - w.w_gap_dark * g_dark - w.w_gap_dte * g_dte
    return float(100.0 * np.clip(raw, 0.0, 1.0))


def summarize(vis: pd.DataFrame, dt_h: float, weights: ScoreWeights | None = None,
              power: PowerParams | None = None, include_energy: bool = True) -> dict:
    weights = weights or ScoreWeights()
    n = len(vis)
    window_h = n * dt_h
    sunlit = vis["sunlit"].to_numpy()
    dte = vis["dte_visible"].to_numpy()
    both = sunlit & dte
    m = {
        "window_h": window_h,
        "pct_sunlit": 100.0 * sunlit.mean(),
        "pct_dte": 100.0 * dte.mean(),
        "pct_both": 100.0 * both.mean(),
        "longest_dark_h": longest_run_hours(~sunlit, dt_h),
        "longest_no_dte_h": longest_run_hours(~dte, dt_h),
        "mean_sun_frac": float(vis["sun_frac"].mean()),
        "pct_uncertain": 100.0 * vis["uncertain"].to_numpy(bool).mean() if "uncertain" in vis else 0.0,
        "pct_eclipsed": 100.0 * (vis["eclipse_frac"].to_numpy() > 0).mean() if "eclipse_frac" in vis else 0.0,
        "step_h": dt_h,
    }
    m["score"] = score_from(sunlit.mean(), dte.mean(), both.mean(), m["longest_dark_h"], m["longest_no_dte_h"],
                            window_h, weights)
    if include_energy:
        m.update(energy_summary(vis["p_solar_w"].to_numpy(), dt_h, power or PowerParams()))
    return m
