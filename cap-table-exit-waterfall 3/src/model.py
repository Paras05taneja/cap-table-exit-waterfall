"""
Startup cap table and exit waterfall model (seed SAFE -> Series A -> exit).

Simplifying assumptions (stated openly on purpose):
  * Post-money SAFE with a valuation cap, no discount. It converts at the lower of
    the cap price and the Series A price.
  * SAFE converts into preferred with a 1x liquidation preference equal to the
    amount invested.
  * Series A has a 1x NON-participating liquidation preference.
  * Preferred classes are pari passu (no seniority between SAFE and Series A).
  * Option pool is treated as fully granted and exercised (strike price ignored).
  * The Series A pre-money includes the SAFE conversion and the pool top-up
    (the usual "pre-money option pool shuffle").
"""
from dataclasses import dataclass
import pandas as pd


@dataclass
class Assumptions:
    founder_shares: float = 10_000_000
    existing_pool_shares: float = 1_000_000
    safe_investment: float = 1_000_000
    safe_post_money_cap: float = 8_000_000
    series_a_pre_money: float = 20_000_000
    series_a_raise: float = 5_000_000
    target_pool_post_a: float = 0.10  # pool as % of fully diluted shares after Series A


def build_cap_table(a: Assumptions) -> dict:
    """Solve share counts after the Series A. Circular (price depends on pool and SAFE
    shares, which depend on price), so solve by fixed-point iteration."""
    F, P0 = a.founder_shares, a.existing_pool_shares
    # Post-money SAFE at the cap: SAFE owns investment/cap of the capitalization
    # (founders + existing pool + SAFE), before the new pool top-up.
    safe_cap_shares = a.safe_investment * (F + P0) / (a.safe_post_money_cap - a.safe_investment)

    T, S = 0.0, safe_cap_shares
    for _ in range(1000):
        price = a.series_a_pre_money / (F + P0 + T + S)
        safe_round_shares = a.safe_investment / price
        S_new = max(safe_cap_shares, safe_round_shares)  # lower price -> more shares
        A = a.series_a_raise / price
        pool_total = a.target_pool_post_a * (F + S_new + A) / (1 - a.target_pool_post_a)
        T_new = max(0.0, pool_total - P0)
        if abs(T_new - T) < 1e-9 and abs(S_new - S) < 1e-9:
            T, S = T_new, S_new
            break
        T, S = T_new, S_new

    price = a.series_a_pre_money / (F + P0 + T + S)
    A = a.series_a_raise / price
    shares = {
        "Founders": F,
        "Option pool": P0 + T,
        "SAFE investors": S,
        "Series A investors": A,
    }
    return {"shares": shares, "series_a_price": price, "safe_price": a.safe_investment / S}


def ownership_table(a: Assumptions) -> pd.DataFrame:
    """Ownership at three points in time: founding, after SAFE conversion, after Series A."""
    cap = build_cap_table(a)
    s = cap["shares"]
    founding = {"Founders": a.founder_shares, "Option pool": a.existing_pool_shares,
                "SAFE investors": 0.0, "Series A investors": 0.0}
    safe_cap_shares = a.safe_investment * (a.founder_shares + a.existing_pool_shares) / (
        a.safe_post_money_cap - a.safe_investment)
    after_safe = {"Founders": a.founder_shares, "Option pool": a.existing_pool_shares,
                  "SAFE investors": safe_cap_shares, "Series A investors": 0.0}
    rows = {}
    for label, d in [("Founding", founding), ("After SAFE (at cap)", after_safe),
                     ("After Series A", s)]:
        tot = sum(d.values())
        rows[label] = {k: v / tot for k, v in d.items()}
    return pd.DataFrame(rows).T


def _payout(exit_value, shares, prefs, converts):
    """Pari passu waterfall. `converts` = set of preferred classes that convert to common."""
    out = {k: 0.0 for k in shares}
    non_conv = {k: v for k, v in prefs.items() if k not in converts}
    L = sum(non_conv.values())
    if exit_value <= L:
        for k, v in non_conv.items():
            out[k] = exit_value * v / L if L else 0.0
        return out
    for k, v in non_conv.items():
        out[k] = v
    remaining = exit_value - L
    participants = [k for k in shares if k not in non_conv]
    total_sh = sum(shares[k] for k in participants)
    for k in participants:
        out[k] = remaining * shares[k] / total_sh
    return out


def waterfall(exit_value: float, a: Assumptions) -> dict:
    """Exit proceeds by holder, with each preferred class choosing the better of
    (take 1x preference) or (convert to common)."""
    shares = build_cap_table(a)["shares"]
    prefs = {"SAFE investors": a.safe_investment, "Series A investors": a.series_a_raise}
    converts = set()
    for _ in range(10):  # iterate until no class wants to switch
        changed = False
        for k in prefs:
            with_k = _payout(exit_value, shares, prefs, converts | {k})[k]
            without_k = _payout(exit_value, shares, prefs, converts - {k})[k]
            want = with_k > without_k
            if want and k not in converts:
                converts.add(k); changed = True
            elif not want and k in converts:
                converts.discard(k); changed = True
        if not changed:
            break
    return _payout(exit_value, shares, prefs, converts)


def exit_scenarios(a: Assumptions, exit_values=None) -> pd.DataFrame:
    if exit_values is None:
        exit_values = [1, 2, 5, 10, 15, 20, 30, 50, 75, 100, 150, 200, 300, 500]
        exit_values = [v * 1_000_000 for v in exit_values]
    rows = []
    for ev in exit_values:
        p = waterfall(ev, a)
        rows.append({
            "exit_value": ev,
            **{f"{k} ($)": v for k, v in p.items()},
            **{f"{k} (%)": v / ev for k, v in p.items()},
            "SAFE MOIC": p["SAFE investors"] / a.safe_investment,
            "Series A MOIC": p["Series A investors"] / a.series_a_raise,
        })
    return pd.DataFrame(rows)
