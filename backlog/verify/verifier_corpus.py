import csv, re, sys
from pathlib import Path

D, DT = r"^\d{4}-\d{2}-\d{2}$", r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$"
S = {
 "d1_crew_master": {"crew_id":"s","base":"s","crew_group":"s","position":"s","fleet":"s","fleet_family":"s","qual_valid_from":D,"qual_valid_to":D,"seniority_number":"i","employment_status":"s","hire_date":D,"termination_date":D},
 "d2_rosters": {"crew_id":"s","base":"s","fleet":"s","position":"s","block_type":"s","start_utc":DT,"end_utc":DT,"start_local":DT,"end_local":DT,"pairing_id":"s","reserve_call_type":"s"},
 "d3_pairings": {"pairing_id":"s","base":"s","fleet":"s","position_complement":"s","duty_periods":"i","credit_hours":"f","layover_stations":"s","start_date":D,"days":"i"},
 "d3_pairing_legs": {"pairing_id":"s","duty_period":"i","leg_seq":"i","flight_no":"s","origin":"s","destination":"s","report_local":DT,"dep_local":DT,"arr_local":DT,"release_local":DT,"block_hours":"f"},
 "d4_absences": {"absence_id":"s","crew_id":"s","notification_ts":DT,"absence_start":D,"absence_end":D,"duration_days":"i","absence_type":"s","affected_pairing_id":"s","base":"s","fleet":"s","position":"s"},
 "d5_reserve_callouts": {"callout_id":"s","crew_id":"s","call_ts":DT,"report_ts":DT,"assigned_pairing_id":"s","outcome":"s","base":"s","fleet":"s"},
 "d6_schedule_changes": {"change_id":"s","crew_id":"s","change_ts":DT,"old_block_type":"s","new_block_type":"s","new_pairing_id":"s","reason_code":"s","initiator":"s"},
 "d7_pay_register": {"crew_id":"s","pay_period":"s","pay_code":"s","amount_cad":"f","duty_date":D,"linked_pairing_id":"s"},
 "d8_flight_movements": {"flight_no":"s","date":D,"origin":"s","destination":"s","fleet":"s","sched_dep_local":DT,"sched_arr_local":DT,"actual_dep_local":DT,"actual_arr_local":DT,"delay_minutes":"i","iata_delay_code":"s","cancelled":"i","cancel_reason":"s"},
 "d9_station_days": {"station":"s","date":D,"disruption_class":"s","season":"s","intensity_multiplier":"f"},
 "d10_positioning_invoices": {"date":D,"station":"s","cost_type":"s","amount_cad":"f","crew_id":"s","pairing_id":"s"},
 "d11_training_sessions": {"crew_id":"s","session_type":"s","start_date":D,"end_date":D,"requalification_deadline":D,"reschedule_cost_cad_estimate":"f"},
}
BANNED = {"name","full_name","first_name","last_name","passenger_name","passenger","pax_name","email","phone","dob","date_of_birth","address","employee_number","ssn","sin"}
ids = {}
for name, schema in S.items():
    p = Path(f"{name}.csv")
    if not p.exists():
        print(f"{name}: MANQUANT"); continue
    err = []
    with p.open(encoding="utf-8-sig", newline="") as fh:
        r = csv.DictReader(fh); cols = set(r.fieldnames or [])
        if b := {c for c in cols if c.strip().lower() in BANNED}: err.append(f"colonnes interdites {sorted(b)}")
        if cols != set(schema): err.append(f"manquantes={sorted(set(schema)-cols)} en trop={sorted(cols-set(schema))}")
        n = zero = num_ids = 0
        for row in r:
            n += 1
            for c, k in schema.items():
                v = (row.get(c) or "").strip()
                if not v: continue
                bad = (k in (D, DT) and not re.match(k, v)) or (k == "i" and not re.match(r"^-?\d+$", v)) \
                      or (k == "f" and not re.match(r"^-?\d+(\.\d+)?$", v))
                if bad and len(err) < 8: err.append(f"ligne {n+1} {c}={v!r}")
            if "crew_id" in schema and re.match(r"^\d+$", row.get("crew_id") or ""): num_ids += 1
            if name == "d2_rosters" and row.get("start_utc") == row.get("end_utc"): zero += 1
        if num_ids: err.insert(0, f"{num_ids} crew_id numériques (matricules ?) – pseudonymiser")
        if zero: err.append(f"{zero} blocs D2 de durée 0")
    if name == "d2_rosters":
        with p.open(encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if not any(x["block_type"] == "RESERVE" for x in rows): err.append("aucun bloc RESERVE")
    print(f"{name}: {'OK' if not err else 'ERREURS'} ({n} lignes)")
    for e in err: print("   -", e)
