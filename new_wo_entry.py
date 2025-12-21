# new_wo_entry.py
import streamlit as st
from datetime import date, timedelta
from database import run_query, fetch_employee_details

# Reuse TRUE IST time from attendance module
from attendance import get_current_ist


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def get_teamlead_center(user):
    emp = fetch_employee_details(user["employee_code"])
    return {
        "center_code": emp.get("center_code"),
        "center_name": emp.get("center_name"),
        "center_location": emp.get("center_location"),
    }


def get_technicians_by_center(center_code):
    sql = """
        SELECT employee_code, employee_name
        FROM employee_details
        WHERE center_code = :cc
          AND user_role = 'Technician'
          AND employee_status = 'Active'
        ORDER BY employee_name
    """
    return run_query(sql, {"cc": center_code}, fetch_one=False) or []


def get_vehicle_manufacturers():
    sql = "SELECT DISTINCT vehicle_manufacturer FROM vehicle_model ORDER BY vehicle_manufacturer"
    rows = run_query(sql, fetch_one=False)
    return [r["vehicle_manufacturer"] for r in rows] if rows else []


def get_vehicle_models(manufacturer):
    sql = """
        SELECT vehicle_model
        FROM vehicle_model
        WHERE vehicle_manufacturer = :vm
        ORDER BY vehicle_model
    """
    rows = run_query(sql, {"vm": manufacturer}, fetch_one=False)
    return [r["vehicle_model"] for r in rows] if rows else []


# ---------------------------------------------------------
# MAIN PAGE
# ---------------------------------------------------------
def new_workorder_entry_page():

    if "last_technician" not in st.session_state:
        st.session_state.last_technician = None


    if not st.session_state.get("logged_in"):
        st.warning("Please login first.")
        return

    user = st.session_state.get("user")
    if user.get("user_role") != "TeamLeader":
        st.error("Access denied.")
        return

    st.header("🛠️ Create or update workorder status")

    st.markdown(
    """
    <style>
    .block-container {
        max-width: 100% !important;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


    # Jobcard type
    jobcard_type = st.selectbox(
        "Select Jobcard Type",
        ["New Job", "Update Job Status", "Repeat Repair", "Re Visit"]
    )

    if jobcard_type != "New Job":
        st.info("This option will be enabled in the next phase.")
        return

    # -------------------------------------------------
    # New Job Form
    # -------------------------------------------------
    now_ist = get_current_ist()
    today = now_ist.date()

    center = get_teamlead_center(user)
    technicians = get_technicians_by_center(center["center_code"])

    if not technicians:
        st.warning("No technicians found for your center.")
        return

    tech_map = {
        f"{t['employee_code']} — {t['employee_name']}": t
        for t in technicians
    }

    with st.form("new_job_form", clear_on_submit=True):


        col1, col2 = st.columns([1, 1], gap="large")


        with col1:
            tech_sel = st.selectbox(
                "Technician",
                list(tech_map.keys()),
                 key="technician_select"
            )

           

            tech = tech_map[tech_sel]

            jobcard_photo = st.camera_input("Capture Jobcard Photo")

           
            vehicle_registration_no = st.text_input("Vehicle Registration No *")

            vehicle_manufacturer = st.selectbox(
                "Vehicle Manufacturer",
                get_vehicle_manufacturers()
            )

            vehicle_model = st.selectbox(
                "Vehicle Model",
                get_vehicle_models(vehicle_manufacturer)
            )

            vehicle_variant = st.text_input("Vehicle Variant")

        with col2:
            jobcard_no = st.text_input("Jobcard No")
            jobcard_date = st.date_input("Jobcard Date", value=today, max_value=today)
            if jobcard_date > today:
                st.error("Jobcard Date cannot be a future date.")
                return


            job_assign_date = st.date_input(
                "Job Assign Date",
                value=today,
                min_value=today - timedelta(days=10),
                max_value=today
            )

            kilometres = st.number_input("Kilometres", min_value=0)
            service_advisor = st.text_input("Name of Service Advisor")
            tl_remarks = st.text_area("TL Remarks")

        st.markdown("---")

        st.write("**Center Details (Auto)**")
        st.write(center)

        submitted = st.form_submit_button("✅ Submit New Job")

    # -------------------------------------------------
    # Submit Logic
    # -------------------------------------------------
    if submitted:

        if not jobcard_photo:
            st.error("Jobcard photo is mandatory. Please capture the photo.")
            return

        if not vehicle_registration_no:
            st.error("Vehicle Registration No is mandatory.")
            return

        if jobcard_date > today:
            st.error("Jobcard Date cannot be a future date.")
            return

        photo_bytes = jobcard_photo.getvalue()


        insert_sql = """
            INSERT INTO workorder_entry (
                jobcard_type,
                technician_code,
                name_of_technician,
                jobcard_photo,
                
                vehicle_registration_no,
                vehicle_manufacturer,
                vehicle_model,
                vehicle_variant,
                jobcard_no,
                jobcard_date,
                job_assign_date,
                kilometres,
                name_of_service_advisor,
                center_code,
                center_name,
                center_location,
                job_start_time,
                tl_id,
                tl_last_update,
                tl_remarks,
                job_status
            )
            VALUES (
                :jobcard_type,
                :technician_code,
                :name_of_technician,
                :jobcard_photo,
                
                :vehicle_registration_no,
                :vehicle_manufacturer,
                :vehicle_model,
                :vehicle_variant,
                :jobcard_no,
                :jobcard_date,
                :job_assign_date,
                :kilometres,
                :service_advisor,
                :center_code,
                :center_name,
                :center_location,
                :job_start_time,
                :tl_id,
                :tl_last_update,
                :tl_remarks,
                'In Progress'
            )
        """

        payload = {
            "jobcard_type": jobcard_type,
            "technician_code": tech["employee_code"],
            "name_of_technician": tech["employee_name"],
            "jobcard_photo": photo_bytes,
            
            "vehicle_registration_no": vehicle_registration_no,
            "vehicle_manufacturer": vehicle_manufacturer,
            "vehicle_model": vehicle_model,
            "vehicle_variant": vehicle_variant,
            "jobcard_no": jobcard_no,
            "jobcard_date": jobcard_date,
            "job_assign_date": job_assign_date,
            "kilometres": kilometres,
            "service_advisor": service_advisor,
            "center_code": center["center_code"],
            "center_name": center["center_name"],
            "center_location": center["center_location"],
            "job_start_time": now_ist,
            "tl_id": user["employee_code"],
            "tl_last_update": now_ist,
            "tl_remarks": tl_remarks,
        }

        run_query(insert_sql, payload)
        st.success("🎉 New workorder created successfully!")
