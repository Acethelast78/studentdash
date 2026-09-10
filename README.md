# XLRI Enrollment Dashboard & Multi-Term Timetable

Standalone, optimized dashboard for XLRI Delhi BMD campus student schedules, multi-student comparison, group study scheduling, and attendance tracking.

* **Dashboard File:** [`xlri_enrollment_dashboard (2).html`](file:///C:/Users/rajaw/.gemini/antigravity/scratch/term4_final/xlri_enrollment_dashboard%20(2).html)
* **ERP Sync Tool:** [`sync_erp.py`](file:///C:/Users/rajaw/.gemini/antigravity/scratch/term4_final/sync_erp.py)

---

## 🚀 Term 5 Highlights & New Features

1. **Default Term 5 View:**
   * Opens directly to **Term 5 (Sep 11, 2026 – Dec 31, 2026)**.
   * Dynamic academic calendar spanning 17 weeks and 112 days.

2. **Term Selector Dropdown:**
   * Located directly next to the **Subject Filter dropdown** in the Timetable toolbar.
   * Allows 1-click switching between **Term 5 (Current)** and **Term 4 (Archived)**.

3. **Frozen Term 4 Archive:**
   * The complete, finalized Term 4 timetable (including September end-term exams) is permanently embedded as a static dataset.
   * Loads instantly offline with zero external network requests.

4. **Automated XL ERP Syncing:**
   * Direct integration with XLRI ERP API (`https://xlerp.xlri.ac.in/api/v1`).
   * Clean JSON session schema parsing with automatic time slot allocation (`08:30`, `10:20`, `12:10`, `14:45`, `16:30`, `18:15`, `20:00`), room numbers (`MCR 07`, `MCR 08`), faculty names, and reschedule/cancellation badges.

5. **UI Streamlining:**
   * Removed unused "Print Schedule" button to free up toolbar space.
   * Cleanly aligned **Term Selector**, **Subject Filter**, **Attendance Tracker**, **Export iCal**, and **Sync ERP** action buttons.

---

## 🔄 How to Sync Live Schedule from XL ERP

### Method 1: Python CLI Tool (Recommended)
Run the sync script in terminal:
```bash
python sync_erp.py
```
*Prompts for your XL ERP email and password securely, fetches all sessions for Term 5 (`2026-09-11` to `2026-12-31`), saves `term5_schedule.json`, and updates the dashboard HTML automatically.*

**Optional Flags:**
```bash
# With credentials
python sync_erp.py --email your.email@xlri.ac.in --password yourpassword

# With existing Bearer token from DevTools
python sync_erp.py --token <token_without_Bearer_prefix>

# Custom date range
python sync_erp.py --start 2026-09-11 --end 2026-12-31
```

---

### Method 2: In-Browser Sync Modal
1. Open the dashboard in your browser.
2. Ensure **Term 5** is selected.
3. Click the **🔄 Sync ERP** button in the timetable toolbar.
4. Either paste your Bearer token to fetch live, or paste the raw JSON payload from `/schedule/my-schedule/student` and click **📥 Import JSON**.
