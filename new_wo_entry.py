# new_wo_entry.py
import streamlit as st
from datetime import timedelta,datetime
from database import run_query, fetch_employee_details
from zoneinfo import ZoneInfo
# Reuse TRUE IST time from attendance module
from attendance import get_current_ist

def get_current_ist():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


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
          AND user_role = 'Technician' OR user_role = 'Engineer'
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


def get_open_jobcards(center_code):
    sql = """
        SELECT id, jobcard_no
        FROM workorder_entry
        WHERE job_status = 'In Progress'
          AND center_code = :cc
        ORDER BY jobcard_no
    """
    return run_query(sql, {"cc": center_code}, fetch_one=False) or []


def get_workorder_details(workorder_id):
    sql = "SELECT * FROM workorder_entry WHERE id = :id"
    return run_query(sql, {"id": workorder_id}, fetch_one=True)
# ---------------------------------------------------------
    # Check for new workorder
    # ---------------------------------------------------------
def check_open_workorder_exists(jobcard_no, center_code):
    sql = """
        SELECT 1
        FROM workorder_entry
        WHERE jobcard_no = :jobcard_no
          AND center_code = :center_code
          AND job_status = 'In Progress'
        LIMIT 1
    """
    return run_query(
        sql,
        {"jobcard_no": jobcard_no, "center_code": center_code},
        fetch_one=True
    ) is not None

def get_recent_closed_jobcards(center_code, from_date):
    sql = """
        SELECT id, jobcard_no
        FROM workorder_entry
        WHERE job_status = 'Closed'
          AND center_code = :cc
          AND jobcard_date >= :from_date
          AND jobcard_photo IS NOT NULL
        ORDER BY jobcard_date DESC
    """
    return run_query(
        sql,
        {"cc": center_code, "from_date": from_date},
        fetch_one=False
    ) or []

    # ---------------------------------------------------------
    # Check for reassign workorder
    # ---------------------------------------------------------
def check_other_open_workorder_exists(jobcard_no, center_code, exclude_id):
    sql = """
        SELECT 1
        FROM workorder_entry
        WHERE jobcard_no = :jobcard_no
          AND center_code = :center_code
          AND job_status = 'In Progress'
          AND id <> :exclude_id
        LIMIT 1
    """
    return run_query(
        sql,
        {
            "jobcard_no": jobcard_no,
            "center_code": center_code,
            "exclude_id": exclude_id,
        },
        fetch_one=True
    ) is not None


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
        ["New workorder", "Re-assign workorder", "Repeat Repair", "Re Visit","Close workorder"]
    )

    if jobcard_type == "New workorder":
        pass
    elif jobcard_type == "Close workorder":
        close_workorder_ui(user)
        return
    elif jobcard_type == "Re-assign workorder":
        reassign_workorder_ui(user)
        return
    elif jobcard_type in ("Repeat Repair", "Re Visit"):
        repeat_revisit_ui(user, jobcard_type)
        return
    else:
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
            jobcard_date = st.date_input("Jobcard Date", value=today, min_value=today - timedelta(days=10), max_value=today)
            if jobcard_date > today:
                st.error("Jobcard Date cannot be a future date.")
                return


            job_assign_date = now_ist.date(),   # ✅ Asia/Kolkata date
            # st.date_input("Job Assign Date",value=today)
            

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

        # 🚫 Prevent duplicate in-progress workorder
        exists = check_open_workorder_exists(
            jobcard_no=jobcard_no,
            center_code=center["center_code"]
        )

        if exists:
            st.error(
                f"❌ Workorder '{jobcard_no}' already exists and is still In Progress. "
                "Please close or re-assign the existing workorder."
            )
            return

        if not jobcard_photo:
            st.error("Jobcard photo is mandatory. Please capture the photo.")
            return

        if not vehicle_registration_no:
            st.error("Vehicle Registration No is mandatory.")
            return

        if jobcard_date > today:
            st.error("Jobcard Date cannot be a future date.")
            return
        
        # if job_assign_date < jobcard_date:
        #         st.error("Job Assign Date cannot be before Jobcard Date.")
        #         return

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

