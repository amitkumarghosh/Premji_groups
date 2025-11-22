import streamlit as st
from datetime import datetime
import pytz
import requests
import ntplib
from sqlalchemy import text
from database import get_db_engine
from io import BytesIO
from PIL import Image
import base64
import time


# -------------------------------------------------------------
#  TRUE INTERNET TIME (NTP -> API -> fallback)
# -------------------------------------------------------------
def get_current_ist(timeout=3, debug=False):
    """
    Returns a TRUE IST datetime regardless of local PC time.
    Steps:
        1. NTP (Highly accurate)
        2. worldtimeapi.org
        3. timeapi.io
        4. System clock (fallback with warning)
    Output: naive datetime (IST) for MySQL DATETIME compatibility
    """

    # Local system IST (fallback last option)
    system_ist = datetime.now(pytz.timezone("Asia/Kolkata")).replace(tzinfo=None)

    # ---------- 1. Try NTP ----------
    try:
        client = ntplib.NTPClient()
        response = client.request("pool.ntp.org", version=3, timeout=timeout)
        utc_dt = datetime.utcfromtimestamp(response.tx_time).replace(tzinfo=pytz.utc)
        ist_dt = utc_dt.astimezone(pytz.timezone("Asia/Kolkata")).replace(tzinfo=None)

        if debug:
            return ist_dt, "NTP (pool.ntp.org)", system_ist
        return ist_dt

    except Exception:
        pass

    # ---------- 2. Try worldtimeapi ----------
    try:
        api = "https://worldtimeapi.org/api/timezone/Asia/Kolkata"
        r = requests.get(api, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        aware = datetime.fromisoformat(data["datetime"])
        ist_dt = aware.astimezone(pytz.timezone("Asia/Kolkata")).replace(tzinfo=None)

        if debug:
            return ist_dt, "worldtimeapi.org", system_ist
        return ist_dt

    except Exception:
        pass

    # ---------- 3. Try timeapi.io ----------
    try:
        api2 = "https://timeapi.io/api/Time/current/zone?timeZone=Asia/Kolkata"
        r2 = requests.get(api2, timeout=timeout)
        r2.raise_for_status()
        d = r2.json()

        aware = datetime(
            d["year"],
            d["month"],
            d["day"],
            d["hour"],
            d["minute"],
            int(d["seconds"]),
            int(d["milliseconds"]) * 1000,
            tzinfo=pytz.timezone("Asia/Kolkata"),
        )
        ist_dt = aware.replace(tzinfo=None)

        if debug:
            return ist_dt, "timeapi.io", system_ist
        return ist_dt

    except Exception:
        pass

    # ---------- 4. Last fallback (system clock) ----------
    st.warning("⚠️ Network time unavailable — using machine's local clock which may be incorrect.")
    if debug:
        return system_ist, "SYSTEM CLOCK (fallback)", system_ist
    return system_ist


# -------------------------------------------------------------
# IMAGE COMPRESSION
# -------------------------------------------------------------
def compress_image(image_data, max_size=(640, 480), quality=60):
    try:
        img = Image.open(BytesIO(image_data))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail(max_size)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()
    except Exception as e:
        st.error(f"Image compression failed: {e}")
        return image_data


# -------------------------------------------------------------
# MAIN ATTENDANCE PAGE
# -------------------------------------------------------------
def attendance_page(user):

    st.header("🕒 Attendance Capture")
    st.markdown("---")

    # Get TRUE INTERNET-BASED IST
    now_ist = get_current_ist()
    today_ist = now_ist.date()

    emp_code = user.get("employee_code")
    emp_name = user.get("employee_name")

    st.write(f"👷 Employee: **{emp_name} ({emp_code})**")
    st.write(f"📅 Date: **{today_ist}**")
    st.write(f"🕓 Time (IST): **{now_ist.strftime('%H:%M:%S')}**")

    # Action map
    action_map = {
        "On Duty In": ("on_duty_in_time", "on_duty_in_image", "🟢", "#00b894", "#009e6f"),
        "Break Out": ("intermidiate_off_out_time", "intermidiate_off_out_image", "🟠", "#fd7e14", "#e46b00"),
        "Break In": ("intermidiate_off_in_time", "intermidiate_off_in_image", "🔵", "#1e90ff", "#0066cc"),
        "On Duty Out": ("on_duty_out_time", "on_duty_out_image", "🔴", "#ff4d4d", "#cc0000"),
    }

    # Fetch today's record
    engine = get_db_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT *
                FROM preamji_attendance
                WHERE emp_code_of_thetechnician=:emp AND attendance_date=:dt
            """
            ),
            {"emp": emp_code, "dt": today_ist},
        ).fetchone()

    record = (
        dict(row._mapping)
        if row
        else {
            "id": None,
            "on_duty_in_time": None,
            "intermidiate_off_out_time": None,
            "intermidiate_off_in_time": None,
            "on_duty_out_time": None,
        }
    )

    # Determine next action
    if not record["on_duty_in_time"]:
        next_action = "On Duty In"
    elif not record["intermidiate_off_out_time"]:
        next_action = "Break Out"
    elif not record["intermidiate_off_in_time"]:
        next_action = "Break In"
    elif not record["on_duty_out_time"]:
        next_action = "On Duty Out"
    else:
        next_action = None

    if not next_action:
        st.success("🎉 All attendance for today completed!")
        show_today_summary(emp_code)
        return

    # Dynamic UI style
    _, _, icon, start_col, end_col = action_map[next_action]
    button_text = f"{icon} ***Please mark your attendance – {next_action}***"

    # Gradient camera button style (same as your older version)
    st.markdown(
        f"""
        <style>
        div[data-testid="stCameraInput"] button {{
            font-size: 24px !important;
            font-weight: 800 !important;
            padding: 1.1em 2.5em !important;
            background: linear-gradient(90deg, {start_col}, {end_col}) !important;
            color: white !important;
            border-radius: 18px !important;
            width: 100% !important;
            border: none !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Oval camera preview – only centre visible
    st.markdown(
        """
        <style>
        /* Center the camera widget */
        div[data-testid="stCameraInput"] {
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        /* Camera preview itself (video / captured image) */
        div[data-testid="stCameraInput"] video,
        div[data-testid="stCameraInput"] img {
            width: min(55vw, 220px) !important;
            height: min(55vw, 220px) !important;
            object-fit: cover !important;
            background: black;

            /* show only an oval in the middle */
            clip-path: ellipse(36% 50% at 50% 46%);
            -webkit-clip-path: ellipse(36% 50% at 50% 46%);
            border-radius: 50%;
            border: 3px solid #ff4d4d;
        }

        @media (max-width: 480px) {
            div[data-testid="stCameraInput"] button {
                font-size: 18px !important;
                padding: 0.8em 1.2em !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.caption("📸 Please keep your face inside the red oval while capturing.")

    img = st.camera_input(
        button_text,
        key=f"{emp_code}_{today_ist}",
    )

    if "last_capture" not in st.session_state:
        st.session_state.last_capture = None

    if img:
        h = hash(img.getvalue())
        if h != st.session_state.last_capture:

            compressed = compress_image(img.getvalue())
            tcol, icol, *_ = action_map[next_action]

            with engine.begin() as conn:

                # UPDATE
                if record["id"]:
                    conn.execute(
                        text(
                            f"UPDATE preamji_attendance "
                            f"SET {tcol}=:t, {icol}=:img, last_edit_timestamp=:ts "
                            f"WHERE id=:id"
                        ),
                        {"t": now_ist, "img": compressed, "ts": now_ist, "id": record["id"]},
                    )

                    # Recalculate only for Out
                    if next_action == "On Duty Out":
                        rec = conn.execute(
                            text(
                                """
                                SELECT on_duty_in_time,
                                       intermidiate_off_out_time,
                                       intermidiate_off_in_time,
                                       on_duty_out_time
                                FROM preamji_attendance
                                WHERE id=:id
                            """
                            ),
                            {"id": record["id"]},
                        ).fetchone()

                        if rec and rec.on_duty_in_time and rec.on_duty_out_time:
                            ti = rec.on_duty_in_time
                            to = rec.on_duty_out_time
                            total_work = (to - ti).total_seconds() / 3600

                            if rec.intermidiate_off_out_time and rec.intermidiate_off_in_time:
                                bo = rec.intermidiate_off_out_time
                                bi = rec.intermidiate_off_in_time
                                total_break = (bi - bo).total_seconds() / 3600
                            else:
                                total_break = 0

                            eff = total_work - total_break

                            conn.execute(
                                text(
                                    """
                                    UPDATE preamji_attendance
                                    SET total_working_hrs=:tw,
                                        total_break_hrs=:tb,
                                        effective_working_hrs=:ew
                                    WHERE id=:id
                                """
                                ),
                                {
                                    "tw": round(total_work, 2),
                                    "tb": round(total_break, 2),
                                    "ew": round(eff, 2),
                                    "id": record["id"],
                                },
                            )

                # INSERT
                else:
                    center = conn.execute(
                        text(
                            "SELECT center_name, center_location "
                            "FROM employee_details WHERE employee_code=:e"
                        ),
                        {"e": emp_code},
                    ).fetchone()

                    cname = center.center_name if center else None
                    cloc = center.center_location if center else None

                    conn.execute(
                        text(
                            f"""
                            INSERT INTO preamji_attendance(
                                attendance_date,
                                emp_code_of_thetechnician,
                                name_of_technician,
                                center_name,
                                center_location,
                                {tcol},
                                {icol},
                                all_innitial_time,
                                last_edit_timestamp
                            )
                            VALUES (
                                :dt,
                                :emp,
                                :name,
                                :cname,
                                :cloc,
                                :t,
                                :img,
                                :first,
                                :ts
                            )
                            """
                        ),
                        {
                            "dt": today_ist,
                            "emp": emp_code,
                            "name": emp_name,
                            "cname": cname,
                            "cloc": cloc,
                            "t": now_ist,
                            "img": compressed,
                            "first": now_ist,
                            "ts": now_ist,
                        },
                    )

            st.session_state.last_capture = h
            st.success(f"✅ {next_action} recorded!")
            time.sleep(1)
            st.rerun()

    show_today_summary(emp_code)


# -------------------------------------------------------------
# SUMMARY VIEW
# -------------------------------------------------------------
def show_today_summary(emp_code):
    """Displays today's attendance summary with thumbnails and working View Full link/button."""

    st.markdown("### 📋 Today's Attendance Summary")

    # Keep images non-interactive but allow the link below to open the full image.
    st.markdown(
        """
        <style>
        /* make the IMG itself non-interactive (prevents direct right-click on the image),
           while anchor tags (links) remain fully clickable */
        .attendance-thumb img {
            pointer-events: none !important;
            user-select: none !important;
            border-radius: 8px;
            border: 1px solid #ccc;
            width: 90px;
            height: 90px;
            object-fit: cover;
            display:block;
            margin-bottom:6px;
        }
        .view-full-link {
            display:inline-block;
            padding:6px 10px;
            background:#0d6efd;
            color:#fff !important;
            border-radius:8px;
            text-decoration:none;
            font-weight:600;
            font-size:14px;
        }
        .view-full-link:hover {
            opacity:0.95;
            transform:translateY(-1px);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # get today's IST date using your existing helper
    now_ist = get_current_ist()
    today_ist = now_ist.date()

    engine = get_db_engine()
    with engine.connect() as conn:
        r = conn.execute(
            text(
                """
                SELECT
                    on_duty_in_time,
                    on_duty_in_image,
                    intermidiate_off_out_time,
                    intermidiate_off_out_image,
                    intermidiate_off_in_time,
                    intermidiate_off_in_image,
                    on_duty_out_time,
                    on_duty_out_image,
                    total_working_hrs,
                    total_break_hrs,
                    effective_working_hrs
                FROM preamji_attendance
                WHERE emp_code_of_thetechnician = :emp
                  AND attendance_date = :dt
            """
            ),
            {"emp": emp_code, "dt": today_ist},
        ).fetchone()

    if not r:
        st.info("No attendance data captured yet for today.")
        return

    record = dict(r._mapping)

    actions = [
        ("On Duty In", "on_duty_in_time", "on_duty_in_image"),
        ("Break Out", "intermidiate_off_out_time", "intermidiate_off_out_image"),
        ("Break In", "intermidiate_off_in_time", "intermidiate_off_in_image"),
        ("On Duty Out", "on_duty_out_time", "on_duty_out_image"),
    ]

    if "preview_image" not in st.session_state:
        st.session_state.preview_image = None
        st.session_state.preview_label = None

    for action_label, time_col, image_col in actions:
        col1, col2, col3 = st.columns([2, 3, 4])
        with col1:
            st.markdown(f"**{action_label}**")
        with col2:
            ts = record.get(time_col)
            st.write(ts.strftime("%H:%M:%S") if ts else "—")
        with col3:
            image_data = record.get(image_col)
            if image_data:
                # create thumbnail bytes
                img = Image.open(BytesIO(image_data))
                img.thumbnail((100, 100))
                buf = BytesIO()
                img.save(buf, format="JPEG")
                thumb_bytes = buf.getvalue()
                thumb_b64 = base64.b64encode(thumb_bytes).decode("utf-8")

                # thumbnail HTML (img is non-interactive by CSS)
                st.markdown(
                    f"""
                    <div class="attendance-thumb" style="display:flex;flex-direction:column;align-items:center;">
                        <img src="data:image/jpeg;base64,{thumb_b64}" alt="thumbnail" />
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Preview button
                btn_key = f"view_{action_label.replace(' ', '_')}"
                if st.button(f"🔎 Preview — {action_label}", key=btn_key):
                    st.session_state.preview_image = image_data
                    st.session_state.preview_label = action_label
            else:
                st.write("—")

    # Show full-size preview in-page (if chosen)
    if st.session_state.get("preview_image"):
        st.markdown("---")
        st.subheader(f"🖼️ Full Image Preview — {st.session_state.preview_label}")
        st.image(st.session_state.preview_image, width="auto")
        if st.button("Close Preview"):
            st.session_state.preview_image = None
            st.session_state.preview_label = None

    # Optional: show working-hours summary
    if record.get("on_duty_out_time"):
        st.markdown("---")
        st.subheader("🕒 Today's Working Summary")
        tw = record.get("total_working_hrs") or 0.0
        tb = record.get("total_break_hrs") or 0.0
        ew = record.get("effective_working_hrs") or 0.0
        st.write(f"**Total Working Hours:** {tw} hrs")
        st.write(f"**Total Break Hours:** {tb} hrs")
        st.write(f"**Effective Working Hours:** {ew} hrs")
