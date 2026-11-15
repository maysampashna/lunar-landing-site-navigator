import numpy as np
import pandas as pd
import pytest

from engine.geometry import destination, disc_fraction_above, initial_bearing, R_MOON_M
from engine.horizon import RasterDEM, MultiDEM, compute_horizon, LOLA_SPS_PROJ
from engine.metrics import ScoreWeights, longest_run_hours, score_from, summarize
from engine.power import PowerParams, energy_summary, required_usable_energy_wh, simulate_battery, stored_energy_deltas_wh
from engine import finder


# ---------------------------------------------------------------- geometry
def test_disc_fraction_limits():
    assert disc_fraction_above(-1.0, 0.0, 0.25) == pytest.approx(0.0)
    assert disc_fraction_above(0.0, 0.0, 0.25) == pytest.approx(0.5)
    assert disc_fraction_above(1.0, 0.0, 0.25) == pytest.approx(1.0)
    xs = np.linspace(-0.3, 0.3, 61)
    f = disc_fraction_above(xs, 0.0, 0.25)
    assert np.all(np.diff(f) >= -1e-12)


def test_destination_bearings_south_polar_site():
    lat, lon = -85.0, 120.0
    la, lo = destination(lat, lon, 180.0, 10_000)        # toward the south pole
    assert la < lat and lo == pytest.approx(lon, abs=1e-6)
    la, lo = destination(lat, lon, 0.0, 10_000)          # local north, away from pole
    assert la > lat
    la, lo = destination(lat, lon, 90.0, 10_000)         # east -> longitude increases
    assert lo > lon
    la, lo = destination(lat, lon, 180.0, np.radians(5.0) * R_MOON_M)
    assert la == pytest.approx(-90.0, abs=1e-6)


# ---------------------------------------------------------------- synthetic DEM helpers
def _write_dem(path, height_fn, half_width_m=200_000, pixel_m=200.0, nodata_outside_m=None):
    """GeoTIFF in LOLA-style south polar stereographic (lunar sphere) with heights from height_fn(x, y)."""
    import rasterio
    from rasterio.transform import from_origin
    n = int(2 * half_width_m / pixel_m)
    xs = -half_width_m + pixel_m * (np.arange(n) + 0.5)
    ys = half_width_m - pixel_m * (np.arange(n) + 0.5)
    X, Y = np.meshgrid(xs, ys)
    Z = height_fn(X, Y).astype("float32")
    if nodata_outside_m is not None:
        Z[np.hypot(X, Y) > nodata_outside_m] = -9999.0
    with rasterio.open(path, "w", driver="GTiff", height=n, width=n, count=1, dtype="float32",
                       crs=LOLA_SPS_PROJ, transform=from_origin(-half_width_m, half_width_m, pixel_m, pixel_m),
                       nodata=-9999.0) as dst:
        dst.write(Z, 1)


def _to_xy(lat, lon):
    from pyproj import CRS, Transformer
    crs = CRS.from_proj4(LOLA_SPS_PROJ)
    return Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True).transform(lon, lat)


def _mountain(lat, lon, height=2000.0, sigma=1500.0):
    mx, my = _to_xy(lat, lon)
    return lambda X, Y: height * np.exp(-((X - mx) ** 2 + (Y - my) ** 2) / (2 * sigma ** 2))


@pytest.mark.parametrize("site_lon", [0.0, 120.0, -150.0, 45.0])
def test_horizon_orientation_mountain_at_pole(tmp_path, site_lon):
    """A mountain AT the south pole must appear at bearing 180 from every site longitude.
    This catches rays cast along DEM grid directions instead of geographic bearings."""
    p = tmp_path / "dem.tif"
    _write_dem(p, _mountain(-90.0, 0.0))
    hp = compute_horizon(-89.0, site_lon, RasterDEM(p), az_step_deg=1.0, max_dist_km=60, site_height_m=0.0)
    assert abs(((hp.az_deg[np.nanargmax(hp.horizon_el_deg)] - 180.0) + 180) % 360 - 180) <= 2.0


