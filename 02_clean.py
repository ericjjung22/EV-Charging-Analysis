"""
EV Charging Gap Analysis — Step 2: Clean & Aggregate (DuckDB + SQL)
Uses SQL to turn the three raw CSVs into one analysis-ready table:
  1. Stations: keep OPEN and PUBLIC ones, treat missing port counts as 0
  2. Registrations: keep light-duty EVs only (Battery Electric + Plug-in Hybrid)
  3. Both: keep only valid 5-digit California zips (90001-96162)
  4. Aggregate each source to one row per zip, then join them
"""

import os
import duckdb

os.makedirs("ev_data/processed", exist_ok=True)
con = duckdb.connect()

# 1. Charging stations: open + public only, missing ports -> 0
con.execute(r"""
    CREATE VIEW stations_clean AS
    SELECT
        CAST("ZIP" AS VARCHAR)             AS zip,
        COALESCE("EV Level2 EVSE Num", 0)  AS l2_ports,
        COALESCE("EV DC Fast Count", 0)    AS dcfc_ports,
        CAST("Open Date" AS DATE)          AS open_date,
        "City"                             AS city
    FROM read_csv_auto('ev_data/ev_raw/altfuelstation.csv', header = true)
    WHERE "Status Code" = 'E'
      AND regexp_matches(CAST("ZIP" AS VARCHAR), '^\d{5}$')
      AND CAST("ZIP" AS VARCHAR) BETWEEN '90001' AND '96162'
""")

# One row per zip: station count, most common city name, port totals,
# and the ports that already existed on 1/1/2021 (from Open Date).
con.execute("""
    CREATE VIEW stations_by_zip AS
    SELECT
        zip,
        COUNT(*)                    AS station_count,
        mode(city)                  AS city,
        SUM(l2_ports)               AS l2_ports,
        SUM(dcfc_ports)             AS dcfc_ports,
        SUM(l2_ports + dcfc_ports)  AS total_ports,
        SUM(CASE WHEN open_date < DATE '2021-01-01'
                 THEN l2_ports + dcfc_ports ELSE 0 END) AS total_ports_2021
    FROM stations_clean
    GROUP BY zip
""")

# 2. EV registrations, one view per snapshot year.
#    Same filter in both: light-duty Battery Electric + Plug-in Hybrid.
#    (Note: the zip column is named "Zip Code" in the 2021 file
#     but "ZIP Code" in the 2026 file.)
con.execute(r"""
    CREATE VIEW ev_2021 AS
    SELECT
        CAST("Zip Code" AS VARCHAR) AS zip,
        SUM("Vehicles")             AS ev_2021
    FROM read_csv_auto('ev_data/ev_raw/zip2021.csv', header = true)
    WHERE "Fuel" IN ('Battery Electric', 'Plug-in Hybrid')
      AND "Duty" = 'Light'
      AND regexp_matches(CAST("Zip Code" AS VARCHAR), '^\d{5}$')
      AND CAST("Zip Code" AS VARCHAR) BETWEEN '90001' AND '96162'
    GROUP BY zip
""")

con.execute(r"""
    CREATE VIEW ev_2025 AS
    SELECT
        CAST("ZIP Code" AS VARCHAR) AS zip,
        SUM("Vehicles")             AS ev_2025
    FROM read_csv_auto('ev_data/ev_raw/zip2025.csv', header = true)
    WHERE "Fuel" IN ('Battery Electric', 'Plug-in Hybrid')
      AND "Duty" = 'Light'
      AND regexp_matches(CAST("ZIP Code" AS VARCHAR), '^\d{5}$')
      AND CAST("ZIP Code" AS VARCHAR) BETWEEN '90001' AND '96162'
    GROUP BY zip
""")

# 3. Join all three to one row per zip.
#    FULL JOIN keeps a zip if it appears in ANY source, and
#    COALESCE(x, 0) turns the missing side into an honest zero.
con.execute("""
    CREATE TABLE zip_summary AS
    SELECT
        COALESCE(e26.zip, e21.zip, s.zip)  AS zip,
        COALESCE(e26.ev_2025, 0)           AS ev_2025,
        COALESCE(e21.ev_2021, 0)           AS ev_2021,
        COALESCE(s.station_count, 0)       AS station_count,
        COALESCE(s.l2_ports, 0)            AS l2_ports,
        COALESCE(s.dcfc_ports, 0)          AS dcfc_ports,
        COALESCE(s.total_ports, 0)         AS total_ports,
        COALESCE(s.total_ports_2021, 0)    AS total_ports_2021,
        s.city                             AS city
    FROM ev_2025 e26
    FULL JOIN ev_2021 e21       ON e26.zip = e21.zip
    FULL JOIN stations_by_zip s ON COALESCE(e26.zip, e21.zip) = s.zip
    ORDER BY zip
""")

con.execute("""
    COPY zip_summary TO 'ev_data/processed/zip_summary.csv'
    (HEADER, DELIMITER ',')
""")

# 4. Statewide cumulative ports at each Jan 1 (for the growth chart).
#    Caveat: closed stations are missing from AFDC, so early years
#    are slightly undercounted.
con.execute("""
    CREATE TABLE ports_by_year AS
    SELECT
        y.year,
        SUM(CASE WHEN s.open_date < make_date(y.year, 1, 1)
                 THEN s.l2_ports + s.dcfc_ports ELSE 0 END) AS total_ports
    FROM (SELECT unnest(range(2021, 2027)) AS year) y
    CROSS JOIN stations_clean s
    GROUP BY y.year
    ORDER BY y.year
""")

con.execute("""
    COPY ports_by_year TO 'ev_data/processed/ports_by_year.csv'
    (HEADER, DELIMITER ',')
""")

# 5. Cleaning log: print what each filter kept, so every exclusion
#    is visible. one(query) just runs a query and returns the
#    single number it produces.
def one(query):
    return con.execute(query).fetchone()[0]

print("=== Cleaning log ===")
print(f"Open stations in valid CA zips : {one('SELECT COUNT(*) FROM stations_clean'):>10,}")
print(f"Total public ports             : {one('SELECT SUM(total_ports) FROM stations_by_zip'):>10,}")
print(f"Light-duty EVs 2021            : {one('SELECT SUM(ev_2021) FROM ev_2021'):>10,}")
print(f"Light-duty EVs 2026            : {one('SELECT SUM(ev_2025) FROM ev_2025'):>10,}")
print(f"Zips in final summary          : {one('SELECT COUNT(*) FROM zip_summary'):>10,}")
print(f"  ...with EVs but ZERO ports   : {one('SELECT COUNT(*) FROM zip_summary WHERE ev_2025 > 0 AND total_ports = 0'):>10,}")

print("\nPreview:")
print(con.execute("SELECT * FROM zip_summary ORDER BY ev_2025 DESC LIMIT 5").df().to_string(index=False))
print("\nSaved: ev_data/processed/zip_summary.csv and ports_by_year.csv")
