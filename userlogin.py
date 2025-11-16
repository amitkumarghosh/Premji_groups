# userlogin.py
import streamlit as st
from database import run_query
from userinterface import user_interface
from PIL import Image

st.set_page_config(
    page_title="Premji Group",
    page_icon="🛠️",
    layout="centered"
)


def login_page():
    st.title("🔐 Premji group user login")

    user_id = st.text_input("User ID")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if not user_id or not password:
            st.warning("Please enter both User ID and Password.")
            return

        query = """
            SELECT employee_code, employee_name, user_role, employee_status
            FROM employee_details
            WHERE employee_code = :emp_code AND password = :password
        """
        user = run_query(query, {"emp_code": user_id, "password": password}, fetch_one=True)

        if user:
            # user is a dict
            status = (user.get("employee_status") or "").lower()
            if status == "active" or status == "1":
                st.session_state["user"] = user
                st.session_state["logged_in"] = True
                st.success(f"Welcome {user['employee_name']} 👋")
                st.rerun()  # forces immediate navigation to interface
            else:
                st.error("Your account is inactive.")
        else:
            st.error("Invalid credentials. Please try again.")


# Page routing logic
if "logged_in" in st.session_state and st.session_state["logged_in"]:
    user_interface()
else:
    login_page()
