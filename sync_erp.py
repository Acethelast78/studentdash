#!/usr/bin/env python3
"""
XL ERP Timetable Dual-Section Sync Utility
Fetches complete Term 5 timetable data by authenticating both Section E and Section F students.
Combines genuine ERP sessions from both sections and exports to term5_timetable.csv (Google Sheets format).

Usage:
    python sync_erp.py
    python sync_erp.py --sec-e-email e@xlri.ac.in --sec-e-password pw_e --sec-f-email f@xlri.ac.in --sec-f-password pw_f
"""

import sys
import os
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
import json
import csv
import argparse
import getpass
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, date, timedelta

API_BASE_URL = "https://xlerp.xlri.ac.in/api/v1"
LOGIN_URL = f"{API_BASE_URL}/auth/login"
SCHEDULE_ENDPOINT = f"{API_BASE_URL}/schedule/my-schedule/student"

DEFAULT_START_DATE = "2026-09-11"
DEFAULT_END_DATE = "2026-12-31"

CSV_OUTPUT_NAME = "term5_timetable.csv"
JSON_OUTPUT_NAME = "term5_schedule.json"

TIME_SLOTS = [
    "8:00 AM",
    "08:30 To 10:00 AM",
    "10:20 To 11:50AM",
    "12:10 To 1:40 PM",
    "02:45 to 4:15 PM",
    "04:30 To 6:00 PM",
    "06:15 To 7:45 PM",
    "08:00 To 9:30PM"
]

def match_time_to_slot_idx(time_str):
    if not time_str:
        return 1
    parts = time_str.split(':')
    h = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    m = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    total_mins = h * 60 + m
    if total_mins < 495: return 0
    if total_mins < 560: return 1
    if total_mins < 675: return 2
    if total_mins < 800: return 3
    if total_mins < 935: return 4
    if total_mins < 1040: return 5
    if total_mins < 1145: return 6
    return 7

def get_password_input(prompt="Enter XL ERP Password: "):
    """Read password with visible * masking on Windows."""
    try:
        import msvcrt
        sys.stdout.write(prompt)
        sys.stdout.flush()
        pw = ""
        while True:
            ch = msvcrt.getch()
            if ch in (b'\r', b'\n'):
                sys.stdout.write('\n')
                sys.stdout.flush()
                break
            elif ch == b'\x08':  # Backspace
                if len(pw) > 0:
                    pw = pw[:-1]
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            elif ch == b'\x03':  # Ctrl+C
                raise KeyboardInterrupt
            else:
                try:
                    char = ch.decode('utf-8', errors='ignore')
                    if char:
                        pw += char
                        sys.stdout.write('*')
                        sys.stdout.flush()
                except Exception:
                    pass
        return pw.strip()
    except Exception:
        try:
            return getpass.getpass(prompt).strip()
        except Exception:
            return input(prompt).strip()

def login(email, password, label="User"):
    """Authenticate with XL ERP and return Bearer token."""
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        LOGIN_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            token = res_data.get("data", {}).get("token") or res_data.get("token") or res_data.get("accessToken")
            if not token and isinstance(res_data.get("data"), str):
                token = res_data["data"]
            if token:
                print(f"[OK] Successfully authenticated ({label}: {email}) with XL ERP.")
                return token
            else:
                print(f"[WARN] Login succeeded for {email} but token was not found in response.")
                return None
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"[ERROR] Login failed for ({label}: {email}) [HTTP {e.code}]: {err_msg}")
        return None
    except Exception as e:
        print(f"[ERROR] Connection error for {email}: {e}")
        return None

def fetch_schedule(token, label="User", start_date=DEFAULT_START_DATE, end_date=DEFAULT_END_DATE):
    """Fetch timetable schedule JSON for date range."""
    params = urllib.parse.urlencode({"startDate": start_date, "endDate": end_date})
    url = f"{SCHEDULE_ENDPOINT}?{params}"
    
    clean_token = token.replace("Bearer ", "").strip()
    headers = {
        "Authorization": f"Bearer {clean_token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    req = urllib.request.Request(url, headers=headers, method="GET")
    
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if res_data.get("success") or "data" in res_data:
                sessions = res_data.get("data", [])
                print(f"[OK] Fetched {len(sessions)} schedule sessions for {label}.")
                return sessions
            else:
                return []
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"[ERROR] Schedule fetch failed for {label} [HTTP {e.code}]: {err_msg}")
        return []
    except Exception as e:
        print(f"[ERROR] Connection error for {label}: {e}")
        return []

