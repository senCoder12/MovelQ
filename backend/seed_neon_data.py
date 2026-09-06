"""Seed Neon PostgreSQL database with the complete hackathon mobility dataset."""

import asyncio
import os
import uuid
from datetime import date, datetime, timedelta
import asyncpg
from dotenv import load_dotenv

load_dotenv("backend/.env")
raw_url = os.environ.get("NEON_DATABASE_URL", "")
url = raw_url.split("?")[0]

async def seed():
    print(f"Connecting to Neon DB: {url[:35]}...")
    conn = await asyncpg.connect(url, ssl="require")
    print("Connected successfully!")

    async with conn.transaction():
        # 1. Dimensions
        print("Seeding dimensions...")
        
        # Business Units
        bus = [
            (1, "catalyst-Slc"),
            (2, "catalyst-Sea"),
            (3, "orbit-Sac"),
            (4, "pinnacle-Aus"),
            (5, "vanta-Slc"),
        ]
        await conn.executemany("""
            INSERT INTO core.dim_business_unit (business_unit_key, business_unit_name)
            OVERRIDING SYSTEM VALUE
            VALUES ($1, $2)
            ON CONFLICT (business_unit_key) DO UPDATE 
            SET business_unit_name = EXCLUDED.business_unit_name;
        """, bus)

        # Offices
        offices = [
            (1, "Oakmont", 1),
            (2, "Barton", 1),
            (3, "Apex", 2),
            (4, "Plaza", 3),
        ]
        await conn.executemany("""
            INSERT INTO core.dim_office (office_key, office_name, business_unit_key)
            OVERRIDING SYSTEM VALUE
            VALUES ($1, $2, $3)
            ON CONFLICT (office_key) DO UPDATE 
            SET office_name = EXCLUDED.office_name, business_unit_key = EXCLUDED.business_unit_key;
        """, offices)

        # Vendors
        vendors = [
            (1, "Vendor Dispatch Desk"),
            (2, "Catalyst South Fleet"),
            (3, "Metro Mobility"),
            (4, "Apex Logistics"),
        ]
        await conn.executemany("""
            INSERT INTO core.dim_vendor (vendor_key, vendor_name)
            OVERRIDING SYSTEM VALUE
            VALUES ($1, $2)
            ON CONFLICT (vendor_key) DO UPDATE SET vendor_name = EXCLUDED.vendor_name;
        """, vendors)

        # Shifts
        shifts = [
            (1, "03:00", 3, "night"),
            (2, "07:00", 7, "morning"),
            (3, "11:00", 11, "morning"),
            (4, "15:00", 15, "afternoon"),
            (5, "19:00", 19, "evening"),
            (6, "23:00", 23, "night"),
        ]
        await conn.executemany("""
            INSERT INTO core.dim_shift (shift_key, shift_code, shift_hour, shift_band)
            OVERRIDING SYSTEM VALUE
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (shift_key) DO UPDATE 
            SET shift_code = EXCLUDED.shift_code, shift_hour = EXCLUDED.shift_hour, shift_band = EXCLUDED.shift_band;
        """, shifts)

        # Vehicles
        vehicles = [
            (1, "CAB-0101", 4, "Electric"),
            (2, "CAB-0102", 6, "Diesel"),
            (3, "CAB-0103", 6, "Diesel"),
            (4, "CAB-0104", 4, "Electric"),
            (5, "CAB-0105", 7, "Diesel"),
            (6, "CAB-0106", 6, "Petrol"),
            (7, "CAB-0107", 4, "Electric"),
            (8, "CAB-0108", 4, "Electric"),
        ]
        await conn.executemany("""
            INSERT INTO core.dim_vehicle (vehicle_key, registration, capacity, fuel_type)
            OVERRIDING SYSTEM VALUE
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (vehicle_key) DO UPDATE SET registration = EXCLUDED.registration;
        """, vehicles)

        # Contracts
        contracts = [
            (1, "CONT-01", "Standard-Night"),
            (2, "CONT-02", "Standard-Day"),
        ]
        await conn.executemany("""
            INSERT INTO core.dim_contract (contract_key, contract_code, slab_name)
            OVERRIDING SYSTEM VALUE
            VALUES ($1, $2, $3)
            ON CONFLICT (contract_key) DO UPDATE SET contract_code = EXCLUDED.contract_code;
        """, contracts)

        # Employees
        print("Seeding employees (150 riders)...")
        employees = [
            (1000 + i, "F" if i % 2 == 0 else "M", "Analyst" if i % 3 == 0 else "Associate")
            for i in range(150)
        ]
        await conn.executemany("""
            INSERT INTO core.dim_employee (stwid, gender, emp_role)
            VALUES ($1, $2, $3)
            ON CONFLICT (stwid) DO NOTHING;
        """, employees)

        # 2. Fact Trips
        print("Seeding trips (July 15, 2026 + historical baseline July 1-14)...")
        trips = []
        legs = []
        alerts = []
        billings = []

        target_date = date(2026, 7, 15)
        leg_seq = 1
        bill_seq = 1

        # Helper to create a trip
        def add_trip(t_id, t_date, bu_key, off_key, ven_key, sh_key, veh_key, direction, delay_min, planned_emp, actual_emp, noshow, reason):
            nonlocal leg_seq, bill_seq
            p_start = datetime(t_date.year, t_date.month, t_date.day, 1, 0) if sh_key == 1 else datetime(t_date.year, t_date.month, t_date.day, 5, 0)
            p_end = p_start + timedelta(minutes=60)
            a_start = p_start + timedelta(minutes=max(0, delay_min // 2))
            a_end = p_end + timedelta(minutes=delay_min)
            
            trips.append((
                t_id, t_date, bu_key, off_key, ven_key, sh_key, veh_key, veh_key,
                "CAB", direction, "HOME", "AUTO", reason, False, False, False,
                24.5, 26.8, p_start, p_end, a_start, a_end, delay_min,
                planned_emp, actual_emp, noshow, []
            ))

            # Billing
            cost = 450.0 + (delay_min * 5)
            billings.append((
                bill_seq, t_id, False, bu_key, off_key, ven_key, 1, t_date, t_date, 26.8, cost
            ))
            bill_seq += 1

            # Legs
            for emp_idx in range(planned_emp):
                stwid = 1000 + (t_id % 100) + emp_idx
                is_ns = (emp_idx < noshow)
                boarded = "Not Boarded" if is_ns else "Boarded"
                p_delay = delay_min if not is_ns else 0
                pl_pickup = p_start + timedelta(minutes=emp_idx * 5)
                act_pickup = a_start + timedelta(minutes=emp_idx * 5 + p_delay)
                legs.append((
                    leg_seq, t_id, False, stwid, t_date, bu_key, off_key, sh_key, "CAB",
                    "Planned", boarded, "NO_SHOW" if is_ns else None, is_ns,
                    pl_pickup, act_pickup, 4.2, 4.5, []
                ))
                leg_seq += 1

        # --- July 15 Trips ---
        # Trip 1097076: Reference incident (28 min delay, 8 employees, Vendor Dispatch Desk)
        add_trip(1097076, target_date, 1, 1, 1, 1, 1, "LOGIN", 28, 8, 8, 0, "TRAFFIC")
        
        # Trip 1097077: 22 min delay, 6 employees, 2 noshows
        add_trip(1097077, target_date, 1, 1, 1, 1, 2, "LOGIN", 22, 6, 4, 2, "DRIVER")
        
        # Trip 1097078: 18 min delay, 12 employees, 1 noshow
        add_trip(1097078, target_date, 1, 1, 2, 1, 3, "LOGIN", 18, 12, 11, 1, "TRAFFIC")

        # Trips 1097079, 1097080, 1097081 (On time trips to complete the 120 employee total: 91 on time)
        add_trip(1097079, target_date, 1, 1, 3, 1, 4, "LOGIN", 5, 30, 30, 0, "NODELAY")
        add_trip(1097080, target_date, 1, 1, 4, 1, 5, "LOGIN", 2, 32, 32, 0, "NODELAY")
        add_trip(1097081, target_date, 1, 1, 2, 1, 6, "LOGIN", 8, 32, 30, 2, "NODELAY")

        # Other shifts on July 15
        add_trip(1097082, target_date, 1, 1, 1, 2, 1, "LOGIN", 10, 25, 25, 0, "NODELAY")
        add_trip(1097083, target_date, 1, 1, 2, 3, 2, "LOGIN", 6, 20, 20, 0, "NODELAY")
        add_trip(1097084, target_date, 1, 1, 3, 4, 3, "LOGOUT", 12, 30, 29, 1, "TRAFFIC")
        add_trip(1097085, target_date, 1, 1, 4, 5, 4, "LOGOUT", 5, 25, 25, 0, "NODELAY")

        # Trip 1098442: Safety event trip
        add_trip(1098442, target_date, 1, 1, 2, 1, 7, "LOGIN", 14, 6, 6, 0, "NODELAY")

        # --- July 1 - 14 Historical Baseline Trips ---
        for day_offset in range(1, 15):
            h_date = target_date - timedelta(days=day_offset)
            base_trip_id = 1090000 + (day_offset * 10)
            add_trip(base_trip_id, h_date, 1, 1, 1, 1, 1, "LOGIN", 4, 20, 20, 0, "NODELAY")
            add_trip(base_trip_id + 1, h_date, 1, 1, 2, 1, 2, "LOGIN", 6, 30, 30, 0, "NODELAY")
            add_trip(base_trip_id + 2, h_date, 1, 1, 3, 1, 3, "LOGIN", 8, 35, 34, 1, "NODELAY")
            add_trip(base_trip_id + 3, h_date, 1, 1, 4, 1, 4, "LOGIN", 5, 35, 35, 0, "NODELAY")

        # --- Alerts ---
        print("Seeding alerts (including 11 DEVICE_NOT_REACHABLE for 1097076)...")
        base_alert_time = datetime(2026, 7, 15, 1, 10)
        for i in range(11):
            alerts.append((
                uuid.uuid4(), 1097076, False, None, 1, target_date,
                "DEVICE_NOT_REACHABLE", "VEHICLE", "Sev-2", "auto_fast",
                base_alert_time + timedelta(minutes=i * 3 + (i % 2)),
                base_alert_time + timedelta(minutes=i * 3 + 1),
                "CLOSED", "MOBILE"
            ))

        # VEHICLE_STOPPAGE alerts for 1097076
        alerts.append((
            uuid.uuid4(), 1097076, False, None, 1, target_date,
            "VEHICLE_STOPPAGE", "VEHICLE", "Sev-1", "triaged",
            datetime(2026, 7, 15, 1, 25), datetime(2026, 7, 15, 1, 45),
            "CLOSED", "GPS"
        ))

        # OVER_SPEEDING safety alert for 1098442
        alerts.append((
            uuid.uuid4(), 1098442, False, None, 1, target_date,
            "OVER_SPEEDING", "VEHICLE", "Sev-1", "triaged",
            datetime(2026, 7, 15, 1, 40), datetime(2026, 7, 15, 1, 42),
            "CLOSED", "TELEMATICS"
        ))

        # Clean old fact data first to allow clean re-seeding
        print("Cleaning previous fact records...")
        await conn.execute("DELETE FROM core.fact_trip_feedback;")
        await conn.execute("DELETE FROM core.fact_alert;")
        await conn.execute("DELETE FROM core.fact_trip_leg;")
        await conn.execute("DELETE FROM core.fact_trip_billing;")
        await conn.execute("DELETE FROM core.fact_trip;")

        # Insert Trips
        print(f"Inserting {len(trips)} trips...")
        await conn.executemany("""
            INSERT INTO core.fact_trip (
                trip_id, trip_date, business_unit_key, office_key, vendor_key, shift_key,
                planned_vehicle_key, actual_vehicle_key, product_type, trip_direction,
                trip_nodal, route_source, delay_reason, actual_escort, is_driver_nc,
                is_cab_nc, planned_km, traveled_km, planned_start_ts, planned_end_ts,
                actual_start_ts, actual_end_ts, delay_minutes, planned_employee_cnt,
                actual_employee_cnt, noshow_cnt, dq_flags
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                $21, $22, $23, $24, $25, $26, $27
            ) ON CONFLICT (trip_id) DO NOTHING;
        """, trips)

        # Insert Legs
        print(f"Inserting {len(legs)} trip legs...")
        await conn.executemany("""
            INSERT INTO core.fact_trip_leg (
                leg_key, trip_id, trip_is_orphan, stwid, trip_date, business_unit_key, office_key,
                shift_key, product_type, signintype, boarding_status, not_boarding_reason,
                is_no_show, planned_pickup_ts, actual_pickup_ts, planned_km, traveled_km,
                dq_flags
            ) OVERRIDING SYSTEM VALUE
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18
            ) ON CONFLICT (leg_key) DO NOTHING;
        """, legs)

        # Insert Alerts
        print(f"Inserting {len(alerts)} alerts...")
        await conn.executemany("""
            INSERT INTO core.fact_alert (
                event_id, trip_id, trip_is_orphan, stwid, business_unit_key, alert_date,
                event_type, alert_scope, severity_raw, resolution_path,
                start_ts, acknowledge_ts, state_text, source
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
            ) ON CONFLICT (event_id) DO NOTHING;
        """, alerts)

        # Insert Billing
        print(f"Inserting {len(billings)} billing lines...")
        await conn.executemany("""
            INSERT INTO core.fact_trip_billing (
                bill_line_key, trip_id, trip_is_orphan, business_unit_key, office_key, vendor_key,
                contract_key, cycle_start, cycle_end, billed_km, trip_cost
            ) OVERRIDING SYSTEM VALUE
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
            ) ON CONFLICT (bill_line_key) DO NOTHING;
        """, billings)

    # 3. Refresh Materialized Views if any
    print("Refreshing materialized views...")
    try:
        await conn.execute("REFRESH MATERIALIZED VIEW analytics.mv_daily_alert_metrics;")
    except Exception as e:
        print("Note on alert view refresh:", e)
    try:
        await conn.execute("REFRESH MATERIALIZED VIEW analytics.mv_daily_trip_metrics;")
    except Exception as e:
        print("Note on trip view refresh:", e)

    # Verification counts
    trip_cnt = await conn.fetchval("SELECT COUNT(*) FROM analytics.v_trip;")
    leg_cnt = await conn.fetchval("SELECT COUNT(*) FROM analytics.v_leg;")
    alert_cnt = await conn.fetchval("SELECT COUNT(*) FROM analytics.v_alert;")
    bill_cnt = await conn.fetchval("SELECT COUNT(*) FROM analytics.v_billing;")

    print("\n--- NEON DATABASE SEEDING COMPLETED ---")
    print(f"analytics.v_trip:    {trip_cnt} rows")
    print(f"analytics.v_leg:     {leg_cnt} rows")
    print(f"analytics.v_alert:   {alert_cnt} rows")
    print(f"analytics.v_billing: {bill_cnt} rows")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(seed())
