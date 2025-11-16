# admin.py
import streamlit as st
import pandas as pd
from datetime import date, datetime

from database import run_query, fetch_employee_details

# Configuration
USER_ROLE_OPTIONS_SUPER = ['Accounts', 'Admin', 'Engineer', 'Super Admin', 'TeamLeader', 'Technician']
USER_ROLE_OPTIONS_ADMIN = ['Accounts', 'Engineer', 'TeamLeader', 'Technician']
USER_DETAILS_OPTIONS = [
    'Disc & Drum R', 'Carbon Cl', 'Brake Testing', 'Wash-Cl & Poli',
    'Manager', 'Admin', 'Accounts', 'Engineer'
]
EMP_STATUS_OPTIONS = ['Active', 'Inactive']
CENTER_STATUS_OPTIONS = ['Active', 'Inactive']

# Helpers
def pd_to_date(val):
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return pd.to_datetime(val).date()
    except Exception:
        try:
            return datetime.fromisoformat(str(val)).date()
        except Exception:
            return None

def _get_center_info(center_code: str):
    if not center_code:
        return {"center_name": None, "center_location": None}
    row = run_query(
        "SELECT center_name, center_location FROM center_details WHERE center_code = :cc LIMIT 1",
        {"cc": center_code}, fetch_one=True
    )
    return dict(row) if row else {"center_name": None, "center_location": None}

def _list_centers():
    rows = run_query("SELECT * FROM center_details ORDER BY center_code", fetch_one=False)
    return rows or []

def _load_all_employees():
    rows = run_query("SELECT * FROM employee_details ORDER BY employee_code", fetch_one=False)
    return rows or []

def _create_employee(payload: dict):
    sql = """
        INSERT INTO employee_details
        (employee_code, employee_name, password, center_code, center_name, center_location,
         center_type, user_role, user_details, employee_doj, employee_status, last_working_day, Updated_By)
        VALUES
        (:employee_code, :employee_name, :password, :center_code, :center_name, :center_location,
         :center_type, :user_role, :user_details, :employee_doj, :employee_status, :last_working_day, :updated_by)
    """
    return run_query(sql, payload)

def _update_employee(payload: dict):
    sql = """
        UPDATE employee_details SET
            employee_code = :new_emp_code,
            employee_name = :employee_name,
            password = :password,
            center_code = :center_code,
            center_name = :center_name,
            center_location = :center_location,
            center_type = :center_type,
            user_role = :user_role,
            user_details = :user_details,
            employee_doj = :employee_doj,
            employee_status = :employee_status,
            last_working_day = :last_working_day,
            Updated_By = :updated_by
        WHERE employee_code = :orig_emp_code
    """
    return run_query(sql, payload)

def _create_center(payload: dict):
    sql = """
        INSERT INTO center_details (center_code, center_name, center_location, center_type, status)
        VALUES (:center_code, :center_name, :center_location, :center_type, :status)
    """
    return run_query(sql, payload)

def _update_center(payload: dict):
    sql = """
        UPDATE center_details SET
            center_code = :new_center_code,
            center_name = :center_name,
            center_location = :center_location,
            center_type = :center_type,
            status = :status
        WHERE center_code = :orig_center_code
    """
    return run_query(sql, payload)

