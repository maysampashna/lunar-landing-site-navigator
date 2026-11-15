"""Loading precomputed data: sites.csv, hourly ephemeris (parquet) and terrain horizon profiles (npz)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .horizon import HorizonProfile

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_sites(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    return pd.read_csv(data_dir / "sites.csv")


def load_ephem(site_id: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    df = pd.read_parquet(data_dir / "ephem" / f"{site_id}.parquet")
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
    return df


def load_horizon(site_id: str, data_dir: Path = DATA_DIR) -> HorizonProfile | None:
    p = data_dir / "horizon" / f"{site_id}.npz"
    return HorizonProfile.load(p) if p.exists() else None


def is_synthetic(site_id: str, data_dir: Path = DATA_DIR) -> bool:
    return (data_dir / "horizon" / f"{site_id}.SYNTHETIC").exists()
