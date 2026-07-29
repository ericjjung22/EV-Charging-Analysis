"""
EV Charging Gap Analysis — Step 4: Visualizations
- Reads the processed tables and produces three headline figures:
"""

import os
import pandas as pd
import matplotlib.pyplot as plt

os.makedirs("figures", exist_ok=True)

summary = pd.read_csv("ev_data/processed/zip_summary.csv", dtype={"zip": str})
top20 = pd.read_csv("ev_data/processed/underserved_top20.csv", dtype={"zip": str})
zero = pd.read_csv("ev_data/processed/zero_port_zips.csv", dtype={"zip": str})

# Build "zip - City" labels for the bar charts.
# Primary source: the station city carried through zip_summary.
# Fallback (zips with no stations): a public zip->city reference file.
# Download it once with:
#   curl -L "https://raw.githubusercontent.com/scpike/us-state-county-zip/master/geo-data.csv" -o ev_data/ev_raw/zip_city.csv
ref = pd.read_csv("ev_data/ev_raw/zip_city.csv", dtype=str)
ref = ref[ref["state_abbr"] == "CA"]                # California rows only
ref = ref[["zipcode", "city"]]                      # keep 2 columns
ref["city"] = ref["city"].str.title()               # "san francisco" -> "San Francisco"
ref["city"] = ref["city"].replace(r"^Zcta \d+$", pd.NA, regex=True)  # placeholders -> blank
ref = ref.rename(columns={"zipcode": "zip", "city": "ref_city"})

# Combine the two sources: use the station city, fill blanks from the
# reference file.
cities = summary[["zip", "city"]].merge(ref, on="zip", how="outer")
cities["city"] = cities["city"].fillna(cities["ref_city"])
cities = cities[["zip", "city"]]

# Manual patches for zips missing from both sources
overrides = {"93619": "Clovis", "92841": "Garden Grove",
             "91390": "Santa Clarita", "94505": "Discovery Bay"}
for zip_code, city_name in overrides.items():
    cities.loc[cities["zip"] == zip_code, "city"] = city_name

# Attach a "zip - City" label to each table we plot
top20 = top20.merge(cities, on="zip", how="left")
top20["label"] = top20["zip"] + " - " + top20["city"].fillna("?")

zero = zero.merge(cities, on="zip", how="left")
zero["label"] = zero["zip"] + " - " + zero["city"].fillna("?")

STATE_AVG = summary["ev_2025"].sum() / summary["total_ports"].sum()

# FIGURE 1: Top 20 underserved zips (EVs per public port)
fig, ax = plt.subplots(figsize=(10, 7))
d = top20.sort_values("evs_per_port")  # worst ends up at the bottom
ax.barh(d["label"], d["evs_per_port"], color="#c0392b")
ax.axvline(STATE_AVG, color="black", linestyle="--", linewidth=1,
           label=f"State average ({STATE_AVG:.0f} EVs/port)")
ax.set_xlabel("EVs per charging port located inside the zip (2026)")
ax.set_ylabel("Zip code")
ax.set_title("First pass: 20 zips with the fewest chargers\nINSIDE their own boundary")
ax.legend()
fig.tight_layout()
fig.savefig("figures/top20_underserved.png", dpi=150)
plt.close(fig)

# ----------------------------------------------------------------
# FIGURE 2: Largest EV populations with ZERO public ports
# ----------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 7))
d = zero.head(15).sort_values("ev_2025")
ax.barh(d["label"], d["ev_2025"], color="#7f1d1d")
ax.set_xlabel("EVs (2026)")
ax.set_ylabel("Zip code")
ax.set_title("15 largest EV populations with ZERO charging ports\ninside the zip code")
fig.tight_layout()
fig.savefig("figures/zero_port_zips.png", dpi=150)
plt.close(fig)

