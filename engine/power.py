"""Illustrative solar-power and battery-storage estimate (NOT a flight-qualified design).

P_solar(t) = A * eta * 1361 W/m^2 * (1 AU / r)^2 * sun_frac(t)
  (vertical, Sun-tracking array; at the pole the Sun is ~on the horizon so incidence ~ 0)
P_net = P_solar - P_load
Stored-energy change per step:
  dE = eta_c * P_net * dt   if P_net > 0  (charging)
  dE = P_net * dt / eta_d   if P_net <= 0 (discharging)
E_req (usable) = max drawdown of cumulative dE from its running peak
                 (= deficit of a battery that starts full and is clamped at full)
C_req (nameplate) = E_req / DoD
Capacity simulation: E(0)=C_usable, E(t+1)=min(C_usable, E(t)+dE); depleted if E < 0.
End-of-window check reported separately (state of charge at end, 'recovers' flag).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SOLAR_CONSTANT_W_M2 = 1361.0


@dataclass
class PowerParams:
    array_area_m2: float = 10.0
    efficiency: float = 0.30
    load_w: float = 1000.0
    eta_charge: float = 0.95
    eta_discharge: float = 0.95
    depth_of_discharge: float = 0.8
    nameplate_capacity_kwh: float | None = None  # None -> simulate with the required capacity


def solar_power_w(sun_frac, sun_dist_au, p: PowerParams):
    return p.array_area_m2 * p.efficiency * SOLAR_CONSTANT_W_M2 / np.asarray(sun_dist_au) ** 2 * np.asarray(sun_frac)


def stored_energy_deltas_wh(p_solar_w, dt_h: float, p: PowerParams):
    p_net = np.asarray(p_solar_w, float) - p.load_w
    return np.where(p_net > 0, p.eta_charge * p_net * dt_h, p_net * dt_h / p.eta_discharge)


def required_usable_energy_wh(dE_wh) -> float:
    cum = np.concatenate([[0.0], np.cumsum(dE_wh)])
    peak = np.maximum.accumulate(cum)
    return float(np.max(peak - cum))


def simulate_battery(dE_wh, usable_capacity_wh: float):
    """Returns (energy trace incl. start, depleted flag)."""
    E = np.empty(len(dE_wh) + 1)
    E[0] = usable_capacity_wh
    depleted = False
    for i, de in enumerate(dE_wh):
        e = min(usable_capacity_wh, E[i] + de)
        if e < -1e-9:
            depleted = True
        E[i + 1] = e
    return E, depleted


def energy_summary(p_solar_w, dt_h: float, p: PowerParams) -> dict:
    p_solar_w = np.asarray(p_solar_w, float)
    dE = stored_energy_deltas_wh(p_solar_w, dt_h, p)
    e_req = required_usable_energy_wh(dE)
    c_req_nameplate = e_req / p.depth_of_discharge
    if p.nameplate_capacity_kwh is not None:
        usable = p.nameplate_capacity_kwh * 1000.0 * p.depth_of_discharge
    else:
        usable = e_req
    E, depleted = simulate_battery(dE, usable)
    soc_end = 1.0 if usable <= 0 else float(E[-1] / usable)
    return {
        "mean_solar_w": float(p_solar_w.mean()) if len(p_solar_w) else 0.0,
        "solar_energy_kwh": float(p_solar_w.sum() * dt_h / 1000.0),
        "load_energy_kwh": float(p.load_w * len(p_solar_w) * dt_h / 1000.0),
        "required_usable_kwh": e_req / 1000.0,
        "required_nameplate_kwh": c_req_nameplate / 1000.0,
        "simulated_usable_kwh": usable / 1000.0,
        "depleted": bool(depleted),
        "soc_end": soc_end,
        "recovers": bool(soc_end >= 1.0 - 1e-6),
    }
