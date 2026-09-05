import streamlit as st
from database import run_query
from attendance import get_current_ist
from new_wo_entry import (
    get_technicians_by_center,
    get_vehicle_manufacturers,
    get_vehicle_models,
    get_workorder_details,
)


# =========================================================
# HELPERS
# =========================================================

def get_editable_workorders():
    sql = """
        SELECT id, jobcard_no
        FROM workorder_entry
        WHERE delete_flag = 0
        ORDER BY id DESC
    """

    return run_query(
        sql,
        fetch_one=False
    ) or []


def get_technician_map(center_code):
    """
    Returns technicians indexed by employee_code.

    Example:

    {
        "AL003": {
            "employee_code": "AL003",
            "employee_name": "Rangaswamy C"
        },
        "AL005": {
            "employee_code": "AL005",
            "employee_name": "Nagraj Kobannanav"
        }
    }
    """

    technicians = get_technicians_by_center(center_code) or []

    tech_map = {}

    for t in technicians:

        employee_code = str(
            t.get("employee_code") or ""
        ).strip()

        employee_name = str(
            t.get("employee_name") or ""
        ).strip()

        if employee_code:
            tech_map[employee_code] = {
                "employee_code": employee_code,
                "employee_name": employee_name,
            }

    return tech_map


# =========================================================
# MAIN ADMIN PAGE
# =========================================================

