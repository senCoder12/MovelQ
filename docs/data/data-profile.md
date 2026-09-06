# Data Profile Report

## Datasets and Characteristics

### 1. `ride_data_trip`
- **Volume:** ~215,885 trips.
- **Coverage:** May-July in staging, July 2026 in core.
- **Characteristics:** Core operational facts about trips.

### 2. `emp_data`
- **Volume:** ~608,793 trip-employee legs.
- **Coverage:** May-July.
- **Characteristics:** Granular breakdown of who is on which trip.

### 3. `bill_data`
- **Volume:** ~613,783+ billing lines.
- **Coverage:** May-July.
- **Characteristics:** Financial implications of trips and shifts.

### 4. `alerts_data`
- **Volume:** ~51,699 alert events.
- **Characteristics:** Extremely noisy. High volume of orphan alerts (72%).

### 5. `trip_feedback`
- **Volume:** Low utility.
- **Characteristics:** >90% modal share, <1% response rate. Not reliable for primary signal detection.

## Tenants and Sites
- **Tenants (4):** Catalyst, Orbit, Pinnacle, Vanta
- **Sites (4):** Aus, Sac, Sea, Slc

## Key Data Issues Discovered
1. **Mangled Numbers:** Comma-mangled numbers in CSV inputs.
2. **Date Format Inconsistency:** Varying date string formats across sources.
3. **Severity Flag Issues:** `severity` column contains string values `'False'` or `'NA'`.
4. **Orphan Alerts:** 72% of alerts cannot be linked to a specific trip or shift directly.
5. **Delay Contradictions:** 54.5% of trips marked `NODELAY` have a computed delay of >10 minutes.
6. **Shift Cluster Anomaly:** Unusual concentration of data points at the `:16` minute mark for shifts.

## Data Schema Overview (Sample)
- **Columns:** All relevant IDs, timestamps, location coordinates, status flags.
- **Null Rates:** High in feedback and specific alert contexts.
- **Distributions:** Heavily skewed by standard shift start/end times.