#=====================================================
#Workorder close UI
#=====================================================
def close_workorder_ui(user):

    st.subheader("🔒 Close Workorder")

    now_ist = get_current_ist()
    center = get_teamlead_center(user)

    open_jobs = get_open_jobcards(center["center_code"])
    if not open_jobs:
        st.info("No open workorders found for your center.")
        return

    job_map = {j["jobcard_no"]: j["id"] for j in open_jobs}

    selected_jobcard = st.selectbox(
        "Select Open Jobcard Number",
        options=list(job_map.keys())
    )

    workorder_id = job_map[selected_jobcard]
    data = get_workorder_details(workorder_id)

    if not data:
        st.error("Failed to load workorder details.")
        return

    st.markdown("### 📄 Workorder Details (Read Only)")

    col1, col2 = st.columns([1, 2])

    with col1:
        if data.get("jobcard_photo"):
            import base64
            img_b64 = base64.b64encode(data["jobcard_photo"]).decode()
            st.markdown(
                f"""
                <a href="data:image/png;base64,{img_b64}" target="_blank">
                    <img src="data:image/png;base64,{img_b64}"
                         style="max-width:180px;border-radius:6px;cursor:pointer;" />
                </a>
                """,
                unsafe_allow_html=True
            )

    with col2:
        st.write({
            "Jobcard No": data["jobcard_no"],
            "Technician": data["name_of_technician"],
            "Vehicle Reg No": data["vehicle_registration_no"],
            "Manufacturer": data["vehicle_manufacturer"],
            "Model": data["vehicle_model"],
            "Variant": data["vehicle_variant"],
            "Kilometres": data["kilometres"],
            "Service Advisor": data["name_of_service_advisor"],
        })

    st.markdown("### 🔧 Services Performed (Enter Numbers)")

    with st.form("close_workorder_form"):

        services = {
            "wheel_alignment": "Wheel Alignment",
            "wheel_balancing": "Wheel Balancing",
            "tyre_fitting": "Tyre Fitting",
            "puncture_removed": "Puncture Removed",
            "tyre_pressuring_monitoring_system": "TPMS",
            "disc_cutting": "Disc Cutting",
            "drum_cutting": "Drum Cutting",
            "brake_testing": "Brake Testing",
            "carbon_cleaning_decarb": "Carbon Cleaning (Decarb)",
            "washing_and_cleaning": "Washing & Cleaning",
            "interior_cleaning": "Interior Cleaning",
            "exterior_polising": "Exterior Polishing",
            "paint_protection_film": "Paint Protection Film",
        }

        updated_services = {}
        cols = st.columns(3)

        for idx, (db_col, label) in enumerate(services.items()):
            with cols[idx % 3]:
                updated_services[db_col] = st.number_input(
                    label,
                    min_value=0,
                    step=1,
                    value=int(data.get(db_col) or 0)
                )

        submit_close = st.form_submit_button("✅ Close Workorder")


    if submit_close:

        set_clause = ", ".join([f"{k} = :{k}" for k in updated_services.keys()])

        sql = f"""
            UPDATE workorder_entry
            SET
                {set_clause},
                job_status = 'Closed',
                job_compleate_date = :job_compleate_date,
                job_compleate_time = :job_compleate_time,
                tl_last_update = :tl_last_update
            WHERE id = :id
        """

        now_ist = get_current_ist()

        payload = {
            **updated_services,
            "job_compleate_date": now_ist.date(),   # ✅ Asia/Kolkata date
            "job_compleate_time": now_ist.time(),   # ✅ Asia/Kolkata time
            "tl_last_update": now_ist,
            "id": workorder_id
        }


        run_query(sql, payload)
        st.success("🎉 Workorder closed successfully!")

