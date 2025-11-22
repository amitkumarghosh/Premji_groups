import streamlit as st
from io import BytesIO, StringIO
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, date
import os
import csv
import base64
from PIL import Image, UnidentifiedImageError

from database import run_query  # your DB helper

# Where to save temp images (Option B - temp directory)
IMAGE_DIR = Path(tempfile.gettempdir()) / "attendance_images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# How long to keep temp files (hours)
CLEANUP_HOURS = 24


def _cleanup_old_images():
    cutoff = datetime.now() - timedelta(hours=CLEANUP_HOURS)
    for p in IMAGE_DIR.glob("*"):
        try:
            if datetime.fromtimestamp(p.stat().st_mtime) < cutoff:
                p.unlink(missing_ok=True)
        except Exception:
            pass


def _ensure_bytes(blob):
    """Accepts bytes, memoryview, or str and returns bytes or None."""
    if blob is None:
        return None
    if isinstance(blob, bytes):
        return blob
    if isinstance(blob, memoryview):
        return blob.tobytes()
    if isinstance(blob, str):
        return blob.encode("utf-8", errors="ignore")
    try:
        return bytes(blob)
    except Exception:
        return None


def _blob_to_png_bytes(blob):
    """Try to convert any image blob to PNG bytes via PIL. If that fails, return raw bytes."""
    b = _ensure_bytes(blob)
    if not b:
        return None
    try:
        img = Image.open(BytesIO(b))
        # Normalize to a safe mode
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")
        out = BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()
    except UnidentifiedImageError:
        # Not a recognized image — return raw bytes (still may display depending on browser)
        return b
    except Exception:
        return b


def _save_blob_to_file(blob: bytes, prefix: str):
    """Save blob to disk (PNG if convertible) and return Path or None."""
    pngbytes = _blob_to_png_bytes(blob)
    if not pngbytes:
        return None
    ts = int(datetime.now().timestamp() * 1000)
    dest = IMAGE_DIR / f"{prefix}_{ts}.png"
    try:
        with open(dest, "wb") as f:
            f.write(pngbytes)
        return dest
    except Exception:
        return None


