import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from model import Assumptions, build_cap_table, ownership_table, waterfall

a = Assumptions()

def test_ownership_sums_to_one():
    assert (abs(ownership_table(a).sum(axis=1) - 1) < 1e-9).all()

def test_series_a_owns_raise_over_post_money():
    own = ownership_table(a).loc["After Series A", "Series A investors"]
    assert abs(own - a.series_a_raise / (a.series_a_pre_money + a.series_a_raise)) < 1e-6

def test_pool_hits_target():
    own = ownership_table(a).loc["After Series A", "Option pool"]
    assert abs(own - a.target_pool_post_a) < 1e-6

def test_safe_owns_investment_over_cap_before_round():
    own = ownership_table(a).loc["After SAFE (at cap)", "SAFE investors"]
    assert abs(own - a.safe_investment / a.safe_post_money_cap) < 1e-9

def test_waterfall_conserves_value():
    for ev in [0.5e6, 3e6, 6e6, 12e6, 40e6, 250e6]:
        assert abs(sum(waterfall(ev, a).values()) - ev) < 1e-6

def test_low_exit_protects_investors_not_founders():
    p = waterfall(3e6, a)
    assert p["Founders"] == 0 and p["Series A investors"] > 0

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