def deduplicate_sessions(sessions_list):
    """Deduplicate sessions from Section E and Section F fetches."""
    seen_keys = set()
    unique_sessions = []
    
    for s in sessions_list:
        if not s or not s.get("classDate") or s.get("isCancelled"):
            continue
        sid = s.get("sessionId")
        if sid:
            if sid in seen_keys:
                continue
            seen_keys.add(sid)
            unique_sessions.append(s)
            continue
            
        c_code = s.get("course", {}).get("courseCode", "") or s.get("courseOfferCode", "")
        sec = s.get("section", {}).get("sectionName", "")
        comp_key = f"{s.get('classDate')}_{s.get('startTime')}_{c_code}_{sec}"
        if comp_key in seen_keys:
            continue
        seen_keys.add(comp_key)
        unique_sessions.append(s)
        
    return unique_sessions

def convert_sessions_to_csv(sessions, out_csv_path=CSV_OUTPUT_NAME):
    """Convert genuine ERP schedule JSON to Google Sheets layout CSV."""
    course_metadata = {}
    for s in sessions:
        course = s.get('course', {})
        code = course.get('courseCode', '') or ''
        name = course.get('courseName', '') or code
        offer_code = s.get('courseOfferCode', '') or f"{code}BD25-5"
        faculty = s.get('faculty', {})
        faculty_name = f"{faculty.get('prefix', '')} {faculty.get('firstName', '')} {faculty.get('lastName', '')}".strip() if faculty else ''
        
        if offer_code and offer_code not in course_metadata:
            course_metadata[offer_code] = {
                'code': offer_code,
                'name': name,
                'faculty': faculty_name,
                'ta': ''
            }

    sessions_by_date = {}
    for s in sessions:
        if not s.get('classDate') or s.get('isCancelled'):
            continue
        c_date = s['classDate']
        d_parts = c_date.split('-')
        if len(d_parts) != 3:
            continue
        formatted_date = f"{d_parts[2]}-{d_parts[1]}-{d_parts[0]}"
        if formatted_date not in sessions_by_date:
            sessions_by_date[formatted_date] = []
        sessions_by_date[formatted_date].append(s)

    start_dt = date(2026, 9, 11)
    end_dt = date(2026, 12, 31)
    curr_dt = start_dt

    csv_rows = []
    csv_rows.append(["      TERM V", "", "", "", "", "", "Venue: Sec E MCR-07 , Sec F MCR-08 , Common MCR-07.", "", "", "", "", "", "", "", ""])
    csv_rows.append(["DAY", "Date/Time", "8:00 AM", "08:30 To 10:00 AM", "10:20 To 11:50AM", "12:10 To 1:40 PM", "02:45 to 4:15 PM", "04:30 To 6:00 PM", "06:15 To 7:45 PM", "08:00 To 9:30PM", "", "Course Code ", "Courses Name", "Faculty", "TA"])

    meta_list = list(course_metadata.values())
    meta_idx = 0

    while curr_dt <= end_dt:
        formatted_date = curr_dt.strftime("%d-%m-%Y")
        day_name = curr_dt.strftime("%A")
        day_sessions = sessions_by_date.get(formatted_date, [])
        
        slots_bucket = {i: [] for i in range(8)}
        for s in day_sessions:
            slot_idx = match_time_to_slot_idx(s.get('startTime', ''))
            course = s.get('course', {})
            code = course.get('courseCode', '') or ''
            sec_info = s.get('section', {}).get('sectionName', '') or ''
            if not sec_info and s.get('attendingSections'):
                sec_info = "/".join(x.get('sectionName', '') for x in s['attendingSections'])
            venue = s.get('venue', {}).get('code', '') or s.get('venue', {}).get('name', '') or ''
            
            slot_text = code
            if sec_info:
                slot_text += f" Sec {sec_info}"
            if venue:
                slot_text += f" ({venue})"
            slots_bucket[slot_idx].append(slot_text)
        
        max_lines = max([len(slots_bucket[i]) for i in range(8)] + [1])
        for line_idx in range(max_lines):
            row = ["", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]
            if line_idx == 0:
                row[0] = day_name
                row[1] = formatted_date
            
            for slot_i in range(8):
                if line_idx < len(slots_bucket[slot_i]):
                    row[2 + slot_i] = slots_bucket[slot_i][line_idx]
            
            if meta_idx < len(meta_list):
                m = meta_list[meta_idx]
                row[11] = m['code']
                row[12] = m['name']
                row[13] = m['faculty']
                row[14] = m['ta']
                meta_idx += 1
                
            csv_rows.append(row)
        curr_dt += timedelta(days=1)

    with open(out_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(csv_rows)
    print(f"[OK] Successfully exported {len(csv_rows)} rows to {out_csv_path}!")
    return True


def update_embedded_html(csv_content):
    """Update TERM5_DEFAULT_CSV constant in HTML files for offline file:/// support."""
    for fn in ["index.html", "xlri_enrollment_dashboard (2).html"]:
        if os.path.exists(fn):
            try:
                with open(fn, "r", encoding="utf-8") as f:
                    content = f.read()
                start_marker = "const TERM5_DEFAULT_CSV = "
                end_marker = ";\n\nlet currentSelectedTerm"
                start_idx = content.find(start_marker)
                end_idx = content.find(end_marker, start_idx)
                if start_idx != -1 and end_idx != -1:
                    new_content = content[:start_idx + len(start_marker)] + json.dumps(csv_content) + content[end_idx:]
                    with open(fn, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"[OK] Updated embedded offline CSV in {fn}")
            except Exception as e:
                print(f"[WARN] Could not update {fn}: {e}")

def main():
    parser = argparse.ArgumentParser(description="XL ERP Timetable Dual-Section Sync Utility")
    parser.add_argument("--sec-e-email", default=os.getenv("XL_ERP_SEC_E_EMAIL") or os.getenv("XL_ERP_EMAIL"), help="Section E Student Email")
    parser.add_argument("--sec-e-password", default=os.getenv("XL_ERP_SEC_E_PASSWORD") or os.getenv("XL_ERP_PASSWORD"), help="Section E Password")
    parser.add_argument("--sec-e-token", default=os.getenv("XL_ERP_SEC_E_TOKEN"), help="Section E Bearer Token")
    
    parser.add_argument("--sec-f-email", default=os.getenv("XL_ERP_SEC_F_EMAIL"), help="Section F Student Email")
    parser.add_argument("--sec-f-password", default=os.getenv("XL_ERP_SEC_F_PASSWORD"), help="Section F Password")
    parser.add_argument("--sec-f-token", default=os.getenv("XL_ERP_SEC_F_TOKEN"), help="Section F Bearer Token")
    
    parser.add_argument("--start", default=DEFAULT_START_DATE, help=f"Start Date (YYYY-MM-DD), default: {DEFAULT_START_DATE}")
    parser.add_argument("--end", default=DEFAULT_END_DATE, help=f"End Date (YYYY-MM-DD), default: {DEFAULT_END_DATE}")
    parser.add_argument("--csv", default=CSV_OUTPUT_NAME, help=f"Output CSV path, default: {CSV_OUTPUT_NAME}")
    
    args = parser.parse_args()
    
    all_sessions = []
    
    # ── 1. Authenticate Section E Student ──────────────────────────────────
    print("====================================================")
    print("  STEP 1: SECTION E STUDENT AUTHENTICATION")
    print("====================================================")
    token_e = args.sec_e_token
    if not token_e:
        email_e = args.sec_e_email or (input("Enter Section E Student Email: ").strip() if sys.stdin.isatty() else None)
        pw_e = args.sec_e_password or (get_password_input("Enter Section E Password: ") if sys.stdin.isatty() else None)
        if not email_e or not pw_e:
            print("[ERROR] Section E Email and Password are required.")
            sys.exit(1)
        token_e = login(email_e, pw_e, label="Section E")
        if not token_e:
            sys.exit(1)
            
    sessions_e = fetch_schedule(token_e, label="Section E", start_date=args.start, end_date=args.end)
    all_sessions.extend(sessions_e)
    
    # ── 2. Authenticate Section F Student ──────────────────────────────────
    print("\n====================================================")
    print("  STEP 2: SECTION F STUDENT AUTHENTICATION")
    print("====================================================")
    token_f = args.sec_f_token
    if not token_f:
        email_f = args.sec_f_email or (input("Enter Section F Student Email: ").strip() if sys.stdin.isatty() else None)
        pw_f = args.sec_f_password or (get_password_input("Enter Section F Password: ") if sys.stdin.isatty() else None)
        if not email_f or not pw_f:
            print("[ERROR] Section F Email and Password are required.")
            sys.exit(1)
        token_f = login(email_f, pw_f, label="Section F")
        if not token_f:
            sys.exit(1)
            
    sessions_f = fetch_schedule(token_f, label="Section F", start_date=args.start, end_date=args.end)
    all_sessions.extend(sessions_f)
    
    # ── 3. Deduplicate & Combine Full Term 5 Timetable ────────────────────
    print("\n====================================================")
    print("  STEP 3: MERGING & GENERATING COMPLETE CSV")
    print("====================================================")
    unique_sessions = deduplicate_sessions(all_sessions)
    print(f"[OK] Total combined unique sessions (Sec E + Sec F + Sec EF): {len(unique_sessions)}")
    
    with open(JSON_OUTPUT_NAME, "w", encoding="utf-8") as f:
        json.dump({"data": unique_sessions}, f, indent=2, ensure_ascii=False)
        
    convert_sessions_to_csv(unique_sessions, args.csv)
    with open(args.csv, "r", encoding="utf-8") as f:
        update_embedded_html(f.read())
    print(f"[OK] Complete batch timetable saved to {args.csv}!")

if __name__ == "__main__":
    main()