# ----------------------------------------------------------------
# FIGURE 3: side-by-side growth — EVs (left) and ports (right).
# Each panel uses its own natural units; both y-axes start at 0.
# EVs have only two real snapshots, so that line is dashed.
# ----------------------------------------------------------------
ports_yr = pd.read_csv("ev_data/processed/ports_by_year.csv")
evs_21 = summary["ev_2021"].sum()
evs_25 = summary["ev_2025"].sum()
ports_first = ports_yr["total_ports"].iloc[0]
ports_last = ports_yr["total_ports"].iloc[-1]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))

# Left panel: EVs
ax1.plot([2021, 2026], [evs_21, evs_25], marker="o", linestyle="--",
         color="#c0392b")
ax1.annotate(f"{evs_21:,.0f}", (2021, evs_21), xytext=(8, -18),
             textcoords="offset points", color="#c0392b")
ax1.annotate(f"{evs_25:,.0f}", (2026, evs_25), xytext=(-62, 8),
             textcoords="offset points", color="#c0392b")
ax1.set_title("Change in number of EV vehicles")
ax1.set_ylabel("Vehicles")
ax1.set_ylim(0, evs_25 * 1.15)
ax1.set_xticks([2021, 2022, 2023, 2024, 2025, 2026])
ax1.grid(alpha=0.3)

# Right panel: ports
ax2.plot(ports_yr["year"], ports_yr["total_ports"], marker="o",
         color="#2c3e50")
ax2.annotate(f"{ports_first:,.0f}", (2021, ports_first), xytext=(8, -18),
             textcoords="offset points", color="#2c3e50")
ax2.annotate(f"{ports_last:,.0f}", (2026, ports_last), xytext=(-48, 8),
             textcoords="offset points", color="#2c3e50")
ax2.set_title("Change in number of charging points")
ax2.set_ylabel("Ports")
ax2.set_ylim(0, ports_last * 1.15)
ax2.set_xticks([2021, 2022, 2023, 2024, 2025, 2026])
ax2.grid(alpha=0.3)

fig.suptitle("EVs and public charging both roughly quadrupled in California, 2021-2026",
             y=1.02)
fig.tight_layout()
fig.savefig("figures/growth_comparison.png", dpi=150, bbox_inches="tight")
plt.close(fig)

# FIGURE 4: the correction — the same 20 zips, measured two ways.
# Left value: ports inside the zip. Right value: ports within 10 miles.
# A log scale is used because the two values differ by up to 70x.
# Needs 04_radius_access.py to have been run first.
radius = pd.read_csv("ev_data/processed/zip_access_radius.csv", dtype={"zip": str})

compare = top20.merge(
    radius[["zip", "evs_per_port_nearby", "access_class"]],
    on="zip", how="left")
compare = compare.dropna(subset=["evs_per_port_nearby"])
compare = compare.sort_values("evs_per_port")

fixed = (compare["access_class"] == "Locally sparse - chargers nearby").sum()

fig, ax = plt.subplots(figsize=(10, 7))
y = range(len(compare))
ax.barh([i + 0.2 for i in y], compare["evs_per_port"], height=0.4,
        color="#c0392b", label="Ports inside the zip only")
ax.barh([i - 0.2 for i in y], compare["evs_per_port_nearby"], height=0.4,
        color="#2c3e50", label="Ports within 10 miles")
ax.set_yticks(list(y), compare["label"])
ax.set_xscale("log")
ax.axvline(STATE_AVG, color="black", linestyle="--", linewidth=1,
           label=f"State average ({STATE_AVG:.0f} EVs/port)")
ax.set_xlabel("EVs per charging port (log scale)")
ax.set_title(f"Most 'underserved' zips have chargers just across the line:\n"
             f"{fixed} of the 20 are well served within a 10-mile radius")
ax.legend(loc="lower right")
fig.tight_layout()
fig.savefig("figures/boundary_vs_radius.png", dpi=150)
plt.close(fig)

print("Saved 4 figures to figures/")
print(f"EVs per port, 2021 : {evs_21 / ports_first:.1f}")
print(f"EVs per port, 2026 : {evs_25 / ports_last:.1f}")
