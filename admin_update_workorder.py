import streamlit as st
from datetime import timedelta
from database import run_query
from attendance import get_current_ist
from new_wo_entry import (
    get_teamlead_center,
    get_technicians_by_center,
    get_vehicle_manufacturers,
    get_vehicle_models,
)
from new_wo_entry import get_workorder_details


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def get_editable_workorders():
    sql = """
        SELECT id, jobcard_no
        FROM workorder_entry
        WHERE delete_flag = 0
        ORDER BY id DESC
    """
    return run_query(sql, fetch_one=False) or []


def get_technician_map(center_code):
    technicians = get_technicians_by_center(center_code)
    return {
        f"{t['employee_code']} — {t['employee_name']}": t
        for t in technicians
    }


# ---------------------------------------------------------
# MAIN PAGE
# ---------------------------------------------------------

def admin_update_workorder_page(user):

    if user.get("user_role") not in ("Admin", "Super Admin"):
        st.error("Access denied.")
        return

    st.header("✏️ Update Workorder Status (Admin)")

    # -----------------------------------------------------
    # Select Workorder
    # -----------------------------------------------------
    workorders = get_editable_workorders()
    if not workorders:
        st.info("No workorders available.")
        return

    wo_map = {f"{r['id']} — {r['jobcard_no']}": r["id"] for r in workorders}
    selected = st.selectbox("Search Workorder by ID", list(wo_map.keys()))
    workorder_id = wo_map[selected]

    data = get_workorder_details(workorder_id)
    if not data:
        st.error("Unable to load workorder details.")
        return

    # -----------------------------------------------------
    # Delete / Edit Actions
    # -----------------------------------------------------
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🗑 Delete Record"):
            run_query(
                "UPDATE workorder_entry SET delete_flag = 1 WHERE id = :id",
                {"id": workorder_id},
            )
            st.success("Record deleted successfully.")
            st.rerun()

    with col2:
        edit_mode = st.button("✏️ Edit Record")

    # if not edit_mode:
    #     st.subheader("📄 Workorder Details (Read Only)")
    #     st.json(data)
    #     return

    # -----------------------------------------------------
    # Edit Form
    # -----------------------------------------------------
    st.markdown("---")
    st.subheader("📝 Edit Workorder")

    now_ist = get_current_ist()
    today = now_ist.date()

    center = {
        "center_code": data["center_code"],
        "center_name": data["center_name"],
        "center_location": data["center_location"],
    }

    tech_map = get_technician_map(center["center_code"])
    tech_keys = list(tech_map.keys())

    with st.form("edit_workorder_form"):

        col1, col2 = st.columns(2)

        with col1:
            jobcard_type = st.selectbox(
                "Jobcard Type",
                ["New workorder", "Repeat Repair", "Re Visit", "Re-assigned job"],
                index=["New workorder", "Repeat Repair", "Re Visit", "Re-assigned job"].index(
                    data["jobcard_type"]
                ),
            )

            tech_sel = st.selectbox(
                "Technician",
                tech_keys,
                index=tech_keys.index(
                    f"{data['technician_code']} — {data['name_of_technician']}"
                ),
            )

            tech = tech_map[tech_sel]

            st.text_input(
                "Name of Technician",
                value=tech["employee_name"],
                disabled=True,
            )

            jobcard_photo = st.camera_input("Update Jobcard Photo (Optional)")

            previous_jobcard_no = st.text_input(
                "Previous Jobcard No",
                value=data.get("previous_jobcard_no") or "",
                disabled=True,
            )

            vehicle_registration_no = st.text_input(
                "Vehicle Registration No",
                value=data["vehicle_registration_no"],
            )

            vehicle_manufacturer = st.selectbox(
                "Vehicle Manufacturer",
                get_vehicle_manufacturers(),
                index=get_vehicle_manufacturers().index(data["vehicle_manufacturer"]),
            )

            vehicle_model = st.selectbox(
                "Vehicle Model",
                get_vehicle_models(vehicle_manufacturer),
                index=get_vehicle_models(vehicle_manufacturer).index(data["vehicle_model"]),
            )

            vehicle_variant = st.text_input(
                "Vehicle Variant",
                value=data["vehicle_variant"],
            )

        with col2:
            jobcard_no = st.text_input(
                "Jobcard No",
                value=data["jobcard_no"],
            )

            jobcard_date = st.date_input(
                "Jobcard Date",
                value=data["jobcard_date"],
                max_value=today,
            )

            st.date_input(
                "Job Assign Date",
                value=data["job_assign_date"],
                disabled=True,
            )

            kilometres = st.number_input(
                "Kilometres",
                value=int(data["kilometres"] or 0),
                min_value=0,
            )

            service_advisor = st.text_input(
                "Name of Service Advisor",
                value=data["name_of_service_advisor"],
            )

            job_status = st.selectbox(
                "Job Status",
                ["In Progress", "Re-Assigned", "Closed"],
                index=["In Progress", "Re-Assigned", "Closed"].index(
                    data["job_status"]
                ),
            )

            admin_remarks = st.text_area(
                "Admin Remarks",
                value=data.get("admin_remarks") or "",
            )

        st.markdown("---")
        st.write("**Center Details (Auto)**")
        st.write(center)

        submit = st.form_submit_button("💾 Update Workorder")

    old_status = data["job_status"]
    new_status = job_status

    # ❌ Admin cannot set Re-Assigned or Closed/Completed
    if new_status in ("Re-Assigned", "Completed", "Closed"):
        if old_status != new_status:
            st.error("❌ Please ask the team leader to change this.")
            return


    # -----------------------------------------------------
    # Submit Logic
    # -----------------------------------------------------
    if submit:

        photo_bytes = (
            jobcard_photo.getvalue()
            if jobcard_photo
            else data["jobcard_photo"]
        )

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
            "kilometres": kilometres,
            "name_of_service_advisor": service_advisor,
            "job_status": job_status,
            "admin_id": user["employee_code"],
            "admin_remarks": admin_remarks,
            "admin_last_update_time": now_ist,
            "id": workorder_id,
        }

        # Auto completion timestamp
        if job_status == "Closed":
            payload["job_compleate_date"] = now_ist.date()
            payload["job_compleate_time"] = now_ist.time()

            completion_sql = """
                job_compleate_date = :job_compleate_date,
                job_compleate_time = :job_compleate_time,
            """
        else:
            completion_sql = ""

        sql = f"""
            UPDATE workorder_entry
            SET
                jobcard_type = :jobcard_type,
                technician_code = :technician_code,
                name_of_technician = :name_of_technician,
                jobcard_photo = :jobcard_photo,
                vehicle_registration_no = :vehicle_registration_no,
                vehicle_manufacturer = :vehicle_manufacturer,
                vehicle_model = :vehicle_model,
                vehicle_variant = :vehicle_variant,
                jobcard_no = :jobcard_no,
                jobcard_date = :jobcard_date,
                kilometres = :kilometres,
                name_of_service_advisor = :name_of_service_advisor,
                job_status = :job_status,
                admin_id = :admin_id,
                admin_remarks = :admin_remarks,
                admin_last_update_time = :admin_last_update_time,
                {completion_sql}
                tl_last_update = tl_last_update
            WHERE id = :id
        """

        run_query(sql, payload)
        st.success("✅ Workorder updated successfully.")
        st.rerun()
