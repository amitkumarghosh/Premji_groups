import streamlit as st
from datetime import timedelta
from new_wo_entry import get_teamlead_center
from attendance import get_current_ist
from database import run_query
import base64
import pandas as pd

def prepare_workorder_dataframe(rows):
    """
    Converts jobcard_photo BLOB to clickable link.
    """
    df = pd.DataFrame(rows)

    if "Jobcard Photo" in df.columns:
        def make_link(blob):
            if blob is None:
                return ""
            try:
                b64 = base64.b64encode(blob).decode("utf-8")
                return f'<a href="data:image/png;base64,{b64}" target="_blank">View Photo</a>'
            except Exception:
                return ""

        df["Jobcard Photo"] = df["Jobcard Photo"].apply(make_link)

    return df



def view_workorders_page(user):

    st.header("📊 View Work Orders")

    now_ist = get_current_ist()
    today = now_ist.date()

    col1, col2 = st.columns(2)
    with col1:
        from_date = st.date_input(
            "From Date",
            value=today - timedelta(days=7),
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

    role = user.get("user_role")

    params = {
        "from_date": from_date,
        "to_date": to_date,
        "delete_flag": 0
    }

    # 🔐 Role-based query
    if role == "TeamLeader":
        center = get_teamlead_center(user)
        params["center_code"] = center["center_code"]

        sql = """
            SELECT
                id AS 'Search ID',
                jobcard_no As 'Jobcard No',
                jobcard_type As 'Jobcard Type',
                technician_code As 'Technician Code',
                name_of_technician As 'Name of Technician',
                jobcard_photo As 'Jobcard Photo',
                previous_jobcard_no As 'Previous Jobcard No',
                jobcard_type As 'Jobcard Type',
                job_status As 'Job Status',
                technician_code As 'Technician Code',
                name_of_technician As 'Name of Technician',
                job_assign_date As 'Job Assign Date',
                job_compleate_date As 'Job Complete Date',
                center_code as 'Center Code'
            FROM workorder_entry
            WHERE job_assign_date BETWEEN :from_date AND :to_date
              AND center_code = :center_code
            ORDER BY job_assign_date DESC
        """
    else:  # Admin / Super Admin
        sql = """
            SELECT
                id AS 'Search ID',
                jobcard_no As 'Jobcard No',
                jobcard_type As 'Jobcard Type',
                technician_code As 'Technician Code',
                name_of_technician As 'Name of Technician',
                jobcard_photo As 'Jobcard Photo',
                previous_jobcard_no As 'Previous Jobcard No',
                jobcard_type As 'Jobcard Type',
                job_status As 'Job Status',
                technician_code As 'Technician Code',
                name_of_technician As 'Name of Technician',
                job_assign_date As 'Job Assign Date',
                job_compleate_date As 'Job Complete Date',
                center_code as 'Center Code'
            FROM workorder_entry
            WHERE job_assign_date BETWEEN :from_date AND :to_date
            ORDER BY job_assign_date DESC
        """

    rows = run_query(sql, params, fetch_one=False)

    if not rows:
        st.info("No workorders found for the selected date range.")
        return

    st.markdown("### 📋 Workorder List")
    # st.dataframe(rows, use_container_width=True)

    df = prepare_workorder_dataframe(rows)

    st.markdown(
        df.to_html(escape=False, index=False),
        unsafe_allow_html=True
        )