@pytest.mark.parametrize("site_lon,true_bearing", [(120.0, 0.0), (120.0, 90.0), (-60.0, 270.0), (10.0, 45.0)])
def test_horizon_orientation_mountain_at_bearing(tmp_path, site_lon, true_bearing):
    site_lat = -88.0
    m_lat, m_lon = destination(site_lat, site_lon, true_bearing, 20_000)
    # independent check of the target direction with the inverse formula
    assert initial_bearing(site_lat, site_lon, m_lat, m_lon) == pytest.approx(true_bearing % 360, abs=0.5)
    p = tmp_path / "dem.tif"
    _write_dem(p, _mountain(float(m_lat), float(m_lon)))
    hp = compute_horizon(site_lat, site_lon, RasterDEM(p), az_step_deg=0.5, max_dist_km=60, site_height_m=0.0)
    got = hp.az_deg[np.nanargmax(hp.horizon_el_deg)]
    assert abs(((got - true_bearing) + 180) % 360 - 180) <= 1.5


def test_horizon_elevation_and_curvature(tmp_path):
    site_lat, site_lon = -88.0, 30.0
    m_lat, m_lon = destination(site_lat, site_lon, 200.0, 40_000)
    p = tmp_path / "dem.tif"
    _write_dem(p, _mountain(float(m_lat), float(m_lon), height=3000.0, sigma=2000.0), pixel_m=100.0)
    hp = compute_horizon(site_lat, site_lon, RasterDEM(p), az_step_deg=0.5, max_dist_km=80,
                         site_height_m=0.0, observer_height_m=0.0)
    expected = np.degrees(np.arctan(3000.0 / 40_000 - 40_000 / (2 * R_MOON_M)))
    assert hp.horizon_el_deg.max() == pytest.approx(expected, abs=0.15)
    # flat terrain direction: horizon slightly negative because of curvature
    flat = hp.at(20.0)
    assert -0.2 < flat <= 0.0


def test_missing_terrain_is_flagged_not_flat(tmp_path):
    p = tmp_path / "dem.tif"
    _write_dem(p, lambda X, Y: np.zeros_like(X), nodata_outside_m=60_000)   # coverage ends 60 km from pole
    hp = compute_horizon(-89.0, 0.0, RasterDEM(p), az_step_deg=5.0, max_dist_km=100, site_height_m=0.0)
    # pointing away from the pole the ray leaves the DEM after ~30 km
    i_north = int(np.argmin(np.abs(hp.az_deg - 0.0)))
    i_south = int(np.argmin(np.abs(hp.az_deg - 180.0)))
    assert hp.incomplete[i_north] and hp.coverage_km[i_north] < 35
    assert not hp.incomplete[i_south] or hp.coverage_km[i_south] > 85


def test_multidem_fallback(tmp_path):
    near, far = tmp_path / "near.tif", tmp_path / "far.tif"
    _write_dem(near, lambda X, Y: np.zeros_like(X), half_width_m=60_000, pixel_m=100.0, nodata_outside_m=40_000)
    _write_dem(far, lambda X, Y: np.full_like(X, 5.0), half_width_m=200_000, pixel_m=400.0)
    dem = MultiDEM([RasterDEM(near), RasterDEM(far)])
    hp = compute_horizon(-89.5, 0.0, dem, az_step_deg=10, max_dist_km=100, site_height_m=0.0)
    assert not hp.incomplete.any()


# ---------------------------------------------------------------- metrics / score
def test_longest_run():
    assert longest_run_hours([True, True, False, True, True, True], 1.0) == 3.0
    assert longest_run_hours([False] * 4, 2.0) == 0.0
    assert longest_run_hours([True] * 4, 0.5) == 2.0


