"""
EV Charging Gap Analysis
Step 1: Load & EDA
- keeps only relevant columns, and prints basic exploration output
"""

import pandas as pd

# 1. DMV vehicle registrations (2021 and 2026 snapshots)

reg_2021 = pd.read_csv("ev_data/ev_raw/zip2021.csv")
reg_2025 = pd.read_csv("ev_data/ev_raw/zip2025.csv")

reg_2021 = reg_2021.rename(columns={"Zip Code": "zip"})
reg_2025 = reg_2025.rename(columns={"ZIP Code": "zip"})

print("=== DMV 2021 ===")
print(reg_2021.shape)
print(reg_2021["Fuel"].value_counts())

print("\n=== DMV 2026 snapshot ===")
print(reg_2025.shape)
print(reg_2025["Fuel"].value_counts())
print(reg_2025["Duty"].value_counts())


# 2. AFDC charging stations 
station_cols = [
    "ZIP", "City", "Status Code", "EV Level2 EVSE Num",
    "EV DC Fast Count", "EV Network", "Open Date",
    "Latitude", "Longitude",
]
stations = pd.read_csv(
    "ev_data/ev_raw/altfuelstation.csv",
    usecols=station_cols,
    low_memory=False,
).rename(columns={"ZIP": "zip"})

print("\n=== AFDC stations ===")
print(stations.shape)
print(stations["Status Code"].value_counts())  
#E=open, T=temp unavailable, P=planned

print("\nNulls per column:")
print(stations.isna().sum())

print("\nSample rows:")
print(stations.head())