#=====================================================
#Workorder re-assign UI
#=====================================================
def reassign_workorder_ui(user):

    st.subheader("🔁 Re-assign Workorder")

    now_ist = get_current_ist()
    today = now_ist.date()
    center = get_teamlead_center(user)

    # 🔁 Reuse existing helper
    open_jobs = get_open_jobcards(center["center_code"])
    if not open_jobs:
        st.info("No in-progress workorders found for your center.")
        return

    job_map = {j["jobcard_no"]: j["id"] for j in open_jobs}

    selected_jobcard = st.selectbox(
        "Select In-Progress Jobcard Number",
        list(job_map.keys())
    )

    workorder_id = job_map[selected_jobcard]

    # 🔁 Reuse existing helper
    data = get_workorder_details(workorder_id)
    if not data:
        st.error("Failed to load workorder details.")
        return

    technicians = get_technicians_by_center(center["center_code"])
    tech_map = {
        f"{t['employee_code']} — {t['employee_name']}": t
        for t in technicians
    }

    st.markdown("### 📄 Existing Workorder (Read Only)")

    col1, col2 = st.columns([1, 2])

    with col1:
        if data.get("jobcard_photo"):
            import base64
            img_b64 = base64.b64encode(data["jobcard_photo"]).decode()
            st.markdown(
                f"""
                <a href="data:image/png;base64,{img_b64}" target="_blank">
                    <img src="data:image/png;base64,{img_b64}"
                         style="max-width:180px;border-radius:6px;cursor:pointer;" />
                </a>
                """,
                unsafe_allow_html=True
            )

    with col2:
        st.write({
            "Jobcard No": data["jobcard_no"],
            "Vehicle Reg No": data["vehicle_registration_no"],
            "Manufacturer": data["vehicle_manufacturer"],
            "Model": data["vehicle_model"],
            "Variant": data["vehicle_variant"],
            "Kilometres": data["kilometres"],
            "Current Technician": data["name_of_technician"],
        })

    st.markdown("---")
    st.markdown("### ✏️ Re-assignment Details")

    with st.form("reassign_workorder_form"):

        new_technician = st.selectbox(
            "Re-assign To Technician",
            list(tech_map.keys())
        )

        new_assign_date = st.date_input(
            "Job Assign Date",
            value=today,
            min_value=today - timedelta(days=10),
            max_value=today
        )

        new_tl_remarks = st.text_area(
            "TL Remarks",
            value=data.get("tl_remarks") or ""
        )

        submit_reassign = st.form_submit_button("🔁 Re-assign")

    if submit_reassign:

        tech = tech_map[new_technician]

        # 1️⃣ Update OLD record
        run_query(
            """
            UPDATE workorder_entry
            SET
                job_status = 'Re-assigned',
                tl_remarks = :remarks,
                tl_last_update = :ts
            WHERE id = :id
            """,
            {
                "remarks": new_tl_remarks,
                "ts": now_ist,
                "id": workorder_id,
            }
        )

        # 2️⃣ Insert NEW record
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
                'Re-assigned job',
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
            "technician_code": tech["employee_code"],
            "name_of_technician": tech["employee_name"],
            "jobcard_photo": data["jobcard_photo"],
            "vehicle_registration_no": data["vehicle_registration_no"],
            "vehicle_manufacturer": data["vehicle_manufacturer"],
            "vehicle_model": data["vehicle_model"],
            "vehicle_variant": data["vehicle_variant"],
            "jobcard_no": data["jobcard_no"],
            "jobcard_date": data["jobcard_date"],
            "job_assign_date": new_assign_date,
            "kilometres": data["kilometres"],
            "service_advisor": data["name_of_service_advisor"],
            "center_code": center["center_code"],
            "center_name": center["center_name"],
            "center_location": center["center_location"],
            "job_start_time": now_ist,
            "tl_id": user["employee_code"],
            "tl_last_update": now_ist,
            "tl_remarks": new_tl_remarks,
        }

        run_query(insert_sql, payload)
        st.success("✅ Workorder re-assigned successfully!")