def test_score_bounds_and_normalization():
    w = ScoreWeights()
    assert score_from(1, 1, 1, 0, 0, 144, w) == pytest.approx(100.0)
    assert score_from(0, 0, 0, 144, 144, 144, w) == pytest.approx(0.0)
    w2 = ScoreWeights(w_sun=0.7, w_dte=0.7, w_both=0.6)          # same ratios, doubled
    assert score_from(0.6, 0.5, 0.4, 20, 30, 144, w) == pytest.approx(score_from(0.6, 0.5, 0.4, 20, 30, 144, w2))
    assert score_from(1, 1, 1, 0, 0, 144, ScoreWeights(5, 5, 5)) == pytest.approx(100.0)   # no saturation trick


# ---------------------------------------------------------------- power / battery
def test_battery_hand_case():
    p = PowerParams(load_w=100.0, eta_charge=0.9, eta_discharge=0.9, depth_of_discharge=0.5)
    dE = stored_energy_deltas_wh([200.0, 0.0, 0.0, 200.0], 1.0, p)
    np.testing.assert_allclose(dE, [90.0, -111.111111, -111.111111, 90.0], rtol=1e-6)
    e_req = required_usable_energy_wh(dE)
    assert e_req == pytest.approx(222.2222, rel=1e-5)
    E, depleted = simulate_battery(dE, e_req)
    np.testing.assert_allclose(E, [222.2222, 222.2222, 111.1111, 0.0, 90.0], atol=1e-3)
    assert not depleted
    s = energy_summary([200.0, 0.0, 0.0, 200.0], 1.0, p)
    assert s["required_nameplate_kwh"] == pytest.approx(0.4444444, rel=1e-5)
    assert s["soc_end"] == pytest.approx(90.0 / 222.2222, rel=1e-4)
    assert not s["recovers"]


def test_battery_undersized_capacity_depletes():
    p = PowerParams(load_w=100.0, eta_charge=1.0, eta_discharge=1.0, depth_of_discharge=1.0,
                    nameplate_capacity_kwh=0.1)
    s = energy_summary([0.0, 0.0, 0.0], 1.0, p)
    assert s["depleted"]


