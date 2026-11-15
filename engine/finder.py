"""Landing-window finder and surface-start-time sensitivity for one or more sites.

Sensitivity ASSUMPTION: a schedule slip shifts surface arrival by exactly +24 h / +48 h.
This is a sensitivity analysis, not a trajectory model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import ScoreWeights, longest_run_hours, score_from, summarize
from .power import PowerParams


UNCERTAIN_LIMIT_PCT = 5.0   # sites with more uncertain time than this are excluded from confident ranking


class DateRangeError(ValueError):
    pass


def _times(vis: pd.DataFrame) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(vis["time_utc"])


def dt_hours(vis: pd.DataFrame) -> float:
    t = _times(vis)
    return (t[1] - t[0]).total_seconds() / 3600.0


def valid_start_range(vis: pd.DataFrame, duration_h: float, max_shift_h: float = 48.0):
    """Earliest and latest allowed surface start so window + max shift stays inside the data."""
    t = _times(vis)
    dt = dt_hours(vis)
    latest = t[-1] + pd.Timedelta(hours=dt) - pd.Timedelta(hours=duration_h + max_shift_h)
    return t[0], latest


def window(vis: pd.DataFrame, start, duration_h: float) -> pd.DataFrame:
    t = _times(vis)
    start = pd.Timestamp(start)
    if start.tz is None:
        start = start.tz_localize("UTC")
    dt = dt_hours(vis)
    i0 = int(t.searchsorted(start))
    n = int(round(duration_h / dt))
    if i0 + n > len(vis) or i0 >= len(t) or abs((t[i0] - start).total_seconds()) > dt * 3600 / 2 + 1:
        raise DateRangeError(f"Window {start} + {duration_h} h is outside the precomputed data "
                             f"({t[0]} .. {t[-1]})")
    return vis.iloc[i0:i0 + n]


def shift_compare(vis_by_site: dict[str, pd.DataFrame], start, duration_h: float = 144.0,
                  shifts_h=(0, 24, 48), weights: ScoreWeights | None = None,
                  power: PowerParams | None = None,
                  terrain_real: dict[str, bool] | None = None) -> tuple[pd.DataFrame, str | None]:
    """Metrics for each site x surface-start shift. Returns (table, best_site_id) where best is the
    highest WORST-CASE score across shifts ('best modeled location under the selected criteria'),
    chosen ONLY among 'confident' sites: REAL terrain (terrain_real[site] is True; a site missing from
    terrain_real, or terrain_real=None, counts as NOT real) AND uncertain time <= UNCERTAIN_LIMIT_PCT in
    every shift. best_site_id is None if no site is confident; the table still ranks all sites
    ('demonstration ranking') via worst_case_score."""
    rows = []
    start = pd.Timestamp(start)
    start = start.tz_localize("UTC") if start.tz is None else start
    for site_id, vis in vis_by_site.items():
        dt = dt_hours(vis)
        earliest, latest = valid_start_range(vis, duration_h, max(shifts_h))
        if start < earliest or start > latest:
            raise DateRangeError(f"Surface start must be between {earliest} and {latest} "
                                 f"(window {duration_h} h + max shift {max(shifts_h)} h)")
        for s in shifts_h:
            st = start + pd.Timedelta(hours=s)
            m = summarize(window(vis, st, duration_h), dt, weights, power)
            rows.append({"site_id": site_id, "shift_h": s, "start_utc": st, **m})
    df = pd.DataFrame(rows)
    worst = df.groupby("site_id")["score"].min().rename("worst_case_score")
    unc = df.groupby("site_id")["pct_uncertain"].max().rename("max_pct_uncertain")
    df = df.merge(worst, on="site_id").merge(unc, on="site_id")
    terrain_real = terrain_real or {}
    real = pd.Series({sid: bool(terrain_real.get(sid, False)) for sid in worst.index}, name="terrain_real")
    df = df.merge(real, left_on="site_id", right_index=True)
    df["confident"] = (df["max_pct_uncertain"] <= UNCERTAIN_LIMIT_PCT) & df["terrain_real"]
    conf = worst[(unc <= UNCERTAIN_LIMIT_PCT) & real]
    best = conf.idxmax() if len(conf) else None
    return df, best


def best_windows(vis: pd.DataFrame, range_start, range_end, duration_h: float = 144.0,
                 step_h: float = 6.0, n_best: int = 5, weights: ScoreWeights | None = None,
                 power: PowerParams | None = None, max_shift_h: float = 0.0) -> pd.DataFrame:
    """Slide a window across [range_start, range_end] and return the top-N start times by score.
    Fast pass uses visibility-only score; full metrics (incl. energy) computed for the top N."""
    weights = weights or ScoreWeights()
    t = _times(vis)
    dt = dt_hours(vis)
    n = int(round(duration_h / dt))
    step = max(1, int(round(step_h / dt)))
    rs, re = pd.Timestamp(range_start), pd.Timestamp(range_end)
    rs = rs.tz_localize("UTC") if rs.tz is None else rs
    re = re.tz_localize("UTC") if re.tz is None else re
    _, latest = valid_start_range(vis, duration_h, max_shift_h)
    re = min(re, latest)
    i0, i1 = int(t.searchsorted(rs)), int(t.searchsorted(re, side="right"))
    if i1 <= i0:
        raise DateRangeError("Empty search range after applying data boundaries")

    sunlit = vis["sunlit"].to_numpy()
    dte = vis["dte_visible"].to_numpy()
    both = sunlit & dte
    cs = lambda a: np.concatenate([[0], np.cumsum(a)])
    c_s, c_d, c_b = cs(sunlit), cs(dte), cs(both)
    starts = np.arange(i0, i1, step)
    scores = np.empty(len(starts))
    for k, i in enumerate(starts):
        j = i + n
        f_s = (c_s[j] - c_s[i]) / n
        f_d = (c_d[j] - c_d[i]) / n
        f_b = (c_b[j] - c_b[i]) / n
        scores[k] = score_from(f_s, f_d, f_b, longest_run_hours(~sunlit[i:j], dt),
                               longest_run_hours(~dte[i:j], dt), duration_h, weights)
    order = np.argsort(-scores, kind="stable")
    picked = []
    min_sep = n // 2   # avoid returning near-duplicate overlapping windows
    for k in order:
        if all(abs(starts[k] - starts[p]) >= min_sep for p in picked):
            picked.append(k)
        if len(picked) >= n_best:
            break
    rows = []
    for k in picked:
        i = starts[k]
        m = summarize(vis.iloc[i:i + n], dt, weights, power)
        rows.append({"start_utc": t[i], **m})
    return pd.DataFrame(rows)


def daily_heatmap(vis: pd.DataFrame, metric: str = "sunlit") -> pd.Series:
    """Daily fraction (0..1) of a boolean column, for calendar heatmaps."""
    s = pd.Series(vis[metric].to_numpy(dtype=float), index=_times(vis))
    return s.resample("1D").mean()
