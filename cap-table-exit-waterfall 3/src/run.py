"""Run the model: print the cap table, save scenario table and charts to outputs/."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from model import Assumptions, build_cap_table, ownership_table, exit_scenarios, waterfall

OUT = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(OUT, exist_ok=True)
a = Assumptions()

cap = build_cap_table(a)
print("Series A price per share: $%.4f | SAFE effective price: $%.4f" % (cap["series_a_price"], cap["safe_price"]))
own = ownership_table(a)
print("\nOwnership over time (%):\n", own.mul(100).round(2).to_string())
own.mul(100).round(2).to_csv(os.path.join(OUT, "ownership_over_time.csv"))

df = exit_scenarios(a)
df.round(4).to_csv(os.path.join(OUT, "exit_scenarios.csv"), index=False)
print("\nExit scenarios (selected columns):")
print(df[["exit_value", "Founders (%)", "Series A MOIC", "SAFE MOIC"]].round(3).to_string(index=False))

# Chart 1: ownership after each stage
ax = own.mul(100).plot(kind="bar", stacked=True, figsize=(8, 5), rot=0)
ax.set_ylabel("Ownership (%)"); ax.set_title("Dilution: who owns the company at each stage")
plt.tight_layout(); plt.savefig(os.path.join(OUT, "ownership_dilution.png"), dpi=150); plt.close()

# Chart 2: share of exit proceeds by holder
evs = np.linspace(1e6, 200e6, 200)
res = [waterfall(v, a) for v in evs]
fig, ax = plt.subplots(figsize=(9, 5))
for k in ["Founders", "Option pool", "SAFE investors", "Series A investors"]:
    ax.plot(evs / 1e6, [r[k] / v * 100 for r, v in zip(res, evs)], label=k)
ax.set_xlabel("Exit value ($M)"); ax.set_ylabel("Share of proceeds (%)")
ax.set_title("Exit waterfall: share of proceeds by holder (1x non-participating pref)")
ax.legend(); ax.grid(alpha=0.3)
plt.tight_layout(); plt.savefig(os.path.join(OUT, "waterfall_share_of_proceeds.png"), dpi=150)
print("\nSaved CSVs and charts to outputs/")
