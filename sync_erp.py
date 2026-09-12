#!/usr/bin/env python3
"""
XL ERP Timetable Multi-Student Sync Utility (5 Students Coverage)
Fetches complete Term 5 timetable data by authenticating the 5 designated student accounts:
  1. Akhilesh K S   (B25344)
  2. Akshat Jain     (B25381)
  3. Pradeep Kumar Dey (B25420)
  4. Anjali Jain     (B25324)
  5. Dhruv Aggarwal  (B25362)

Combines genuine ERP sessions from all students, deduplicates them, and exports to:
  - term5_schedule.json (raw API format)
  - term5_timetable.csv (Google Sheets layout format)
  - index.html (embedded offline fallback)
"""

import sys
import os
import re
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
from datetime import datetime, date, timedelta, timezone

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

# Designated 5 Students Metadata
STUDENTS_CONFIG = [
    {"slot": 1, "name": "Akhilesh K S", "sid": "B25344", "key": "STUDENT_1"},
    {"slot": 2, "name": "Akshat Jain", "sid": "B25381", "key": "STUDENT_2"},
    {"slot": 3, "name": "Pradeep Kumar Dey", "sid": "B25420", "key": "STUDENT_3"},
    {"slot": 4, "name": "Anjali Jain", "sid": "B25324", "key": "STUDENT_4"},
    {"slot": 5, "name": "Dhruv Aggarwal", "sid": "B25362", "key": "STUDENT_5"},
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
                print(f"[WARN] Login succeeded for ({label}: {email}) but token was not found in response.")
                return None
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"[ERROR] Login failed for ({label}: {email}) [HTTP {e.code}]: {err_msg}")
        return None
    except Exception as e:
        print(f"[ERROR] Connection error for ({label}: {email}): {e}")
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
    """Deduplicate sessions across all students."""
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
            
        c_obj = s.get("course") or {}
        c_code = (
            c_obj.get("courseCode", "") or 
            s.get("courseOfferCode", "") or 
            s.get("sessionName", "") or 
            s.get("title", "") or 
            s.get("eventName", "") or 
            s.get("name", "")
        )
        sec_obj = s.get("section") or {}
        sec = sec_obj.get("sectionName", "")
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
    
    # Dynamically determine latest class date from active sessions (at least Nov 30)
    max_session_dt = date(2026, 11, 30)
    for s in sessions:
        if s.get('classDate') and not s.get('isCancelled'):
            try:
                parts = s['classDate'].split('-')
                if len(parts) == 3:
                    s_dt = date(int(parts[0]), int(parts[1]), int(parts[2]))
                    if s_dt > max_session_dt:
                        max_session_dt = s_dt
            except Exception:
                pass

    # Stretch timetable to the Sunday of the latest class week (Mon=0, Sun=6)
    days_to_sunday = (6 - max_session_dt.weekday()) % 7
    end_dt = max_session_dt + timedelta(days=days_to_sunday)
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
            c_obj = s.get('course') or {}
            
            # Robustly extract course code or session/event title (e.g. 'Term V registration')
            code = (
                c_obj.get('courseCode', '') or 
                s.get('courseCode', '') or 
                s.get('sessionName', '') or 
                s.get('title', '') or 
                s.get('eventName', '') or 
                s.get('activityName', '') or 
                s.get('name', '') or 
                c_obj.get('courseName', '') or 
                s.get('description', '') or 
                'Event'
            ).strip()
            
            sec_obj = s.get('section') or {}
            sec_info = sec_obj.get('sectionName', '') or ''
            if not sec_info and s.get('attendingSections'):
                sec_info = "/".join(x.get('sectionName', '') for x in s['attendingSections'] if x.get('sectionName'))
            
            v_obj = s.get('venue') or {}
            venue = v_obj.get('code', '') or v_obj.get('name', '') or ''
            
            slot_text = code
            if sec_info and not re.search(r'\bsec\s*' + re.escape(sec_info) + r'\b', slot_text, re.IGNORECASE):
                slot_text += f" Sec {sec_info}"
            if venue and not re.search(r'\b' + re.escape(venue) + r'\b', slot_text, re.IGNORECASE):
                slot_text += f" ({venue})"
            slots_bucket[slot_idx].append(slot_text)
        
        # Guarantee mandatory institutional events if omitted by ERP student endpoint
        if formatted_date == "11-09-2026":
            has_reg = any("REGISTRATION" in str(x).upper() for x in slots_bucket[0])
            if not has_reg:
                slots_bucket[0].insert(0, "Term V registration (LCR-01)")

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
    """Update TERM5_DEFAULT_CSV and sync timestamp in index.html for offline & GitHub Pages support."""
    fn = "index.html"
    if os.path.exists(fn):
        try:
            with open(fn, "r", encoding="utf-8") as f:
                content = f.read()
            # 1. Update CSV
            start_marker = "const TERM5_DEFAULT_CSV = "
            end_marker = ";\n\nlet currentSelectedTerm"
            start_idx = content.find(start_marker)
            end_idx = content.find(end_marker, start_idx)
            if start_idx != -1 and end_idx != -1:
                content = content[:start_idx + len(start_marker)] + json.dumps(csv_content) + content[end_idx:]
            
            # 2. Update sync timestamp (IST)
            now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%I:%M %p")
            content = re.sub(r"let timetableSyncTime\s*=\s*['\"][^'\"]*['\"];", f"let timetableSyncTime = '{now_ist}';", content)
            
            with open(fn, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[OK] Updated embedded offline CSV and sync timestamp ({now_ist}) in {fn}")
        except Exception as e:
            print(f"[WARN] Could not update {fn}: {e}")

def main():
    parser = argparse.ArgumentParser(description="XL ERP Timetable Multi-Student Sync Utility (5 Students)")
    
    # 5 Student credential arguments
    for cfg in STUDENTS_CONFIG:
        k = cfg["key"]
        slug = k.lower().replace("_", "-")
        parser.add_argument(f"--{slug}-email", default=os.getenv(f"{k}_EMAIL"), help=f"{cfg['name']} ({cfg['sid']}) Email")
        parser.add_argument(f"--{slug}-password", default=os.getenv(f"{k}_PASSWORD"), help=f"{cfg['name']} ({cfg['sid']}) Password")
        parser.add_argument(f"--{slug}-token", default=os.getenv(f"{k}_TOKEN"), help=f"{cfg['name']} ({cfg['sid']}) Bearer Token")
        
    # Backward compatibility for legacy dual-account args
    parser.add_argument("--sec-e-email", default=os.getenv("XL_ERP_SEC_E_EMAIL"), help="Legacy Section E Email")
    parser.add_argument("--sec-e-password", default=os.getenv("XL_ERP_SEC_E_PASSWORD"), help="Legacy Section E Password")
    parser.add_argument("--sec-f-email", default=os.getenv("XL_ERP_SEC_F_EMAIL"), help="Legacy Section F Email")
    parser.add_argument("--sec-f-password", default=os.getenv("XL_ERP_SEC_F_PASSWORD"), help="Legacy Section F Password")
    
    parser.add_argument("--start", default=DEFAULT_START_DATE, help=f"Start Date (YYYY-MM-DD), default: {DEFAULT_START_DATE}")
    parser.add_argument("--end", default=DEFAULT_END_DATE, help=f"End Date (YYYY-MM-DD), default: {DEFAULT_END_DATE}")
    parser.add_argument("--csv", default=CSV_OUTPUT_NAME, help=f"Output CSV path, default: {CSV_OUTPUT_NAME}")
    
    args = parser.parse_args()
    
    all_sessions = []
    successful_students = []
    
    print("================================================================")
    print("  XL ERP TIMETABLE SYNC — 5 DESIGNATED STUDENTS COVERAGE")
    print("================================================================")
    
    for cfg in STUDENTS_CONFIG:
        slot = cfg["slot"]
        name = cfg["name"]
        sid = cfg["sid"]
        k = cfg["key"]
        slug = k.lower()
        
        label = f"Student #{slot}: {name} ({sid})"
        print(f"\n────────────────────────────────────────────────────────────────")
        print(f"  {label}")
        print(f"────────────────────────────────────────────────────────────────")
        
        token = getattr(args, f"{slug}_token", None)
        email = getattr(args, f"{slug}_email", None)
        password = getattr(args, f"{slug}_password", None)
        
        # Legacy fallback if slot 1/2 and legacy env vars are present
        if slot == 1 and not email and args.sec_e_email:
            email, password = args.sec_e_email, args.sec_e_password
        elif slot == 2 and not email and args.sec_f_email:
            email, password = args.sec_f_email, args.sec_f_password
            
        if not token:
            if not email and sys.stdin.isatty():
                email = input(f"Enter Email for {name} ({sid}) [or press Enter to skip]: ").strip()
            if email and not password and sys.stdin.isatty():
                password = get_password_input(f"Enter Password for {name} ({sid}): ")
                
            if email and password:
                token = login(email, password, label=f"{name} ({sid})")
            else:
                print(f"[SKIP] No credentials provided for {label}. Skipping.")
                continue
                
        if token:
            sessions = fetch_schedule(token, label=f"{name} ({sid})", start_date=args.start, end_date=args.end)
            if sessions:
                all_sessions.extend(sessions)
                successful_students.append(f"{name} ({sid}) - {len(sessions)} sessions")
            else:
                print(f"[WARN] 0 sessions returned for {label}.")
                
    # ── Final Merge & Processing ──────────────────────────────────────────
    print("\n================================================================")
    print("  TIMETABLE AGGREGATION & EXPORT")
    print("================================================================")
    print(f"Authenticated accounts with data: {len(successful_students)}/{len(STUDENTS_CONFIG)}")
    for s in successful_students:
        print(f"  ✓ {s}")
        
    if not all_sessions:
        print("[ERROR] No schedule data was fetched from any student account. Timetable not modified.")
        sys.exit(1)
        
    unique_sessions = deduplicate_sessions(all_sessions)
    print(f"\n[OK] Total combined unique class sessions: {len(unique_sessions)}")
    
    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%I:%M %p")
    now_ist_full = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d-%b-%Y %I:%M %p IST")

    with open(JSON_OUTPUT_NAME, "w", encoding="utf-8") as f:
        json.dump({
            "last_synced_time": now_ist,
            "last_synced_full": now_ist_full,
            "total_sessions": len(unique_sessions),
            "data": unique_sessions
        }, f, indent=2, ensure_ascii=False)
        
    convert_sessions_to_csv(unique_sessions, args.csv)
    
    with open(args.csv, "r", encoding="utf-8") as f:
        update_embedded_html(f.read())
        
    print(f"\n[SUCCESS] Full Term 5 timetable successfully synced and saved to {args.csv}!")

if __name__ == "__main__":
    main()