#=====================================================
#Reapet Or Revisit UI
#=====================================================
def repeat_revisit_ui(user, jobcard_type):

    st.subheader(f"🔁 {jobcard_type}")

    now_ist = get_current_ist()
    today = now_ist.date()
    from_date = today - timedelta(days=30)
    center = get_teamlead_center(user)

    # ✅ Closed jobs from last 30 days
    closed_jobs = get_recent_closed_jobcards(center["center_code"], from_date)
    if not closed_jobs:
        st.info("No eligible closed workorders found (last 30 days).")
        return

    job_map = {j["jobcard_no"]: j["id"] for j in closed_jobs}

    selected_jobcard = st.selectbox(
        "Select Closed Jobcard Number",
        list(job_map.keys())
    )

    workorder_id = job_map[selected_jobcard]
    data = get_workorder_details(workorder_id)

    if not data:
        st.error("Failed to load workorder details.")
        return
    
    # 🚫 BLOCK repeat/revisit if another active workorder exists
    active_exists = check_open_workorder_exists(
        jobcard_no=data["jobcard_no"],
        center_code=center["center_code"]
    )

    if active_exists:
        st.error(
            "❌ The existing workorder is yet not closed. "
            "Please close the active workorder before creating Repeat Repair / Re Visit."
        )
        return


    technicians = get_technicians_by_center(center["center_code"])
    tech_map = {
        f"{t['employee_code']} — {t['employee_name']}": t
        for t in technicians
    }

    # ---------- Read-only details ----------
    st.markdown("### 📄 Previous Workorder (Read Only)")

    col1, col2 = st.columns([1, 2])
    with col1:
        import base64
        img = base64.b64encode(data["jobcard_photo"]).decode()
        st.markdown(
            f"""
            <a href="data:image/png;base64,{img}" target="_blank">
                <img src="data:image/png;base64,{img}"
                     style="max-width:180px;border-radius:6px;cursor:pointer;" />
            </a>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.write({
            "Jobcard No": data["jobcard_no"],
            "Vehicle Reg No": data["vehicle_registration_no"],
            "Manufacturer": data["vehicle_manufacturer"],
            "Model": data["vehicle_model"],
            "Variant": data["vehicle_variant"],
            "Kilometres": data["kilometres"],
        })

    st.markdown("---")
    st.markdown("### ✏️ New Assignment Details")

    with st.form("repeat_revisit_form"):

        new_technician = st.selectbox(
            "Assign Technician",
            list(tech_map.keys())
        )

        new_assign_date = st.date_input(
            "Job Assign Date",
            value=today,
            min_value=today - timedelta(days=10),
            max_value=today
        )

        new_jobcard_no = st.text_input(
        "New Jobcard No *",
        help="Must be different from previous jobcard number"
        )


        tl_remarks = st.text_area("TL Remarks")

        submit = st.form_submit_button(f"➕ Create {jobcard_type}")

    if submit:

        tech = tech_map[new_technician]

        # ❌ Validation: new jobcard no must be entered
        if not new_jobcard_no:
            st.error("New Jobcard No is mandatory.")
            return

        # ❌ Validation: new jobcard no cannot be same as previous
        if new_jobcard_no == data["jobcard_no"]:
            st.error("New Jobcard No cannot be same as previous jobcard number.")
            return


        insert_sql = """
            INSERT INTO workorder_entry (
                jobcard_type,
                technician_code,
                name_of_technician,
                jobcard_photo,
                previous_jobcard_no,
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
                :previous_jobcard_no,
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
            "jobcard_type": jobcard_type,                # Repeat Repair / Re Visit
            "technician_code": tech["employee_code"],
            "name_of_technician": tech["employee_name"],
            "jobcard_photo": data["jobcard_photo"],

            # ✅ OLD jobcard stored here
            "previous_jobcard_no": data["jobcard_no"],

            # ✅ NEW jobcard number
            "jobcard_no": new_jobcard_no,

            "vehicle_registration_no": data["vehicle_registration_no"],
            "vehicle_manufacturer": data["vehicle_manufacturer"],
            "vehicle_model": data["vehicle_model"],
            "vehicle_variant": data["vehicle_variant"],
            "jobcard_date": today,
            "job_assign_date": new_assign_date,
            "kilometres": data["kilometres"],
            "service_advisor": data["name_of_service_advisor"],
            "center_code": center["center_code"],
            "center_name": center["center_name"],
            "center_location": center["center_location"],
            "job_start_time": now_ist,
            "tl_id": user["employee_code"],
            "tl_last_update": now_ist,
            "tl_remarks": tl_remarks,
        }


        run_query(insert_sql, payload)
        st.success(f"✅ {jobcard_type} workorder created successfully!")
#=====================================================