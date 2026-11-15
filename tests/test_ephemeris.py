"""Ephemeris checks (skipped automatically if kernels are not present)."""
import pandas as pd
from pathlib import Path

import numpy as np
import pytest

from engine.ephemeris import KERNEL_FILES, LunarSky, hourly_grid

KDIR = Path(__file__).resolve().parent.parent / "kernels"
pytestmark = pytest.mark.skipif(not all((KDIR / f).exists() for f in KERNEL_FILES.values()),
                                reason="kernels not downloaded")


@pytest.fixture(scope="module")
def sky():
    return LunarSky(KDIR)


def test_sun_elevation_bounds_near_pole(sky):
    lat = -86.0
    df = sky.compute(lat, 0.0, 0.0, hourly_grid("2027-01-01", "2028-01-01"))
    bound = (90 - abs(lat)) + 1.6 + 0.3     # colatitude + spin-axis tilt + margin
    assert df["sun_el_deg"].abs().max() < bound
    assert df["sun_el_deg"].max() > (90 - abs(lat))      # reaches above colatitude at some season


def test_sun_azimuth_completes_circle_each_lunation(sky):
    df = sky.compute(-89.5, 0.0, 0.0, hourly_grid("2027-03-01", "2027-03-31"))
    az = np.unwrap(np.radians(df["sun_az_deg"].to_numpy()))
    turns = abs(az[-1] - az[0]) / (2 * np.pi)
    assert 0.9 < turns < 1.1                              # ~one revolution per ~29.5 days


def test_earth_near_side_azimuth(sky):
    # from a south-polar site on the 0 deg meridian Earth sits roughly to local north (az ~ 0)
    df = sky.compute(-85.0, 0.0, 0.0, hourly_grid("2027-01-01", "2027-03-01"))
    az = ((df["earth_az_deg"] + 180) % 360) - 180
    assert az.abs().max() < 15


@pytest.mark.parametrize("day", ["2026-03-03", "2028-12-31"])   # total lunar eclipses
def test_total_lunar_eclipse_hides_sun(sky, day):
    from engine import visibility
    from engine.horizon import HorizonProfile
    df = sky.compute(0.0, 0.0, 0.0, hourly_grid(day, pd.Timestamp(day) + pd.Timedelta(days=1), step_h=1 / 6))
    flat = HorizonProfile(np.arange(0, 360, 0.5), np.full(720, -90.0), np.full(720, 150.0),
                          np.zeros(720, bool), 0.0, 2.0, 150.0)
    v = visibility.compute(df, flat, visibility.VisParams())
    assert v.eclipse_frac.max() == pytest.approx(1.0)
    assert v.sun_frac.min() == pytest.approx(0.0)


def test_no_eclipse_on_ordinary_day(sky):
    from engine import visibility
    df = sky.compute(0.0, 0.0, 0.0, hourly_grid("2027-05-01", "2027-05-02"))
    assert visibility.compute(df, None, visibility.VisParams()).eclipse_frac.max() == 0.0


def test_dsn_moon_coverage_is_nearly_continuous(sky):
    from engine.dsn import coverage, moon_elevations
    d = coverage(moon_elevations(sky, hourly_grid("2027-03-01", "2027-04-01")), 10.0)
    for c in ("dsn_goldstone_el", "dsn_madrid_el", "dsn_canberra_el"):
        assert d[c].between(-90, 90).all() and d[c].max() > 30      # Moon rises high at every complex
    assert d.dsn_any.mean() > 0.85                                  # three complexes ~120 deg apart
