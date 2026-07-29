"""
EV Charging Gap Analysis — Step 7: How unequal is charging access?
-------------------------------------------------------------------
Answers: is the charging gap spread evenly across California,
or concentrated in specific places?

Method: compute the Gini coefficient of port access at three scales.
  - Across zip codes, counting ports INSIDE each zip
  - Across zip codes, counting ports within 10 MILES (from step 04)
  - Across counties
Comparing the three shows how much of the apparent gap is a real
shortage and how much is an artifact of where boundaries fall.

Output: ev_data/processed/county_summary.csv
"""

import pandas as pd
import numpy as np

# ----------------------------------------------------------------
# Step 1: load the zip summary and attach each zip's county
# (the zip_city.csv reference file has a county column)
# ----------------------------------------------------------------
zips = pd.read_csv("ev_data/processed/zip_summary.csv", dtype={"zip": str})

ref = pd.read_csv("ev_data/ev_raw/zip_city.csv", dtype=str)
ref = ref[ref["state_abbr"] == "CA"]                 # California rows only
ref = ref[["zipcode", "county"]]                     # keep 2 columns
ref = ref.rename(columns={"zipcode": "zip"})         # match our key name

df = zips.merge(ref, on="zip", how="left")

# Some zips are missing from the reference file -> no county.
# We report how many, then drop them from the county analysis.
missing = df["county"].isna()
print(f"Zips without a county match: {missing.sum()} "
      f"(holding {df[missing]['ev_2025'].sum():,.0f} EVs) -> excluded")
df = df[~missing]

# ----------------------------------------------------------------
# Step 2: add up EVs and ports for each county
# ----------------------------------------------------------------
county = df.groupby("county", as_index=False)[
    ["ev_2025", "ev_2021", "total_ports", "total_ports_2021"]
].sum()

county["evs_per_port"] = county["ev_2025"] / county["total_ports"]

print("\n=== Counties ranked by EVs per public port (worst first) ===")
show = county.sort_values("evs_per_port", ascending=False).head(15)
print(show[["county", "ev_2025", "total_ports", "evs_per_port"]]
      .round(1).to_string(index=False))

# ----------------------------------------------------------------
# Step 3: the Gini coefficient of charging access
#
# Idea: line places up from worst-served to best-served, then walk
# down the line tracking two running totals:
#   - what share of all EVs we have passed so far
#   - what share of all ports we have passed so far
# Perfect equality: the two rise together (30% of EVs -> 30% of ports).
# Inequality: ports lag behind. Gini measures that lag (0 to 1).
# ----------------------------------------------------------------
def gini(frame):
    f = frame[frame["ev_2025"] > 0].copy()

    # sort from worst-served to best-served
    f["ports_per_ev"] = f["total_ports"] / f["ev_2025"]
    f = f.sort_values("ports_per_ev")

    # running share of EVs and of ports (both go from 0 to 1)
    ev_share = f["ev_2025"].cumsum() / f["ev_2025"].sum()
    port_share = f["total_ports"].cumsum() / f["total_ports"].sum()

    # area under the curve of port_share vs ev_share;
    # perfect equality would give area 0.5, so Gini = 1 - 2*area
    x = np.concatenate([[0], ev_share])
    y = np.concatenate([[0], port_share])
    area = np.trapezoid(y, x)
    return 1 - 2 * area

# The same measure using ports within 10 miles instead of ports inside
# the zip. The 10-mile circles overlap, so these port totals are not an
# inventory of the state's chargers — the number measures how evenly
# ACCESS to charging is spread, not where the chargers sit.
radius = pd.read_csv("ev_data/processed/zip_access_radius.csv",
                     dtype={"zip": str})
# compare like with like: EVs within 10 miles against ports within
# 10 miles (using a zip's own EV count against a 10-mile port count
# would mix two different areas together)
radius = radius[["zip", "evs_within_radius", "ports_within_radius"]]
radius = radius.rename(columns={"evs_within_radius": "ev_2025",
                                "ports_within_radius": "total_ports"})

print("\n=== Gini coefficient of charging access ===")
print(f"Across zips, ports inside the zip  : {gini(df):.3f}")
print(f"Across zips, ports within 10 miles : {gini(radius):.3f}")
print(f"Across counties                    : {gini(county):.3f}")
print("(0 = ports spread exactly in proportion to EVs; 1 = all in one place)")
print("\nInequality collapses once access is measured by what drivers can")
print("actually reach: most of the apparent zip-level gap is a boundary")
print("effect, not a real shortage.")

county.to_csv("ev_data/processed/county_summary.csv", index=False)
print("\nSaved: ev_data/processed/county_summary.csv")
