import streamlit as st
import pandas as pd
import base64
from datetime import timedelta
from io import BytesIO

from database import run_query
from attendance import get_current_ist
from new_wo_entry import get_teamlead_center


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def prepare_workorder_dataframe(rows):
    """
    Convert jobcard_photo BLOB to clickable HTML link.
    """
    df = pd.DataFrame(rows)

    if "Jobcard Photo" in df.columns:
        def make_link(blob):
            if blob is None:
                return ""
            try:
                b64 = base64.b64encode(blob).decode("utf-8")
                return (
                    f'<a href="data:image/png;base64,{b64}" '
                    f'target="_blank">View Photo</a>'
                )
            except Exception:
                return ""

        df["Jobcard Photo"] = df["Jobcard Photo"].apply(make_link)

    return df


def prepare_excel_dataframe(rows):
    """
    Prepare dataframe for Excel download.
    Includes all fields except:
    - jobcard_photo (binary)
    - admin_last_update_time
    - delete_flag
    """
    df = pd.DataFrame(rows)

    columns_to_drop = [
        "Jobcard Photo",          # UI alias (binary)
        "admin_last_update_time", # raw DB column
        "delete_flag"             # soft delete flag
    ]

    # Drop only if present (safe for role-based queries)
    df = df.drop(
        columns=[c for c in columns_to_drop if c in df.columns],
        errors="ignore"
    )

    return df


def fetch_workorders_for_excel(role, params, user):
    """
    Fetch ALL columns for Excel export.
    Excludes delete_flag = 1 records.
    """
    if role == "TeamLeader":
        center = get_teamlead_center(user)
        params["center_code"] = center["center_code"]

        sql = """
            SELECT *
            FROM workorder_entry
            WHERE job_assign_date BETWEEN :from_date AND :to_date
              AND center_code = :center_code
              AND delete_flag = 0
            ORDER BY job_assign_date DESC
        """
    else:
        sql = """
            SELECT *
            FROM workorder_entry
            WHERE job_assign_date BETWEEN :from_date AND :to_date
              AND delete_flag = 0
            ORDER BY job_assign_date DESC
        """

    return run_query(sql, params, fetch_one=False)


# ---------------------------------------------------------
# MAIN PAGE
# ---------------------------------------------------------

def view_workorders_page(user):

    st.header("📊 View Work Orders")

    # -------------------------
    # Date range selection
    # -------------------------
    now_ist = get_current_ist()
    today = now_ist.date()

    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input(
            "From Date",
            value=today - timedelta(days=31),
            max_value=today
        )
    with col2:
        to_date = st.date_input(
            "To Date",
            value=today,
            min_value=from_date,
            max_value=today
        )

    if from_date > to_date:
        st.error("From Date cannot be greater than To Date.")
        return

    # -------------------------
    # Role-based filtering
    # -------------------------
    role = user.get("user_role")

    params = {
        "from_date": from_date,
        "to_date": to_date,
    }

    if role == "TeamLeader":
        center = get_teamlead_center(user)
        params["center_code"] = center["center_code"]

        sql = """
            SELECT
                jobcard_no AS 'Jobcard No',
                jobcard_type AS 'Jobcard Type',
                technician_code AS 'Technician Code',
                name_of_technician AS 'Name of Technician',
                jobcard_photo AS 'Jobcard Photo',
                previous_jobcard_no AS 'Previous Jobcard No',
                job_status AS 'Job Status',
                job_assign_date AS 'Job Assign Date',
                job_compleate_date AS 'Job Complete Date',
                center_code AS 'Center Code'
            FROM workorder_entry
            WHERE job_assign_date BETWEEN :from_date AND :to_date
              AND center_code = :center_code
              AND delete_flag = 0
            ORDER BY job_assign_date DESC
        """
    else:  # Admin / Super Admin
        sql = """
            SELECT
                jobcard_no AS 'Jobcard No',
                jobcard_type AS 'Jobcard Type',
                technician_code AS 'Technician Code',
                name_of_technician AS 'Name of Technician',
                jobcard_photo AS 'Jobcard Photo',
                previous_jobcard_no AS 'Previous Jobcard No',
                job_status AS 'Job Status',
                job_assign_date AS 'Job Assign Date',
                job_compleate_date AS 'Job Complete Date',
                center_code AS 'Center Code'
            FROM workorder_entry
            WHERE job_assign_date BETWEEN :from_date AND :to_date
              AND delete_flag = 0
            ORDER BY job_assign_date DESC
        """

    rows = run_query(sql, params, fetch_one=False)

    if not rows:
        st.info("No workorders found for the selected date range.")
        return

    # -------------------------
    # Optional Excel Download
    # -------------------------
    st.markdown("### ⬇️ Download Workorders")

    excel_rows = fetch_workorders_for_excel(role, params.copy(), user)

    excel_df = pd.DataFrame(excel_rows)

    # Drop only unwanted columns
    excel_df = excel_df.drop(
        columns=[
            "jobcard_photo",
            "admin_last_update_time",
            "delete_flag"
        ],
        errors="ignore"
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        excel_df.to_excel(writer, index=False, sheet_name="Workorders")

    output.seek(0)

    filename = f"workorders_{from_date}_to_{to_date}.xlsx"

    st.download_button(
        label="📥 Download Excel",
        data=output,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )



    # -------------------------
    # Display table (full width)
    # -------------------------
    st.markdown("### 📋 Workorder List")

    df = prepare_workorder_dataframe(rows)

    st.markdown(
        df.to_html(escape=False, index=False),
        unsafe_allow_html=True
    )
