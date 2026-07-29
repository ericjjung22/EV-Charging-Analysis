"""
EV Charging Gap Analysis — Step 5: Tableau map export
------------------------------------------------------
Builds one Tableau-ready table (one row per zip) for the interactive
choropleth: ev_data/processed/tableau_map.csv

Tableau geocodes US zip codes natively, so no boundary file is needed.

Two colour fields are included:
  service_category — based on ports INSIDE the zip (first pass)
  access_class     — based on ports within 10 miles (corrected view)
"""

import pandas as pd

MIN_EVS = 1000  # same threshold as 03_analysis.py

df = pd.read_csv("ev_data/processed/zip_summary.csv", dtype={"zip": str})

# 10-mile access columns from 04_radius_access.py
radius = pd.read_csv("ev_data/processed/zip_access_radius.csv", dtype={"zip": str})
radius = radius[["zip", "ports_within_radius", "evs_within_radius",
                 "evs_per_port_nearby", "access_class"]]
df = df.merge(radius, on="zip", how="left")

baseline = df["ev_2025"].sum() / df["total_ports"].sum()

# Keep the columns the map needs
out = df[["zip", "city", "ev_2025", "ev_2021", "station_count",
          "l2_ports", "dcfc_ports", "total_ports", "total_ports_2021",
          "ports_within_radius", "evs_within_radius",
          "evs_per_port_nearby", "access_class"]].copy()

# zips with no center point get no radius result
out["access_class"] = out["access_class"].fillna("No location data")

# Core gap metric. A zip with zero ports has no ratio (can't divide
# by 0), so it stays blank — Tableau shows blanks cleanly, and those
# zips get their own category below.
out["evs_per_port"] = out["ev_2025"] / out["total_ports"].replace(0, pd.NA)
out["vs_state_avg"] = out["evs_per_port"] / baseline

# Growth columns
out["evs_added"] = out["ev_2025"] - out["ev_2021"]
out["ports_added"] = out["total_ports"] - out["total_ports_2021"]

# A ready-made category for coloring the map
def category(row):
    if row["ev_2025"] < MIN_EVS:
        return "Fewer than 1,000 EVs"
    if row["total_ports"] == 0:
        return "1,000+ EVs, zero ports"
    if row["evs_per_port"] > 3 * baseline:
        return "Severely underserved (>3x state avg)"
    if row["evs_per_port"] > baseline:
        return "Below average"
    return "At or above average"

out["service_category"] = out.apply(category, axis=1)

out.to_csv("ev_data/processed/tableau_map.csv", index=False)

print(f"Rows exported           : {len(out):,}")
print(f"State average (EVs/port): {baseline:.1f}")
print("\nService category (ports inside the zip):")
print(out["service_category"].value_counts().to_string())
print("\nAccess class (ports within 10 miles):")
print(out["access_class"].value_counts().to_string())
print("\nSaved: ev_data/processed/tableau_map.csv")
