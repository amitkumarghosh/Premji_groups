# teamlead.py
import streamlit as st
from database import fetch_employee_details, run_query
from typing import List, Tuple
import os

# Try to reuse your attendance functions (attendance_page + get_current_ist)
try:
    from attendance import attendance_page, get_current_ist
except Exception:
    # If attendance.py isn't importable or does not export get_current_ist,
    # define a local fallback get_current_ist (NTP -> HTTP APIs -> system)
    attendance_page = None

    import pytz
    import requests
    import ntplib
    from datetime import datetime

    def get_current_ist(timeout=3, debug=False):
        """
        Fallback implementation that mirrors attendance.py:
         1) NTP (pool.ntp.org)
         2) worldtimeapi.org
         3) timeapi.io
         4) system clock fallback (with a warning)
        Returns naive datetime representing IST.
        """
        system_ist = datetime.now(pytz.timezone("Asia/Kolkata")).replace(tzinfo=None)

        # 1) NTP
        try:
            client = ntplib.NTPClient()
            resp = client.request("pool.ntp.org", version=3, timeout=timeout)
            utc_dt = datetime.utcfromtimestamp(resp.tx_time).replace(tzinfo=pytz.utc)
            ist_dt = utc_dt.astimezone(pytz.timezone("Asia/Kolkata")).replace(tzinfo=None)
            if debug:
                return ist_dt, "ntp://pool.ntp.org", system_ist
            return ist_dt
        except Exception:
            pass

        # 2) worldtimeapi
        try:
            url = "https://worldtimeapi.org/api/timezone/Asia/Kolkata"
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            aware = datetime.fromisoformat(data["datetime"])
            ist_dt = aware.astimezone(pytz.timezone("Asia/Kolkata")).replace(tzinfo=None)
            if debug:
                return ist_dt, "https://worldtimeapi.org", system_ist
            return ist_dt
        except Exception:
            pass

        # 3) timeapi.io
        try:
            url2 = "https://timeapi.io/api/Time/current/zone?timeZone=Asia/Kolkata"
            r2 = requests.get(url2, timeout=timeout)
            r2.raise_for_status()
            d = r2.json()
            aware = datetime(
                d["year"], d["month"], d["day"],
                d["hour"], d["minute"], int(d.get("seconds", 0)),
                int(d.get("milliseconds", 0)) * 1000,
                tzinfo=pytz.timezone("Asia/Kolkata")
            )
            ist_dt = aware.replace(tzinfo=None)
            if debug:
                return ist_dt, "https://timeapi.io", system_ist
            return ist_dt
        except Exception:
            pass

        # fallback
        st.warning("Network time sources unavailable — using system clock in IST.")
        if debug:
            return system_ist, "system_fallback", system_ist
        return system_ist


def get_technicians_for_teamlead_by_center(teamlead_code: str) -> List[Tuple[str, str]]:
    """
    Find technicians who belong to the same center_code as the teamlead.
    Returns list of tuples (employee_code, employee_name, role).
    """
    tl = fetch_employee_details(teamlead_code)
    if not tl:
        st.error("Couldn't find your record in employee_details.")
        return []

    tl = dict(tl)
    center_code = tl.get("center_code") or tl.get("center") or tl.get("centerId")
    if not center_code:
        st.error("Your profile does not have a center_code. Please update employee_details.")
        return []

    query = """
        SELECT employee_code, employee_name, user_role, employee_status
        FROM employee_details
        WHERE center_code = :center_code
          AND (user_role = 'Technician' OR user_role = 'technician' OR user_role = 'Employee')
        ORDER BY employee_name
    """
    rows = run_query(query, {"center_code": center_code}, fetch_one=False)
    if not rows:
        return []
    result = []
    for r in rows:
        if r.get("employee_code") == teamlead_code:
            continue
        status = (r.get("employee_status") or "").lower()
        # include only active-like users
        if status not in ("inactive", "0", "false"):
            result.append((r["employee_code"], r["employee_name"], r.get("user_role")))
    return result


def main():
    """
    TeamLead page that reuses the existing attendance_page UI for the selected technician.
    Also uses network-backed IST for time debugging/display so it's consistent with attendance.py.
    """
    st.header("Mark attendance for the other")
    st.write("As a Team Leader you can mark attendance on behalf of technicians under your supervision.")

    # session / auth expectations
    logged_in = st.session_state.get("logged_in", False)
    user_data = st.session_state.get("user_data", {})  # expects 'code','role','name' etc
    if not logged_in or not user_data:
        st.warning("You must be logged in to use this page. Please log in first.")
        return

    teamlead_code = user_data.get("code") or st.session_state.get("user_code")
    if not teamlead_code:
        st.error("Missing teamlead code in session.")
        return

    # Show network time vs system time (helpful to verify correct time source)
    try:
        # try debug mode to get source info
        dt, src, sys_dt = get_current_ist(debug=True)
        st.info(f"Using network time source: {src} — IST now: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        st.caption(f"System clock (IST) shows: {sys_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception:
        # fallback: call without debug
        try:
            dt = get_current_ist()
            st.info(f"IST now: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception:
            # silently ignore if the helper completely fails
            pass

    technicians = get_technicians_for_teamlead_by_center(teamlead_code)
    if not technicians:
        st.warning("No technicians found under your supervision. Please check the employee_details table or schema.")
        return

    # Build options: show role for clarity
    options = [f"{code} — {name} ({role or 'Technician'})" for code, name, role in technicians]
    selected = st.selectbox("Select Technician (employee_code — employee_name)", options)
    selected_code = selected.split(" — ", 1)[0].strip()

    # Fetch full technician row to build a user dict that matches your usual login/user structure
    tech_row = fetch_employee_details(selected_code)
    if not tech_row:
        st.error("Failed to load selected technician details.")
        return
    tech = dict(tech_row)

    # Build a user dict expected by attendance_page(user)
    user_for_attendance = {
        "employee_code": tech.get("employee_code"),
        "employee_name": tech.get("employee_name"),
        "user_role": tech.get("user_role") or "Technician",
        "center_code": tech.get("center_code"),
        "center_name": tech.get("center_name"),
        "employee_status": tech.get("employee_status"),
    }

    st.markdown("---")
    st.write("Below is the existing attendance interface for the selected technician. Use it the same way you do when marking your own attendance.")
    st.caption("Note: this will perform the same checks and saves as the regular Attendance page.")

    if attendance_page is None:
        st.error("attendance_page() is not importable — ensure attendance.py exports attendance_page(user).")
        return

    # set session values for the attendance_page (some pages rely on session['user'])
    st.session_state["user_for_teamlead_action"] = user_for_attendance
    previous_user = st.session_state.get("user")
    st.session_state["user"] = user_for_attendance

    try:
        attendance_page(user_for_attendance)
    finally:
        # restore session user to avoid side-effects
        st.session_state["user"] = previous_user


if __name__ == "__main__":
    main()
