"""
EV Charging Gap Analysis — Step 4: 10-mile access check

The first analysis only counted chargers inside each zip code.
This script checks whether those same zip codes are still underserved
when nearby chargers and nearby EV demand are included.
"""

import pandas as pd
import numpy as np

RADIUS_MILES = 10
MIN_EVS = 1000
EARTH_RADIUS_MILES = 3958.8


# 1. Load zip-level EV/charger data and zip center coordinates
zips = pd.read_csv("ev_data/processed/zip_summary.csv", dtype={"zip": str})

centers = pd.read_csv("ev_data/ev_raw/uszips.csv", dtype={"zip": str})
centers = centers[centers["state_id"] == "CA"]
centers = centers[["zip", "lat", "lng"]]
centers = centers.rename(columns={"lat": "latitude", "lng": "longitude"})

access = zips.merge(centers, on="zip", how="left")

missing = access["latitude"].isna()
print(f"Zips without a center point: {missing.sum()}")
access = access[~missing].reset_index(drop=True)


# 2. Load open charging stations and calculate ports per station
station_cols = [
    "ZIP", "Status Code", "EV Level2 EVSE Num",
    "EV DC Fast Count", "Latitude", "Longitude"
]

stations = pd.read_csv(
    "ev_data/ev_raw/altfuelstation.csv",
    usecols=station_cols,
    low_memory=False,
)

stations = stations[stations["Status Code"] == "E"]
stations = stations.dropna(subset=["Latitude", "Longitude"])

stations["ports"] = (
    stations["EV Level2 EVSE Num"].fillna(0)
    + stations["EV DC Fast Count"].fillna(0)
)

print(f"Open stations with coordinates: {len(stations):,}")


# 3. Distance function using the Haversine formula
# lat2/lon2 can be a full column, so one zip can be compared
# against all stations or all other zip centers at once.
def distance_miles(lat1, lon1, lat2, lon2):
    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    lat_diff = lat2 - lat1
    lon_diff = lon2 - lon1

    a = (
        np.sin(lat_diff / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin(lon_diff / 2) ** 2
    )

    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(a))


# 4. For each zip, count chargers and EVs within 10 miles
station_lats = stations["Latitude"].values
station_lons = stations["Longitude"].values
station_ports = stations["ports"].values

zip_lats = access["latitude"].values
zip_lons = access["longitude"].values
zip_evs = access["ev_2025"].values

ports_nearby = []
evs_nearby = []

for i in range(len(access)):
    station_distance = distance_miles(
        zip_lats[i], zip_lons[i], station_lats, station_lons
    )
    nearby_ports = station_ports[station_distance <= RADIUS_MILES].sum()
    ports_nearby.append(nearby_ports)

    zip_distance = distance_miles(
        zip_lats[i], zip_lons[i], zip_lats, zip_lons
    )
    nearby_evs = zip_evs[zip_distance <= RADIUS_MILES].sum()
    evs_nearby.append(nearby_evs)

access["ports_within_radius"] = ports_nearby
access["evs_within_radius"] = evs_nearby

# Large zip codes can have chargers far from their center.
# Do not count fewer chargers than the zip already contains.
access["ports_within_radius"] = access[
    ["ports_within_radius", "total_ports"]
].max(axis=1)


# 5. Compare zip-only access with 10-mile access
access["evs_per_port_in_zip"] = (
    access["ev_2025"] / access["total_ports"].replace(0, pd.NA)
)

access["evs_per_port_nearby"] = (
    access["evs_within_radius"]
    / access["ports_within_radius"].replace(0, pd.NA)
)

state_avg = zips["ev_2025"].sum() / zips["total_ports"].sum()
print(f"\nStatewide average: {state_avg:.1f} EVs per port")


# 6. Classify each zip
# Underserved = more than twice the statewide EVs-per-port average.
def classify(row):
    inside_bad = (
        pd.isna(row["evs_per_port_in_zip"])
        or row["evs_per_port_in_zip"] > 2 * state_avg
    )

    nearby_bad = (
        pd.isna(row["evs_per_port_nearby"])
        or row["evs_per_port_nearby"] > 2 * state_avg
    )

    if inside_bad and nearby_bad:
        return "Isolated - underserved by both measures"
    elif inside_bad:
        return "Locally sparse - chargers nearby"
    elif nearby_bad:
        return "Locally fine - crowded region"
    else:
        return "Well served"


access["access_class"] = access.apply(classify, axis=1)
access.loc[access["ev_2025"] < MIN_EVS, "access_class"] = "Fewer than 1,000 EVs"

large_zips = access[access["ev_2025"] >= MIN_EVS].copy()

print("\n=== Access results for zips with 1,000+ EVs ===")
print(large_zips["access_class"].value_counts())


# 7. Show the zip codes that remain underserved
isolated = large_zips[
    large_zips["access_class"] == "Isolated - underserved by both measures"
].copy()

isolated = isolated.sort_values("evs_per_port_nearby", ascending=False)

show_cols = [
    "zip", "city", "ev_2025", "total_ports",
    "ports_within_radius", "evs_per_port_in_zip", "evs_per_port_nearby"
]

print("\n=== Top 20 isolated zips ===")
print(isolated.head(20)[show_cols].round(1).to_string(index=False))


# 8. Re-check the original top 20 from Step 3
old_top20 = pd.read_csv(
    "ev_data/processed/underserved_top20.csv",
    dtype={"zip": str},
)

comparison = old_top20.merge(
    large_zips[[
        "zip", "city", "access_class",
        "ports_within_radius", "evs_per_port_nearby"
    ]],
    on="zip",
    how="left",
)

print("\n=== Original top 20, re-examined ===")
print(comparison[[
    "zip", "city", "evs_per_port",
    "ports_within_radius", "evs_per_port_nearby", "access_class"
]].round(1).to_string(index=False))


# 9. Save results
access.to_csv("ev_data/processed/zip_access_radius.csv", index=False)
print("\nSaved: ev_data/processed/zip_access_radius.csv")