# Manage Users: search/edit + create
def _manage_users_tab(current_user_code: str, current_user_role: str):
    st.header("Manage Users")

    # Show employee table to both Admin and Super Admin (so Super Admin sees it like Admin)
    st.subheader("All employees")
    rows = _load_all_employees()
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, width='stretch')
        st.download_button("Download employee_details as CSV", data=df.to_csv(index=False), file_name="employee_details.csv", mime="text/csv")
    else:
        st.info("No employee records found.")

    tabs = st.tabs(["Search / Edit user", "Add new user"])

    # Search / Edit
    with tabs[0]:
        st.subheader("Search & Edit user")
        if "admin_search_code" not in st.session_state:
            st.session_state["admin_search_code"] = ""

        search_input_val = st.text_input("Enter Employee Code (e.g. AL0001)",
                                         value=st.session_state.get("admin_search_code", ""),
                                         key="admin_search_textinput")
        if st.button("Search", key="admin_search_btn") and search_input_val.strip():
            st.session_state["admin_search_code"] = search_input_val.strip()

        if st.session_state.get("admin_search_code"):
            search_code = st.session_state["admin_search_code"].strip()

            minimal = run_query("SELECT employee_code, user_role FROM employee_details WHERE employee_code = :emp LIMIT 1",
                                {"emp": search_code}, fetch_one=True)
            if not minimal:
                st.error("No such employee.")
                st.session_state["admin_search_code"] = ""
                return

            target_emp = minimal.get("employee_code")
            target_role = (minimal.get("user_role") or "").strip()

            # Admin restriction: Admin cannot view Admin/Super Admin unless their own record
            if current_user_role == "Admin" and target_emp != current_user_code and target_role in ("Admin", "Super Admin"):
                st.error("Access restricted: Admins cannot view Admin or Super Admin records.")
                st.session_state["admin_search_code"] = ""
                return

            # Super Admin: no restriction here (they can view everything)
            row = fetch_employee_details(search_code)
            if not row:
                st.error("Failed to load user record.")
                st.session_state["admin_search_code"] = ""
                return

            user = dict(row)
            st.success(f"Found: {user.get('employee_name')} ({user.get('employee_code')})")

            orig_emp_code = user.get("employee_code")
            orig_center_type = user.get("center_type")
            orig_employee_doj = user.get("employee_doj")

            role_options = USER_ROLE_OPTIONS_SUPER if current_user_role == "Super Admin" else USER_ROLE_OPTIONS_ADMIN

            # st.markdown("**Current values (read-only)**")
            # st.json({
            #     "employee_code": user.get("employee_code"),
            #     "employee_name": user.get("employee_name"),
            #     "user_role": user.get("user_role"),
            #     "employee_status": user.get("employee_status"),
            #     "center_code": user.get("center_code"),
            #     "center_name": user.get("center_name"),
            #     "center_location": user.get("center_location"),
            # })

            st.markdown("---")
            st.markdown("**Edit user (leave blank text fields to keep existing)**")
            form_key = f"edit_user_form_{orig_emp_code}"
            with st.form(form_key):
                col1, col2 = st.columns(2)
                with col1:
                    employee_name = st.text_input("Employee Name", value=user.get("employee_name") or "", key=f"name_{orig_emp_code}")
                    employee_code = st.text_input("Employee Code (can update)", value=user.get("employee_code") or "", key=f"code_{orig_emp_code}")
                    password_input = st.text_input("Password (leave blank to keep existing)", value="", key=f"pass_{orig_emp_code}")
                    center_code = st.text_input("Center Code", value=user.get("center_code") or "", key=f"ccode_{orig_emp_code}")
                with col2:
                    center_info = _get_center_info(center_code) if center_code else {"center_name": user.get("center_name"), "center_location": user.get("center_location")}
                    st.text_input("Center Name (auto)", value=center_info.get("center_name") or user.get("center_name") or "", disabled=True)
                    st.text_input("Center Location (auto)", value=center_info.get("center_location") or user.get("center_location") or "", disabled=True)

                    user_role = st.selectbox("User Role", options=role_options,
                                             index=role_options.index(user.get("user_role")) if user.get("user_role") in role_options else 0)
                    user_details = st.selectbox("User Details", options=USER_DETAILS_OPTIONS,
                                                index=USER_DETAILS_OPTIONS.index(user.get("user_details")) if user.get("user_details") in USER_DETAILS_OPTIONS else 0)
                    employee_status = st.selectbox("Employee Status", options=EMP_STATUS_OPTIONS,
                                                   index=EMP_STATUS_OPTIONS.index(user.get("employee_status")) if user.get("employee_status") in EMP_STATUS_OPTIONS else 0)
                    st.text_input("Employee DOJ (readonly)", value=str(orig_employee_doj) if orig_employee_doj else "", disabled=True)
                    if employee_status == "Inactive":
                        default_last = pd_to_date(user.get("last_working_day")) or date.today()
                        last_working_day = st.date_input("Last working day", value=default_last)
                    else:
                        last_working_day = None

                submitted = st.form_submit_button("Save changes")
                if submitted:
                    new_password_candidate = (password_input or "").strip()
                    password_to_save = new_password_candidate if new_password_candidate != "" else user.get("password")

                    new_employee_name = (employee_name or "").strip() or user.get("employee_name")
                    new_employee_code = (employee_code or "").strip() or orig_emp_code
                    new_center_code = (center_code or "").strip() or user.get("center_code")

                    new_center_info = _get_center_info(new_center_code) if new_center_code else {"center_name": user.get("center_name"), "center_location": user.get("center_location")}
                    new_center_name = new_center_info.get("center_name") or user.get("center_name")
                    new_center_location = new_center_info.get("center_location") or user.get("center_location")

                    payload = {
                        "new_emp_code": new_employee_code,
                        "employee_name": new_employee_name,
                        "password": password_to_save,
                        "center_code": new_center_code,
                        "center_name": new_center_name,
                        "center_location": new_center_location,
                        "center_type": orig_center_type,
                        "user_role": user_role,
                        "user_details": user_details,
                        "employee_doj": orig_employee_doj,
                        "employee_status": employee_status,
                        "last_working_day": last_working_day.isoformat() if last_working_day else None,
                        "updated_by": current_user_code,
                        "orig_emp_code": orig_emp_code,
                    }

                    res = _update_employee(payload)
                    verify = run_query("SELECT * FROM employee_details WHERE employee_code = :emp", {"emp": payload["new_emp_code"]}, fetch_one=True)
                    if verify:
                        st.success("User updated successfully.")
                    else:
                        st.error("Update failed or did not persist. Check logs.")

    # Add new user
    with tabs[1]:
        st.subheader("Add new user")
        with st.form("create_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_employee_code = st.text_input("Employee Code (unique)")
                new_employee_name = st.text_input("Employee Name")
                new_password = st.text_input("Password", type="password")
                new_center_code = st.text_input("Center Code (optional)")
            with col2:
                center_info = _get_center_info(new_center_code) if new_center_code else {"center_name": None, "center_location": None}
                st.text_input("Center Name (auto)", value=center_info.get("center_name") or "", disabled=True)
                st.text_input("Center Location (auto)", value=center_info.get("center_location") or "", disabled=True)

                if current_user_role == "Super Admin":
                    new_role = st.selectbox("User Role", USER_ROLE_OPTIONS_SUPER)
                else:
                    new_role = st.selectbox("User Role", USER_ROLE_OPTIONS_ADMIN)
                new_user_details = st.selectbox("User Details", USER_DETAILS_OPTIONS)
                new_employee_status = st.selectbox("Employee Status", EMP_STATUS_OPTIONS)

            created = st.form_submit_button("Create user")
            if created:
                if not new_employee_code or not new_employee_name or not new_password:
                    st.error("Employee code, name and password are required.")
                else:
                    exists = run_query("SELECT 1 FROM employee_details WHERE employee_code = :emp LIMIT 1", {"emp": new_employee_code}, fetch_one=True)
                    if exists:
                        st.error("Employee code already exists.")
                    else:
                        payload = {
                            "employee_code": new_employee_code.strip(),
                            "employee_name": new_employee_name.strip(),
                            "password": new_password.strip(),
                            "center_code": new_center_code.strip() if new_center_code else None,
                            "center_name": center_info.get("center_name"),
                            "center_location": center_info.get("center_location"),
                            "center_type": None,
                            "user_role": new_role,
                            "user_details": new_user_details,
                            "employee_doj": None,
                            "employee_status": new_employee_status,
                            "last_working_day": None,
                            "updated_by": current_user_code,
                        }
                        r = _create_employee(payload)
                        verify = run_query("SELECT * FROM employee_details WHERE employee_code = :emp", {"emp": payload["employee_code"]}, fetch_one=True)
                        if verify:
                            st.success("User created successfully.")
                        else:
                            st.error("Failed to create user. Check DB and logs.")

# Manage centers tab
def _manage_centers_tab(current_user_code: str, current_user_role: str):
    st.header("Manage Centers")
    centers = _list_centers()
    df = pd.DataFrame(centers) if centers else pd.DataFrame(columns=["center_code", "center_name", "center_location", "center_type", "status"])
    st.subheader("Existing Centers")
    st.dataframe(df, width='stretch')

    tabs = st.tabs(["Add Center", "Edit Center"])
    # Add
    with tabs[0]:
        st.subheader("Add new center")
        with st.form("add_center_form"):
            center_code = st.text_input("Center Code (unique)")
            center_name = st.text_input("Center Name")
            center_location = st.text_input("Center Location")
            center_type = st.text_input("Center Type")
            status = st.selectbox("Status", options=CENTER_STATUS_OPTIONS, index=0)
            create = st.form_submit_button("Add center")
            if create:
                if not center_code or not center_name:
                    st.error("Center code and name are required.")
                else:
                    exists = run_query("SELECT 1 FROM center_details WHERE center_code = :cc LIMIT 1", {"cc": center_code}, fetch_one=True)
                    if exists:
                        st.error("Center code already exists.")
                    else:
                        payload = {
                            "center_code": center_code.strip(),
                            "center_name": center_name.strip(),
                            "center_location": center_location.strip() if center_location else None,
                            "center_type": center_type.strip() if center_type else None,
                            "status": status.strip() if status else None,
                        }
                        r = _create_center(payload)
                        verify = run_query("SELECT * FROM center_details WHERE center_code = :cc", {"cc": payload["center_code"]}, fetch_one=True)
                        if verify:
                            st.success("Center added successfully.")
                        else:
                            st.error("Failed to add center. Check DB.")

    # Edit
    with tabs[1]:
        st.subheader("Edit existing center")
        center_codes = [c["center_code"] for c in centers] if centers else []
        center_select = st.selectbox("Select center to edit", options=center_codes, index=0 if center_codes else None)
        if center_select:
            center_row = run_query("SELECT * FROM center_details WHERE center_code = :cc LIMIT 1", {"cc": center_select}, fetch_one=True)
            if center_row:
                center_row = dict(center_row)
                orig_center_code = center_row.get("center_code")
                with st.form(f"edit_center_form_{orig_center_code}"):
                    new_center_code = st.text_input("Center Code", value=center_row.get("center_code") or "")
                    new_center_name = st.text_input("Center Name", value=center_row.get("center_name") or "")
                    new_center_location = st.text_input("Center Location", value=center_row.get("center_location") or "")
                    new_center_type = st.text_input("Center Type", value=center_row.get("center_type") or "")
                    new_status = st.selectbox("Status", options=CENTER_STATUS_OPTIONS, index=CENTER_STATUS_OPTIONS.index(center_row.get("status")) if center_row.get("status") in CENTER_STATUS_OPTIONS else 0)
                    save = st.form_submit_button("Save center changes")
                    if save:
                        payload = {
                            "new_center_code": new_center_code.strip() or orig_center_code,
                            "center_name": new_center_name.strip() or center_row.get("center_name"),
                            "center_location": new_center_location.strip() or center_row.get("center_location"),
                            "center_type": new_center_type.strip() or center_row.get("center_type"),
                            "status": new_status.strip() or center_row.get("status"),
                            "orig_center_code": orig_center_code,
                        }
                        r = _update_center(payload)
                        verify = run_query("SELECT * FROM center_details WHERE center_code = :cc LIMIT 1", {"cc": payload["new_center_code"]}, fetch_one=True)
                        if verify:
                            st.success("Center updated successfully.")
                        else:
                            st.error("Failed to update center. Check DB.")

# Admin page entrypoint
def admin_page():
    if not st.session_state.get("logged_in"):
        st.warning("You must be logged in first.")
        return

    user = st.session_state.get("user") or {}
    current_user_code = user.get("employee_code")
    current_user_role = user.get("user_role")

    if current_user_role not in ("Admin", "Super Admin"):
        st.error("Access denied.")
        return

    st.title("Administration")
    st.markdown("---")

    rows = _load_all_employees()
    st.markdown(f"**Total employees:** {len(rows)}")
    st.markdown("---")

    main_tabs = st.tabs(["Manage Users", "Manage Centers"])
    with main_tabs[0]:
        _manage_users_tab(current_user_code, current_user_role)
    with main_tabs[1]:
        _manage_centers_tab(current_user_code, current_user_role)

if __name__ == "__main__":
    admin_page()
