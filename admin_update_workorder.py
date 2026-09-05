import streamlit as st
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
    """
    Create technician list using employee_code as the unique key.

    This is safer than using:
        employee_code + employee_name

    because the technician's name may change in the master table.
    """
    technicians = get_technicians_by_center(center_code) or []

    tech_map = {}

    for t in technicians:
        employee_code = str(t.get("employee_code") or "").strip()
        employee_name = str(t.get("employee_name") or "").strip()

        if employee_code:
            tech_map[employee_code] = t

    return tech_map


# ---------------------------------------------------------
# MAIN PAGE
# ---------------------------------------------------------

def admin_update_workorder_page(user):

    # -----------------------------------------------------
    # Access Control
    # -----------------------------------------------------
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

    wo_map = {
        f"{r['id']} — {r['jobcard_no']}": r["id"]
        for r in workorders
    }

    selected = st.selectbox(
        "Search Workorder by ID",
        list(wo_map.keys())
    )

    workorder_id = wo_map[selected]

    # -----------------------------------------------------
    # Load Workorder Details
    # -----------------------------------------------------
    data = get_workorder_details(workorder_id)

    if not data:
        st.error("Unable to load workorder details.")
        return

    # -----------------------------------------------------
    # Delete / Edit Actions
    # -----------------------------------------------------
    col1, col2 = st.columns(2)

    with col1:
        delete_clicked = st.button("🗑 Delete Record")

    with col2:
        edit_mode = st.button("✏️ Edit Record")

    # -----------------------------------------------------
    # Delete Record
    # -----------------------------------------------------
    if delete_clicked:

        run_query(
            """
            UPDATE workorder_entry
            SET delete_flag = 1
            WHERE id = :id
            """,
            {"id": workorder_id},
        )

        st.success("Record deleted successfully.")
        st.rerun()

    # -----------------------------------------------------
    # Edit Form
    # -----------------------------------------------------
    st.markdown("---")
    st.subheader("📝 Edit Workorder")

    now_ist = get_current_ist()
    today = now_ist.date()

    # -----------------------------------------------------
    # Center Details
    # -----------------------------------------------------
    center = {
        "center_code": data.get("center_code"),
        "center_name": data.get("center_name"),
        "center_location": data.get("center_location"),
    }

    # -----------------------------------------------------
    # Technician List
    # -----------------------------------------------------
    tech_map = get_technician_map(center["center_code"])
    

    # Existing technician from the workorder
    current_technician_code = str(
        data.get("technician_code") or ""
    ).strip()

    current_technician_name = str(
        data.get("name_of_technician") or ""
    ).strip()

    # -----------------------------------------------------
    # IMPORTANT:
    # If the old technician is not available in the current
    # technician master list, add the old technician temporarily.
    #
    # This prevents ValueError and also prevents the existing
    # technician from being accidentally changed.
    # -----------------------------------------------------
    if (
        current_technician_code
        and current_technician_code not in tech_map
    ):
        tech_map[current_technician_code] = {
            "employee_code": current_technician_code,
            "employee_name": current_technician_name,
        }

        st.warning(
            f"⚠️ The existing technician "
            f"'{current_technician_code} — {current_technician_name}' "
            "is not available in the current technician master list. "
            "The existing technician has been retained."
        )

    tech_codes = list(tech_map.keys())

    # -----------------------------------------------------
    # Jobcard Type Options
    # -----------------------------------------------------
    jobcard_types = [
        "New workorder",
        "Repeat Repair",
        "Re Visit",
        "Re-assigned job",
    ]

    current_jobcard_type = data.get("jobcard_type")

    # If old value is not in current options, keep it available
    if (
        current_jobcard_type
        and current_jobcard_type not in jobcard_types
    ):
        jobcard_types.insert(0, current_jobcard_type)

        st.warning(
            f"⚠️ Existing Jobcard Type "
            f"'{current_jobcard_type}' is not in the current options. "
            "It has been retained."
        )

    # -----------------------------------------------------
    # Vehicle Manufacturer List
    # -----------------------------------------------------
    manufacturers = get_vehicle_manufacturers() or []

    current_manufacturer = data.get("vehicle_manufacturer")

    # Keep old manufacturer if it no longer exists in master list
    if (
        current_manufacturer
        and current_manufacturer not in manufacturers
    ):
        manufacturers.insert(0, current_manufacturer)

        st.warning(
            f"⚠️ Existing vehicle manufacturer "
            f"'{current_manufacturer}' is not in the current master list. "
            "It has been retained."
        )

    # -----------------------------------------------------
    # Vehicle Model List
    # -----------------------------------------------------
    models = get_vehicle_models(current_manufacturer) or []

    current_model = data.get("vehicle_model")

    # Keep old model if it is still relevant to the current manufacturer
    if current_model and current_model not in models:
        models.insert(0, current_model)

        st.warning(
            f"⚠️ Existing vehicle model "
            f"'{current_model}' is not available for "
            f"'{current_manufacturer}'. It has been retained."
        )

    # -----------------------------------------------------
    # FORM
    # -----------------------------------------------------
    with st.form("edit_workorder_form"):

        col1, col2 = st.columns(2)

        # =================================================
        # LEFT COLUMN
        # =================================================
        with col1:

                jobcard_type = st.selectbox(
                    "Jobcard Type",
                    [
                        "New workorder",
                        "Repeat Repair",
                        "Re Visit",
                        "Re-assigned job"
                    ],
                    index=[
                        "New workorder",
                        "Repeat Repair",
                        "Re Visit",
                        "Re-assigned job"
                    ].index(data["jobcard_type"]),
                )

                tech_sel = st.selectbox(
                    "Technician",
                    tech_keys,
                    index=tech_keys.index(
                        f"{data['technician_code']} — "
                        f"{data['name_of_technician']}"
                    ),
                )

                tech = tech_map[tech_sel]

                st.text_input(
                    "Name of Technician",
                    value=tech["employee_name"],
                    disabled=True,
                )

                jobcard_photo = st.camera_input(
                    "Update Jobcard Photo (Optional)"
                )

                previous_jobcard_no = st.text_input(
                    "Previous Jobcard No",
                    value=data.get("previous_jobcard_no") or "",
                    disabled=True,
                )

                vehicle_registration_no = st.text_input(
                    "Vehicle Registration No",
                    value=data["vehicle_registration_no"],
                )

                # -------------------------------------------------
                # Vehicle Manufacturer
                # -------------------------------------------------

                manufacturers = get_vehicle_manufacturers()

                current_manufacturer = (
                    data.get("vehicle_manufacturer") or ""
                )

                if not manufacturers:
                    st.error(
                        "No vehicle manufacturers found in vehicle master."
                    )
                    st.stop()

                # Keep old manufacturer if it is no longer in master
                if current_manufacturer not in manufacturers:
                    manufacturers = [
                        current_manufacturer
                    ] + manufacturers

                vehicle_manufacturer = st.selectbox(
                    "Vehicle Manufacturer",
                    manufacturers,
                    index=manufacturers.index(current_manufacturer),
                )

                # -------------------------------------------------
                # Vehicle Model
                # Depends on Vehicle Manufacturer
                # -------------------------------------------------

                models = get_vehicle_models(vehicle_manufacturer)

                current_model = data.get("vehicle_model") or ""

                if not models:

                    st.warning(
                        f"No vehicle models found for "
                        f"'{vehicle_manufacturer}'."
                    )

                    vehicle_model = st.text_input(
                        "Vehicle Model",
                        value=current_model,
                    )

                else:

                    # Keep old model if it is not available anymore
                    if current_model and current_model not in models:

                        models = [current_model] + models

                        st.warning(
                            f"The existing vehicle model "
                            f"'{current_model}' is not available "
                            f"for '{vehicle_manufacturer}'. "
                            f"The existing model has been retained."
                        )

                    vehicle_model = st.selectbox(
                        "Vehicle Model",
                        models,
                        index=(
                            models.index(current_model)
                            if current_model in models
                            else 0
                        ),
                    )

                vehicle_variant = st.text_input(
                    "Vehicle Variant",
                    value=data["vehicle_variant"],
                )        
        # =================================================
        # RIGHT COLUMN
        # =================================================
        with col2:

            # -------------------------------------------------
            # Jobcard No
            # -------------------------------------------------
            jobcard_no = st.text_input(
                "Jobcard No",
                value=data.get("jobcard_no") or "",
            )

            # -------------------------------------------------
            # Jobcard Date
            # -------------------------------------------------
            jobcard_date = st.date_input(
                "Jobcard Date",
                value=data.get("jobcard_date"),
                max_value=today,
            )

            # -------------------------------------------------
            # Job Assign Date
            # -------------------------------------------------
            st.date_input(
                "Job Assign Date",
                value=data.get("job_assign_date"),
                disabled=True,
            )

            # -------------------------------------------------
            # Kilometres
            # -------------------------------------------------
            kilometres = st.number_input(
                "Kilometres",
                value=int(data.get("kilometres") or 0),
                min_value=0,
            )

            # -------------------------------------------------
            # Service Advisor
            # -------------------------------------------------
            service_advisor = st.text_input(
                "Name of Service Advisor",
                value=data.get("name_of_service_advisor") or "",
            )

            # -------------------------------------------------
            # Job Status
            # -------------------------------------------------
            job_status_options = [
                "In Progress",
                "Re-Assigned",
                "Closed",
            ]

            current_job_status = data.get("job_status")

            # If database contains another status, keep it
            if (
                current_job_status
                and current_job_status not in job_status_options
            ):
                job_status_options.insert(
                    0,
                    current_job_status
                )

            job_status = st.selectbox(
                "Job Status",
                job_status_options,
                index=job_status_options.index(
                    current_job_status
                )
                if current_job_status in job_status_options
                else 0,
            )

            # -------------------------------------------------
            # Admin Remarks
            # -------------------------------------------------
            admin_remarks = st.text_area(
                "Admin Remarks",
                value=data.get("admin_remarks") or "",
            )

        # -----------------------------------------------------
        # Center Details
        # -----------------------------------------------------
        st.markdown("---")
        st.write("**Center Details (Auto)**")
        st.write(center)

        # -----------------------------------------------------
        # SUBMIT BUTTON
        # -----------------------------------------------------
        submit = st.form_submit_button(
            "💾 Update Workorder"
        )

    # =========================================================
    # STATUS VALIDATION
    # =========================================================

    old_status = data.get("job_status")
    new_status = job_status

    # Admin cannot change the status to Re-Assigned or Closed
    # if it is currently different.
    if new_status in (
        "Re-Assigned",
        "Completed",
        "Closed",
    ):

        if old_status != new_status:

            st.error(
                "❌ Admin cannot change the workorder to "
                f"'{new_status}'. "
                "Please ask the Team Leader to change this status."
            )

            return

    # =========================================================
    # SUBMIT LOGIC
    # =========================================================

    if submit:

        # -----------------------------------------------------
        # Photo
        # -----------------------------------------------------
        if jobcard_photo:
            photo_bytes = jobcard_photo.getvalue()
        else:
            photo_bytes = data.get("jobcard_photo")

        # -----------------------------------------------------
        # Payload
        # -----------------------------------------------------
        payload = {
            "jobcard_type": jobcard_type,

            "technician_code": tech.get(
                "employee_code"
            ),

            "name_of_technician": tech.get(
                "employee_name"
            ),

            "jobcard_photo": photo_bytes,

            "vehicle_registration_no":
                vehicle_registration_no,

            "vehicle_manufacturer":
                vehicle_manufacturer,

            "vehicle_model":
                vehicle_model,

            "vehicle_variant":
                vehicle_variant,

            "jobcard_no":
                jobcard_no,

            "jobcard_date":
                jobcard_date,

            "kilometres":
                kilometres,

            "name_of_service_advisor":
                service_advisor,

            "job_status":
                job_status,

            "admin_id":
                user["employee_code"],

            "admin_remarks":
                admin_remarks,

            "admin_last_update_time":
                now_ist,

            "id":
                workorder_id,
        }

        # -----------------------------------------------------
        # Completion Date / Time
        # -----------------------------------------------------
        if job_status == "Closed":

            payload["job_compleate_date"] = (
                now_ist.date()
            )

            payload["job_compleate_time"] = (
                now_ist.time()
            )

            completion_sql = """
                job_compleate_date = :job_compleate_date,
                job_compleate_time = :job_compleate_time,
            """

        else:

            completion_sql = ""

        # -----------------------------------------------------
        # UPDATE SQL
        # -----------------------------------------------------
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

        # -----------------------------------------------------
        # Execute Update
        # -----------------------------------------------------
        run_query(sql, payload)

        st.success(
            "✅ Workorder updated successfully."
        )

        st.rerun()