"""
EV Charging Gap Analysis — Step 3: Analysis
Answers the research question with three gap measures:
  A. EVs per public port (the current gap)      -> ranked top-20 table
  B. Zips with EVs but ZERO public ports        -> callout table
  C. Growth mismatch, 2021 -> 2026              -> forward-looking table
Then combines A and C into a "build here" shortlist.
"""

import pandas as pd

# Only rank zips with a meaningful EV base — tiny zips produce
# noisy ratios (200 EVs / 2 ports looks "worse" than it is).
MIN_EVS = 1000

df = pd.read_csv("ev_data/processed/zip_summary.csv", dtype={"zip": str})

# Statewide baseline
state_evs = df["ev_2025"].sum()
state_ports = df["total_ports"].sum()
baseline = state_evs / state_ports

print("=== Statewide baseline (ports inside zip boundaries) ===")
print(f"EVs (2026)               : {state_evs:,.0f}")
print(f"Public charging ports    : {state_ports:,.0f}")
print(f"EVs per port (statewide) : {baseline:.1f}")


# Metric A: EVs per port — the core gap measure.
# Keep zips with enough EVs and at least one port, compute the
# ratio, and rank the worst 20.
has_evs = df["ev_2025"] >= MIN_EVS
has_ports = df["total_ports"] > 0

ranked = df[has_evs & has_ports].copy()
ranked["evs_per_port"] = ranked["ev_2025"] / ranked["total_ports"]
ranked["vs_state_avg"] = ranked["evs_per_port"] / baseline
ranked = ranked.sort_values("evs_per_port", ascending=False)

top20 = ranked.head(20)
top20 = top20[["zip", "ev_2025", "total_ports", "evs_per_port", "vs_state_avg"]]

print(f"\n=== A. Top 20 zips by EVs per port INSIDE the zip (>= {MIN_EVS} EVs) ===")
print(top20.round(1).to_string(index=False))

# ----------------------------------------------------------------
# Metric B: zips with real EV demand and NO public ports at all.
# ----------------------------------------------------------------
zero = df[has_evs & (df["total_ports"] == 0)]
zero = zero.sort_values("ev_2025", ascending=False)
zero = zero[["zip", "ev_2025", "ev_2021"]]

print(f"\n=== B. Zips with >= {MIN_EVS} EVs and ZERO ports inside the zip ===")
print(f"Count: {len(zero)}")
print(zero.round(0).to_string(index=False))

# Metric C: growth mismatch — for every port added since 2021,
# how many EVs arrived? A zip that added 0 ports has no ratio
# (dividing by 0 is undefined), so it becomes NA and is counted
# separately below.
grow = df[has_evs].copy()
grow["evs_added"] = grow["ev_2025"] - grow["ev_2021"]
grow["ports_added"] = grow["total_ports"] - grow["total_ports_2021"]
grow["new_evs_per_new_port"] = grow["evs_added"] / grow["ports_added"].replace(0, pd.NA)
grow = grow.sort_values("new_evs_per_new_port", ascending=False)

mismatch = grow.head(20)
mismatch = mismatch[["zip", "evs_added", "ports_added", "new_evs_per_new_port"]]

print("\n=== C. Top 20 growth-mismatch zips (EVs added per port added) ===")
print(mismatch.round(1).to_string(index=False))

added_evs_no_ports = grow[(grow["ports_added"] == 0) & (grow["evs_added"] > 0)]
print(f"\nZips that added EVs but ZERO new ports since 2021: {len(added_evs_no_ports)}")

# The shortlist: zips in the worst 50 on Metric A AND the worst 50
# on Metric C.
worst_current = ranked.head(50)["zip"]
worst_growth = grow.head(50)["zip"]
shortlist = worst_current[worst_current.isin(worst_growth)]
shortlist = sorted(shortlist)

print(f"\n=== Provisional shortlist, worst 50 on BOTH metrics: {len(shortlist)} zips ===")
print("(re-tested against 10-mile access in 04_radius_access.py)")
print(", ".join(shortlist))

# Saving the tables for the visualization stage
top20.to_csv("ev_data/processed/underserved_top20.csv", index=False)
zero.to_csv("ev_data/processed/zero_port_zips.csv", index=False)
mismatch.to_csv("ev_data/processed/growth_mismatch_top20.csv", index=False)
print("\nSaved: underserved_top20.csv, zero_port_zips.csv, growth_mismatch_top20.csv")