def admin_update_workorder_page(user):

    # =====================================================
    # ACCESS CONTROL
    # =====================================================

    if user.get("user_role") not in (
        "Admin",
        "Super Admin"
    ):
        st.error("Access denied.")
        return


    st.header("✏️ Update Workorder Status (Admin)")


    # =====================================================
    # SELECT WORKORDER
    # =====================================================

    workorders = get_editable_workorders()

    if not workorders:
        st.info("No workorders available.")
        return


    wo_map = {
        f"{row['id']} — {row['jobcard_no']}": row["id"]
        for row in workorders
    }


    selected = st.selectbox(
        "Search Workorder by ID",
        list(wo_map.keys()),
        key="admin_workorder_select"
    )


    workorder_id = wo_map[selected]


    # =====================================================
    # LOAD WORKORDER DETAILS
    # =====================================================

    data = get_workorder_details(workorder_id)

    if not data:
        st.error("Unable to load workorder details.")
        return


    # =====================================================
    # DELETE / EDIT BUTTONS
    # =====================================================

    col1, col2 = st.columns(2)


    with col1:

        delete_clicked = st.button(
            "🗑 Delete Record",
            key="admin_delete_workorder"
        )


    with col2:

        st.button(
            "✏️ Edit Record",
            key="admin_edit_workorder"
        )


    # =====================================================
    # DELETE RECORD
    # =====================================================

    if delete_clicked:

        run_query(
            """
            UPDATE workorder_entry
            SET delete_flag = 1
            WHERE id = :id
            """,
            {
                "id": workorder_id
            }
        )

        st.success(
            "Record deleted successfully."
        )

        st.rerun()


    # =====================================================
    # CURRENT DATE / TIME
    # =====================================================

    now_ist = get_current_ist()
    today = now_ist.date()


    # =====================================================
    # CENTER DETAILS
    # =====================================================

    center_code = str(
        data.get("center_code") or ""
    ).strip()

    center_name = data.get(
        "center_name"
    )

    center_location = data.get(
        "center_location"
    )

    center = {
        "center_code": center_code,
        "center_name": center_name,
        "center_location": center_location,
    }


    # =====================================================
    # TECHNICIAN LIST
    # =====================================================

    tech_map = get_technician_map(
        center_code
    )


    # Existing technician stored in workorder
    current_technician_code = str(
        data.get("technician_code") or ""
    ).strip()

    current_technician_name = str(
        data.get("name_of_technician") or ""
    ).strip()


    # -----------------------------------------------------
    # If existing technician is not in master list,
    # temporarily add him/her.
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
            f"'{current_technician_code} — "
            f"{current_technician_name}' "
            "is not available in the current technician "
            "master list. The existing technician has "
            "been retained."
        )


    # -----------------------------------------------------
    # Stop if there is absolutely no technician
    # -----------------------------------------------------

    if not tech_map:

        st.error(
            f"No Technician / Engineer found for "
            f"center '{center_code}'."
        )

        return


    tech_codes = list(
        tech_map.keys()
    )


    # =====================================================
    # JOB CARD TYPE
    # =====================================================

    jobcard_types = [
        "New workorder",
        "Repeat Repair",
        "Re Visit",
        "Re-assigned job",
    ]


    current_jobcard_type = (
        data.get("jobcard_type")
    )


    if (
        current_jobcard_type
        and current_jobcard_type not in jobcard_types
    ):

        jobcard_types.insert(
            0,
            current_jobcard_type
        )


    # =====================================================
    # VEHICLE MANUFACTURER
    #
    # IMPORTANT:
    # This is OUTSIDE the form.
    #
    # Therefore changing manufacturer immediately
    # reruns Streamlit and refreshes the model list.
    # =====================================================

    manufacturers = (
        get_vehicle_manufacturers() or []
    )


    current_manufacturer = str(
        data.get("vehicle_manufacturer") or ""
    ).strip()


    if (
        current_manufacturer
        and current_manufacturer not in manufacturers
    ):

        manufacturers.insert(
            0,
            current_manufacturer
        )

        st.warning(
            f"⚠️ Existing vehicle manufacturer "
            f"'{current_manufacturer}' is not in "
            "the current master list. It has been retained."
        )


    if not manufacturers:

        st.error(
            "No vehicle manufacturers found "
            "in vehicle master."
        )

        return


    # -----------------------------------------------------
    # Session state key for manufacturer
    # -----------------------------------------------------

    manufacturer_key = (
        f"admin_manufacturer_{workorder_id}"
    )


    if manufacturer_key not in st.session_state:

        st.session_state[
            manufacturer_key
        ] = current_manufacturer


    # If database manufacturer is no longer valid,
    # use first available manufacturer.

    if (
        st.session_state[manufacturer_key]
        not in manufacturers
    ):

        st.session_state[
            manufacturer_key
        ] = manufacturers[0]


    # -----------------------------------------------------
    # Manufacturer dropdown
    # -----------------------------------------------------

    vehicle_manufacturer = st.selectbox(
        "Vehicle Manufacturer",
        manufacturers,
        key=manufacturer_key
    )


    # =====================================================
    # VEHICLE MODEL
    #
    # Depends on Vehicle Manufacturer
    # =====================================================

    models = (
        get_vehicle_models(
            vehicle_manufacturer
        ) or []
    )


    current_model = str(
        data.get("vehicle_model") or ""
    ).strip()


    # -----------------------------------------------------
    # Keep old model if it is not available
    # for the selected manufacturer.
    #
    # This is important for old records.
    # -----------------------------------------------------

    if (
        current_model
        and current_model not in models
        and vehicle_manufacturer == current_manufacturer
    ):

        models.insert(
            0,
            current_model
        )

        st.warning(
            f"⚠️ Existing vehicle model "
            f"'{current_model}' is not available "
            f"for '{vehicle_manufacturer}'. "
            "The existing model has been retained."
        )


    # -----------------------------------------------------
    # If manufacturer has no models
    # -----------------------------------------------------

    if not models:

        st.warning(
            f"No vehicle models found for "
            f"'{vehicle_manufacturer}'."
        )

        vehicle_model = None

    else:

        # -------------------------------------------------
        # Session state key for model
        # -------------------------------------------------

        model_key = (
            f"admin_model_{workorder_id}"
        )


        # First load
        if model_key not in st.session_state:

            if (
                vehicle_manufacturer
                == current_manufacturer
                and current_model
                and current_model in models
            ):

                st.session_state[
                    model_key
                ] = current_model

            else:

                st.session_state[
                    model_key
                ] = models[0]


        # -------------------------------------------------
        # If manufacturer changed and the old model
        # does not belong to the new manufacturer,
        # automatically select the first valid model.
        # -------------------------------------------------

        if (
            st.session_state[model_key]
            not in models
        ):

            st.session_state[
                model_key
            ] = models[0]


        vehicle_model = st.selectbox(
            "Vehicle Model",
            models,
            key=model_key
        )


    # =====================================================
    # EDIT FORM
    #
    # Manufacturer and Model are intentionally outside
    # this form so they can work as dependent dropdowns.
    # =====================================================

    st.markdown("---")
    st.subheader("📝 Edit Workorder")


    with st.form(
        "edit_workorder_form"
    ):

        col1, col2 = st.columns(2)


        # =================================================
        # LEFT COLUMN
        # =================================================

        with col1:

            # -------------------------------------------------
            # Jobcard Type
            # -------------------------------------------------

            jobcard_type = st.selectbox(
                "Jobcard Type",
                jobcard_types,
                index=(
                    jobcard_types.index(
                        current_jobcard_type
                    )
                    if current_jobcard_type
                    in jobcard_types
                    else 0
                )
            )


            # -------------------------------------------------
            # Technician
            # -------------------------------------------------

            tech_labels = []

            for code in tech_codes:

                technician = tech_map[code]

                label = (
                    f"{code} — "
                    f"{technician['employee_name']}"
                )

                tech_labels.append(label)


            # Current technician label

            current_tech_label = (
                f"{current_technician_code} — "
                f"{current_technician_name}"
            )


            if current_tech_label in tech_labels:

                technician_index = (
                    tech_labels.index(
                        current_tech_label
                    )
                )

            else:

                technician_index = 0


            tech_sel = st.selectbox(
                "Technician",
                tech_labels,
                index=technician_index
            )


            # Get selected technician code

            selected_tech_code = (
                tech_sel.split(" — ", 1)[0]
            )


            tech = tech_map[
                selected_tech_code
            ]


            # -------------------------------------------------
            # Technician Name
            # -------------------------------------------------

            st.text_input(
                "Name of Technician",
                value=tech["employee_name"],
                disabled=True
            )


            # -------------------------------------------------
            # Jobcard Photo
            # -------------------------------------------------

            jobcard_photo = st.camera_input(
                "Update Jobcard Photo (Optional)"
            )


            # -------------------------------------------------
            # Previous Jobcard No
            # -------------------------------------------------

            st.text_input(
                "Previous Jobcard No",
                value=(
                    data.get(
                        "previous_jobcard_no"
                    ) or ""
                ),
                disabled=True
            )


            # -------------------------------------------------
            # Vehicle Registration
            # -------------------------------------------------

            vehicle_registration_no = st.text_input(
                "Vehicle Registration No",
                value=(
                    data.get(
                        "vehicle_registration_no"
                    ) or ""
                )
            )


            # -------------------------------------------------
            # Vehicle Variant
            # -------------------------------------------------

            vehicle_variant = st.text_input(
                "Vehicle Variant",
                value=(
                    data.get(
                        "vehicle_variant"
                    ) or ""
                )
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
                value=(
                    data.get(
                        "jobcard_no"
                    ) or ""
                )
            )


            # -------------------------------------------------
            # Jobcard Date
            # -------------------------------------------------

            jobcard_date = st.date_input(
                "Jobcard Date",
                value=data.get(
                    "jobcard_date"
                ),
                max_value=today
            )


            # -------------------------------------------------
            # Job Assign Date
            # -------------------------------------------------

            st.date_input(
                "Job Assign Date",
                value=data.get(
                    "job_assign_date"
                ),
                disabled=True
            )


            # -------------------------------------------------
            # Kilometres
            # -------------------------------------------------

            kilometres = st.number_input(
                "Kilometres",
                value=int(
                    data.get(
                        "kilometres"
                    ) or 0
                ),
                min_value=0
            )


            # -------------------------------------------------
            # Service Advisor
            # -------------------------------------------------

            service_advisor = st.text_input(
                "Name of Service Advisor",
                value=(
                    data.get(
                        "name_of_service_advisor"
                    ) or ""
                )
            )


            # -------------------------------------------------
            # Job Status
            # -------------------------------------------------

            job_status_options = [
                "In Progress",
                "Re-Assigned",
                "Closed",
            ]


            current_job_status = (
                data.get("job_status")
            )


            if (
                current_job_status
                and current_job_status
                not in job_status_options
            ):

                job_status_options.insert(
                    0,
                    current_job_status
                )


            job_status = st.selectbox(
                "Job Status",
                job_status_options,
                index=(
                    job_status_options.index(
                        current_job_status
                    )
                    if current_job_status
                    in job_status_options
                    else 0
                )
            )


            # -------------------------------------------------
            # Admin Remarks
            # -------------------------------------------------

            admin_remarks = st.text_area(
                "Admin Remarks",
                value=(
                    data.get(
                        "admin_remarks"
                    ) or ""
                )
            )


        # =================================================
        # CENTER DETAILS
        # =================================================

        st.markdown("---")

        st.write(
            "**Center Details (Auto)**"
        )

        st.write(center)


        # =================================================
        # SUBMIT
        # =================================================

        submit = st.form_submit_button(
            "💾 Update Workorder"
        )


    # =====================================================
    # STATUS VALIDATION
    # =====================================================

    old_status = data.get(
        "job_status"
    )

    new_status = job_status


    # -----------------------------------------------------
    # Admin cannot change status from In Progress
    # to Re-Assigned or Closed.
    # -----------------------------------------------------

    if new_status in (
        "Re-Assigned",
        "Completed",
        "Closed",
    ):

        if old_status != new_status:

            st.error(
                "❌ Admin cannot change the "
                f"workorder to '{new_status}'. "
                "Please ask the Team Leader "
                "to change this status."
            )

            return


    # =====================================================
    # SUBMIT LOGIC
    # =====================================================

    if submit:

        # -------------------------------------------------
        # Validate Jobcard Date
        # -------------------------------------------------

        if jobcard_date > today:

            st.error(
                "❌ Jobcard Date cannot be "
                "a future date."
            )

            return


        # -------------------------------------------------
        # Photo
        # -------------------------------------------------

        if jobcard_photo:

            photo_bytes = (
                jobcard_photo.getvalue()
            )

        else:

            photo_bytes = data.get(
                "jobcard_photo"
            )


        # -------------------------------------------------
        # Payload
        # -------------------------------------------------

        payload = {

            "jobcard_type":
                jobcard_type,

            "technician_code":
                tech["employee_code"],

            "name_of_technician":
                tech["employee_name"],

            "jobcard_photo":
                photo_bytes,

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


        # =================================================
        # COMPLETION DATE / TIME
        # =================================================

        if job_status == "Closed":

            payload[
                "job_compleate_date"
            ] = now_ist.date()

            payload[
                "job_compleate_time"
            ] = now_ist.time()


            completion_sql = """
                job_compleate_date =
                    :job_compleate_date,

                job_compleate_time =
                    :job_compleate_time,
            """

        else:

            completion_sql = ""


        # =================================================
        # UPDATE SQL
        # =================================================

        sql = f"""
            UPDATE workorder_entry
            SET
                jobcard_type =
                    :jobcard_type,

                technician_code =
                    :technician_code,

                name_of_technician =
                    :name_of_technician,

                jobcard_photo =
                    :jobcard_photo,

                vehicle_registration_no =
                    :vehicle_registration_no,

                vehicle_manufacturer =
                    :vehicle_manufacturer,

                vehicle_model =
                    :vehicle_model,

                vehicle_variant =
                    :vehicle_variant,

                jobcard_no =
                    :jobcard_no,

                jobcard_date =
                    :jobcard_date,

                kilometres =
                    :kilometres,

                name_of_service_advisor =
                    :name_of_service_advisor,

                job_status =
                    :job_status,

                admin_id =
                    :admin_id,

                admin_remarks =
                    :admin_remarks,

                admin_last_update_time =
                    :admin_last_update_time,

                {completion_sql}

                tl_last_update =
                    tl_last_update

            WHERE id = :id
        """


        # =================================================
        # EXECUTE
        # =================================================

        run_query(
            sql,
            payload
        )


        st.success(
            "✅ Workorder updated successfully."
        )


        st.rerun()