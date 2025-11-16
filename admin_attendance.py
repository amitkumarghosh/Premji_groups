# admin_attendance.py
import streamlit as st
from io import BytesIO, StringIO
from pathlib import Path
from datetime import datetime, timedelta, date
import os
import csv
import base64
from PIL import Image, UnidentifiedImageError

from database import run_query  # your DB helper

# Where to save temp images (Option A)
IMAGE_DIR = Path("/mnt/data/attendance_images")
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
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _build_html_table(rows, max_rows=100):
    """Render an HTML table (compact) for the latest rows with a thumbnail column clickable (data URL)."""
    # Table columns to show (map to your DB field names)
    columns = [
        ("id", "ID"),
        ("attendance_date", "Date"),
        ("emp_code_of_thetechnician", "Employee Code"),
        ("name_of_technician", "Name"),
        ("on_duty_in_time", "In Time"),
        ("on_duty_out_time", "Out Time"),
        ("total_working_hrs", "Total Hrs"),
        ("effective_working_hrs", "Effective Hrs"),
        ("center_location", "Location"),
    ]

    html = []
    html.append("<style>")
    html.append("table.att-table{width:100%;border-collapse:collapse;font-family:inherit}")
    html.append("table.att-table th, table.att-table td{padding:8px 10px;border-bottom:1px solid #2a2a2a;text-align:left}")
    html.append("table.att-table th{background:#2a2a2a;color:#fff;font-weight:600}")
    html.append("table.att-table tr:hover{background:#151515}")
    html.append(".thumb-cell img{max-width:80px;max-height:60px;border-radius:4px;display:block;}")
    html.append("</style>")

    html.append('<table class="att-table">')
    # header: add Photo as first column
    html.append("<thead><tr>")
    html.append("<th>Photo</th>")
    for _, label in columns:
        html.append(f"<th>{_escape_html(label)}</th>")
    html.append("</tr></thead><tbody>")

    for i, r in enumerate(rows[:max_rows]):
        # thumbnail: first non-empty image column
        image_cols = [
            "on_duty_in_image",
            "on_duty_out_image",
            "intermediate_off_out_image",
            "intermediate_off_in_image",
        ]
        thumb_html = '<div style="color:#999">No image</div>'
        for col in image_cols:
            blob = r.get(col)
            if blob:
                data_url = _blob_to_data_url(blob)
                saved = _save_blob_to_file(blob, prefix=f"att_{r.get('id')}_{col}")
                if data_url:
                    thumb_html = f'<a href="{data_url}" target="_blank" rel="noopener noreferrer" title="Open full image"><img src="{data_url}" style="max-width:80px;max-height:60px;border-radius:4px;"/></a>'
                elif saved:
                    file_url = f"file://{saved}"
                    thumb_html = f'<a href="{file_url}" target="_blank" rel="noopener noreferrer"><img src="{file_url}" style="max-width:80px;max-height:60px;border-radius:4px;"/></a>'
                break

        html.append("<tr>")
        html.append(f'<td class="thumb-cell">{thumb_html}</td>')
        for col_key, _ in columns:
            val = r.get(col_key)
            html.append(f"<td>{_escape_html(val)}</td>")
        html.append("</tr>")

    html.append("</tbody></table>")
    return "\n".join(html)


def admin_attendance_page():
    if not st.session_state.get("logged_in"):
        st.warning("Please log in to view attendance records.")
        return

    user = st.session_state.get("user", {})
    st.title("Attendance Records")
    st.markdown("Latest 100 attendance records. Use the search box + date range to filter older records.")

    _cleanup_old_images()

    # Latest 100
    st.subheader("Latest 100 attendance entries (table)")
    latest_sql = "SELECT * FROM preamji_attendance ORDER BY id DESC LIMIT 100"
    latest_rows = run_query(latest_sql, fetch_one=False) or []
    if latest_rows:
        html = _build_html_table(latest_rows, max_rows=100)
        st.markdown(html, unsafe_allow_html=True)
        # Offer CSV download
        csv_bytes = _rows_to_csv_bytes(latest_rows)
        st.download_button("Download latest 100 as CSV", data=csv_bytes, file_name="attendance_latest_100.csv", mime="text/csv")
    else:
        st.info("No attendance records found.")

    st.markdown("---")
    # Search area
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

    if submitted:
        q, params = _build_search_query(emp_code.strip() if emp_code else None, start, end)
        rows = run_query(q, params, fetch_one=False) or []
        st.write(f"Found {len(rows)} matching rows")
        if rows:
            csv_bytes = _rows_to_csv_bytes(rows)
            st.download_button("Download results as CSV", data=csv_bytes, file_name="attendance_results.csv", mime="text/csv")
            # show table same style
            html = _build_html_table(rows, max_rows=len(rows))
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.info("No records match your search.")

    st.markdown("---")
    st.caption("Images are rendered as thumbnails and open in a new tab when clicked. Temporary files saved under /mnt/data/attendance_images/ (cleaned after 24h).")