# ---------------------------------------------------------------- finder
def _synthetic_vis(hours=24 * 60, dt=1.0):
    t = pd.date_range("2027-01-01", periods=hours, freq=f"{dt}h", tz="UTC")
    k = np.arange(hours)
    sunlit = (k // 24) % 10 < 7            # 7 days lit, 3 days dark
    dte = (k // 24) % 14 < 9
    return pd.DataFrame({"time_utc": t, "sunlit": sunlit, "dte_visible": dte, "both": sunlit & dte,
                         "sun_frac": sunlit.astype(float), "p_solar_w": sunlit * 3000.0,
                         "uncertain": False, "eclipse_frac": 0.0})


def test_best_windows_finds_fully_lit_window():
    vis = _synthetic_vis()
    res = finder.best_windows(vis, "2027-01-01", "2027-02-15", duration_h=72, step_h=24, n_best=3)
    assert res.iloc[0]["pct_sunlit"] == pytest.approx(100.0)
    assert len(res) == 3


def test_shift_compare_and_boundaries():
    vis = _synthetic_vis()
    df, best = finder.shift_compare({"A": vis, "B": vis.assign(sunlit=False, both=False, p_solar_w=0.0)},
                                    "2027-01-01", duration_h=144, terrain_real={"A": True, "B": True})
    assert set(df["shift_h"]) == {0, 24, 48} and best == "A"
    with pytest.raises(finder.DateRangeError):
        finder.shift_compare({"A": vis}, "2027-02-27", duration_h=144)     # window+48 h past data end


# ---------------------------------------------------------------- eclipses and terrain uncertainty
from engine.geometry import covered_fraction, max_far_terrain_angle_deg
from engine.horizon import HorizonProfile
from engine import visibility


def test_covered_fraction():
    assert covered_fraction(0.27, 0.95, 2.0) == pytest.approx(0.0)
    assert covered_fraction(0.27, 0.95, 0.1) == pytest.approx(1.0)
    f = covered_fraction(0.27, 0.95, 0.95)          # Sun centre on Earth's limb -> about half covered
    assert 0.4 < f < 0.6
    seps = np.linspace(0.5, 1.4, 50)
    assert np.all(np.diff(covered_fraction(0.27, 0.95, seps)) <= 1e-12)


def _ephem_row(sun_az, sun_el, earth_az=0.0, earth_el=5.0, n=1):
    return pd.DataFrame({"time_utc": pd.date_range("2027-01-01", periods=n, freq="h", tz="UTC"),
                         "sun_az_deg": sun_az, "sun_el_deg": sun_el, "sun_dist_au": 1.0,
                         "earth_az_deg": earth_az, "earth_el_deg": earth_el, "earth_dist_km": 384400.0})


def test_uncertainty_from_missing_terrain():
    az = np.arange(0, 360, 0.5)
    inc = (az > 80) & (az < 100)                      # rays toward east ran out of DEM at 30 km
    hp = HorizonProfile(az, np.zeros_like(az), np.where(inc, 30.0, 150.0), inc, 0.0, 2.0, 150.0)
    bound = max_far_terrain_angle_deg(30.0)
    assert 15 < bound < 25                            # 12 km relief at 30 km could subtend ~20 deg
    v = visibility.compute(_ephem_row(90.0, 1.0), hp, visibility.VisParams())
    assert bool(v.sun_uncertain.iloc[0])              # low Sun over missing terrain -> uncertain
    v = visibility.compute(_ephem_row(90.0, bound + 2), hp, visibility.VisParams())
    assert not bool(v.sun_uncertain.iloc[0])          # high enough that nothing unknown can block it
    v = visibility.compute(_ephem_row(200.0, 1.0), hp, visibility.VisParams())
    assert not bool(v.sun_uncertain.iloc[0])          # complete ray -> certain


def test_uncertain_site_excluded_from_confident_ranking():
    good = _synthetic_vis()
    bad = good.assign(uncertain=True)                 # identical numbers but terrain-uncertain
    df, best = finder.shift_compare({"bad": bad, "good": good}, "2027-01-01", duration_h=144,
                                    terrain_real={"bad": True, "good": True})
    assert best == "good"
    df, best = finder.shift_compare({"bad": bad}, "2027-01-01", duration_h=144)
    assert best is None



# ---------------------------------------------------------------- confidence must fail closed on bad terrain
def test_missing_horizon_never_confident():
    v = visibility.compute(_ephem_row([90.0] * 200, [3.0] * 200, n=200), None, visibility.VisParams())
    assert v.uncertain.all()
    vis = _synthetic_vis().assign(uncertain=True)
    df, best = finder.shift_compare({"X": vis}, "2027-01-01", duration_h=144, terrain_real={"X": True})
    assert best is None and not df.confident.any()


def test_nan_horizon_directions_are_uncertain():
    az = np.arange(0, 360, 0.5)
    hz = np.zeros_like(az); hz[(az > 80) & (az < 100)] = np.nan          # no samples at all toward east
    hp = HorizonProfile(az, hz, np.full_like(az, 150.0), np.isnan(hz), 0.0, 2.0, 150.0)
    v = visibility.compute(_ephem_row(90.0, 30.0), hp, visibility.VisParams())   # even a high Sun
    assert bool(v.sun_uncertain.iloc[0])
    assert np.isfinite(v.horizon_at_sun_deg.iloc[0])                    # plotted, not NaN
    v = visibility.compute(_ephem_row(200.0, 3.0), hp, visibility.VisParams())
    assert not bool(v.sun_uncertain.iloc[0])


def test_synthetic_or_unknown_terrain_never_confident():
    vis = _synthetic_vis()
    _, best = finder.shift_compare({"A": vis}, "2027-01-01", duration_h=144, terrain_real={"A": False})
    assert best is None
    _, best = finder.shift_compare({"A": vis}, "2027-01-01", duration_h=144)       # default: not real
    assert best is None


def test_zero_weights_detected():
    assert not ScoreWeights(0, 0, 0).is_valid()
    assert not ScoreWeights(-1, 1, 1).is_valid()
    assert ScoreWeights().is_valid()
    with pytest.raises(ValueError):
        ScoreWeights(0, 0, 0).normalized()