def _blob_to_data_url(blob: bytes):
    """Return a data:image/png;base64,... string suitable for use as an href/src."""
    pngbytes = _blob_to_png_bytes(blob)
    if not pngbytes:
        return None
    b64 = base64.b64encode(pngbytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _build_search_query(emp_code: str = None, start_date: date = None, end_date: date = None):
    base = "SELECT * FROM preamji_attendance"
    conditions = []
    params = {}
    if emp_code:
        conditions.append("emp_code_of_thetechnician = :emp")
        params["emp"] = emp_code
    if start_date:
        conditions.append("attendance_date >= :start")
        params["start"] = start_date.isoformat()
    if end_date:
        conditions.append("attendance_date <= :end")
        params["end"] = end_date.isoformat()
    if conditions:
        base += " WHERE " + " AND ".join(conditions)
    base += " ORDER BY id DESC"
    return base, params


def _rows_to_csv_bytes(rows):
    """Convert list-of-mappings rows to CSV bytes."""
    if not rows:
        return b""
    columns = list(rows[0].keys())
    str_buf = StringIO()
    writer = csv.writer(str_buf)
    writer.writerow(columns)
    for r in rows:
        writer.writerow([r.get(c) if r.get(c) is not None else "" for c in columns])
    return str_buf.getvalue().encode("utf-8")


def _rows_to_dataframe(rows):
    import pandas as pd
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _escape_html(s):
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _make_image_cell(blob, row_id, col_key):
    """Return HTML for a single image cell (thumbnail + click to open)."""
    if not blob:
        return '<div style="color:#999">No image</div>'

    data_url = _blob_to_data_url(blob)
    saved = _save_blob_to_file(blob, prefix=f"att_{row_id}_{col_key}")

    if data_url:
        return (
            f'<a href="{data_url}" target="_blank" rel="noopener noreferrer" '
            f'title="Open full image"><img src="{data_url}" '
            f'style="max-width:80px;max-height:60px;border-radius:4px;"/></a>'
        )

    if saved:
        file_url = f"file://{saved}"
        return (
            f'<a href="{file_url}" target="_blank" rel="noopener noreferrer">'
            f'<img src="{file_url}" style="max-width:80px;max-height:60px;'
            f'border-radius:4px;"/></a>'
        )

    return '<div style="color:#999">No image</div>'


def _build_html_table(rows, max_rows=100):
    """Render an HTML table (compact) with 4 separate image columns."""
    # Normal data columns (DB field name, header text) – ID REMOVED
    columns = [
        ("attendance_date", "Date"),
        ("emp_code_of_thetechnician", "Employee Code"),
        ("name_of_technician", "Name"),
        ("on_duty_in_time", "In Time"),
        ("on_duty_out_time", "Out Time"),
        ("total_working_hrs", "Total Hrs"),
        ("effective_working_hrs", "Effective Hrs"),
        ("center_location", "Location"),
    ]

    def _image_cell(row, col_key):
        """Return HTML for a single image cell."""
        blob = row.get(col_key)
        if not blob:
            return '<div style="color:#999">No image</div>'

        # we can still use id internally if present, but it's not displayed
        row_id = row.get("id", "")
        data_url = _blob_to_data_url(blob)
        saved = _save_blob_to_file(blob, prefix=f"att_{row_id}_{col_key}")

        if data_url:
            return (
                f'<a href="{data_url}" target="_blank" rel="noopener noreferrer" '
                f'title="Open full image">'
                f'<img src="{data_url}" '
                f'style="max-width:80px;max-height:60px;border-radius:4px;"/></a>'
            )
        if saved:
            file_url = f"file://{saved}"
            return (
                f'<a href="{file_url}" target="_blank" rel="noopener noreferrer">'
                f'<img src="{file_url}" '
                f'style="max-width:80px;max-height:60px;border-radius:4px;"/></a>'
            )
        return '<div style="color:#999">No image</div>'

    html = []
    html.append("<style>")
    html.append("""
        table.att-table{
            width:100%;
            border-collapse:collapse;
            font-family:inherit;
            table-layout:fixed;
        }
        table.att-table th, table.att-table td{
            padding:8px 10px;
            border-bottom:1px solid #2a2a2a;
            text-align:left;
            vertical-align:top;
        }
        table.att-table th{
            background:#2a2a2a;
            color:#fff;
            font-weight:600;
        }
        table.att-table tr:hover{background:#151515}
        .thumb-cell img{
            max-width:80px;
            max-height:60px;
            border-radius:4px;
            display:block;
        }
    """)
    html.append("</style>")

    html.append('<table class="att-table">')
    # ---------- table header ----------
    html.append("<thead><tr>")
    html.append("<th>In Photo</th>")
    html.append("<th>Out Photo</th>")
    html.append("<th>Break start photo</th>")
    html.append("<th>Break end photo</th>")
    for _, label in columns:
        html.append(f"<th>{_escape_html(label)}</th>")
    html.append("</tr></thead><tbody>")

    # ---------- table body ----------
    for r in rows[:max_rows]:
        html.append("<tr>")

        # 4 separate image cells
        html.append(f'<td class="thumb-cell">{_image_cell(r, "on_duty_in_image")}</td>')
        html.append(f'<td class="thumb-cell">{_image_cell(r, "on_duty_out_image")}</td>')
        html.append(f'<td class="thumb-cell">{_image_cell(r, "intermidiate_off_out_image")}</td>')
        html.append(f'<td class="thumb-cell">{_image_cell(r, "intermidiate_off_in_image")}</td>')

        # normal text columns
        for col_key, _label in columns:
            val = r.get(col_key)
            html.append(f"<td>{_escape_html(val)}</td>")

        html.append("</tr>")

    html.append("</tbody></table>")
    return "\n".join(html)


def admin_attendance_page():
    if not st.session_state.get("logged_in"):
        st.warning("Please log in to view attendance records.")
        return

    # --- Maintenance button at top of page ---
    if st.button("🧹 Clear old picture (older than 31 days)"):
        try:
            clear_sql = """
                UPDATE preamji_attendance
                SET
                    on_duty_in_image = NULL,
                    on_duty_out_image = NULL,
                    intermidiate_off_out_image = NULL,
                    intermidiate_off_in_image = NULL
                WHERE attendance_date < (CURDATE() - INTERVAL 31 DAY)
            """
            # run the UPDATE
            run_query(clear_sql, fetch_one=False)
            st.success("Old picture fields cleared for all records older than 31 days.")
        except Exception as e:
            st.error(f"Failed to clear old pictures: {e}")
#===================================================================
    # --- Summary report for a date range (per employee) ---
    st.subheader("Attendance summary report")

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        summary_start = st.date_input(
            "Report start date", 
            value=date.today() - timedelta(days=30),
            key="summary_start_date"
        )
    with c2:
        summary_end = st.date_input(
            "Report end date", 
            value=date.today(),
            key="summary_end_date"
        )
    with c3:
        generate_report = st.button("Generate report", key="btn_generate_report")

    if generate_report:
        if summary_start > summary_end:
            st.error("Start date cannot be after end date.")
        else:
            summary_sql = """
                SELECT
                    emp_code_of_thetechnician AS Employee_Code,
                    name_of_technician       AS Employee_Name,
                    COUNT(*)                 AS Count_Days,
                    COALESCE(SUM(total_working_hrs), 0)  AS Total_Working_Hours,
                    COALESCE(SUM(total_break_hrs), 0)    AS Total_Break_Hours
                FROM preamji_attendance
                WHERE attendance_date BETWEEN :start AND :end
                GROUP BY emp_code_of_thetechnician, name_of_technician
                ORDER BY employee_name, employee_code
            """
            params = {
                "start": summary_start.isoformat(),
                "end": summary_end.isoformat(),
            }
            summary_rows = run_query(summary_sql, params, fetch_one=False) or []
            st.write(f"Found {len(summary_rows)} employee(s) in this date range.")

            if summary_rows:
                # Convert to dataframe for nice table view
                df_summary = _rows_to_dataframe(summary_rows)
                st.dataframe(df_summary, use_container_width=True)

                # CSV download
                csv_bytes = _rows_to_csv_bytes(summary_rows)
                st.download_button(
                    "Download summary report as CSV",
                    data=csv_bytes,
                    file_name=f"attendance_summary_{summary_start}_to_{summary_end}.csv",
                    mime="text/csv",
                )
            else:
                st.info("No attendance data found for the selected date range.")



#===================================================================
    # ---- Search area ----
    st.subheader("Search attendance (employee code + date range)")
    with st.form("attendance_search_form", clear_on_submit=False):
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            emp_code = st.text_input("Employee Code (exact, e.g. AL0001)")
        with col2:
            start = st.date_input("Start date", value=date.today() - timedelta(days=30))
        with col3:
            end = st.date_input("End date", value=date.today())
        submitted = st.form_submit_button("Search")

    # ---- Search results OUTSIDE the form (full width) ----
    if submitted:
        q, params = _build_search_query(
            emp_code.strip() if emp_code else None, start, end
        )
        rows = run_query(q, params, fetch_one=False) or []
        st.write(f"Found {len(rows)} matching rows")

        if rows:
            csv_bytes = _rows_to_csv_bytes(rows)
            st.download_button(
                "Download results as CSV",
                data=csv_bytes,
                file_name="attendance_results.csv",
                mime="text/csv",
            )

            html = _build_html_table(rows, max_rows=len(rows))
            st.markdown(
                f"""
                <div style="width:100%; overflow-x:auto;">
                    {html}
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info("No records match your search.")

    st.markdown("---")
    st.caption(
        "Images are rendered as thumbnails and open in a new tab when clicked. "
        "Temporary image files are saved in the server's temp folder and cleaned after 24 hours."
    )

    _cleanup_old_images()

    # --- Today's records, shown only after button click ---
    st.subheader("Today's attendance entries (table)")

    if st.button("Show today's attendance records"):
        today = date.today().isoformat()
        today_sql = """
            SELECT *
            FROM preamji_attendance
            WHERE attendance_date = :today
            ORDER BY id DESC
        """
        today_rows = run_query(today_sql, {"today": today}, fetch_one=False) or []

        if today_rows:
            html = _build_html_table(today_rows, max_rows=len(today_rows))
            st.markdown(
                f"""
                <div style="width:100%; overflow-x:auto;">
                    {html}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # CSV download for today's records
            csv_bytes = _rows_to_csv_bytes(today_rows)
            st.download_button(
                "Download today's attendance as CSV",
                data=csv_bytes,
                file_name=f"attendance_{today}.csv",
                mime="text/csv",
            )
        else:
            st.info("No attendance records found for today.")

    st.markdown("---")
