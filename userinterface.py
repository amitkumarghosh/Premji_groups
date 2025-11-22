# userinterface.py
import streamlit as st
from attendance import attendance_page

# try to import teamlead and admin pages if present
try:
    from teamlead import main as teamlead_page
except Exception:
    teamlead_page = None

try:
    from admin import admin_page
except Exception:
    admin_page = None

from PIL import Image
import os
from io import BytesIO

# Try to use project-level database helper if available
try:
    from database import fetch_employee_details
    DATABASE_HELPER_AVAILABLE = True
except Exception:
    DATABASE_HELPER_AVAILABLE = False

# near other imports
try:
    from admin_attendance import admin_attendance_page
except Exception as e:
    admin_attendance_page = None
    import streamlit as st
    st.error("Error importing admin_attendance:")
    st.exception(e)



# If no database helper, provide a safe fallback (MySQL via st.secrets or sqlite file)
if not DATABASE_HELPER_AVAILABLE:
    try:
        import mysql.connector
        MYSQL_AVAILABLE = True
    except Exception:
        MYSQL_AVAILABLE = False

    import sqlite3
    DB_PATH = "Tools_And_Tools.sqlite"

    def get_mysql_connection():
        if not MYSQL_AVAILABLE:
            return None
        creds = st.secrets.get("mysql") if "mysql" in st.secrets else {
            "host": os.environ.get("MYSQL_HOST"),
            "port": int(os.environ.get("MYSQL_PORT", 3306)) if os.environ.get("MYSQL_PORT") else 3306,
            "user": os.environ.get("MYSQL_USER"),
            "password": os.environ.get("MYSQL_PASSWORD"),
            "database": os.environ.get("MYSQL_DATABASE"),
        }
        if not creds or not creds.get("host") or not creds.get("user") or not creds.get("database"):
            return None
        try:
            conn = mysql.connector.connect(
                host=creds.get("host"),
                port=creds.get("port", 3306),
                user=creds.get("user"),
                password=creds.get("password"),
                database=creds.get("database"),
                autocommit=True,
            )
            return conn
        except Exception as e:
            st.error(f"Could not connect to MySQL: {e}")
            return None

    def get_sqlite_connection(path=DB_PATH):
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch_employee_details(employee_code: str):
        # try MySQL first
        mysql_conn = get_mysql_connection()
        if mysql_conn:
            try:
                cur = mysql_conn.cursor(dictionary=True)
                cur.execute(
                    "SELECT * FROM employee_details WHERE employee_code = %s LIMIT 1",
                    (employee_code,),
                )
                row = cur.fetchone()
                cur.close()
                if row:
                    return row
            except Exception as e:
                st.error(f"Error fetching employee details from MySQL: {e}")
            finally:
                try:
                    mysql_conn.close()
                except Exception:
                    pass

        # fallback to sqlite
        try:
            conn = get_sqlite_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM employee_details WHERE employee_code = ? LIMIT 1", (employee_code,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            return row
        except Exception as e:
            st.error(f"Error fetching employee details: {e}")
            return None

# page config
st.set_page_config(page_title="Premji Group", page_icon="🛠️", layout="wide")


# Force the main block container to use full width even after reruns
st.markdown(
    """
    <style>
    .block-container {
        max-width: 100% !important;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)



# temp dir for images (if needed)
TEMP_IMAGE_DIR = "temp_profile_images"
os.makedirs(TEMP_IMAGE_DIR, exist_ok=True)


def _maybe_render_image_from_row(details):
    """Render image from file path or bytes/blob if available."""
    if not details:
        return False

    possible_path_keys = ["profile_image_path", "photo_path", "image_path", "profile_photo", "photo"]
    possible_blob_keys = ["profile_image_blob", "photo_blob", "image_blob", "profile_photo_blob", "photo_blob"]

    for k in possible_path_keys:
        if k in details and details[k]:
            path = details[k]
            if path and os.path.exists(path):
                try:
                    img = Image.open(path)
                    st.image(img, use_column_width=True)
                    return True
                except Exception:
                    break

    for k in possible_blob_keys:
        if k in details and details[k]:
            blob = details[k]
            try:
                img_bytes = bytes(blob)
                img = Image.open(BytesIO(img_bytes))
                st.image(img, use_column_width=True)
                return True
            except Exception:
                break

    return False


def render_profile_card(details_row):
    """Render a responsive profile card with highlighted values."""
    if not details_row:
        st.info("No profile details found for this user.")
        return

    details = dict(details_row)

    name = details.get("employee_name") or details.get("name") or details.get("full_name") or "Unknown"
    code = details.get("employee_code") or details.get("emp_code") or details.get("code") or ""
    role = details.get("user_role") or details.get("role") or ""

    # simple responsive/value styling
    st.markdown(
        """
        <style>
        .profile-value { color: #2a8bd6; font-weight:600; }
        @media (max-width:600px) {
            .stImage > img { width:100% !important; height:auto !important; }
            .profile-value { font-size:1.05rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns([1, 3])
    with cols[0]:
        rendered = _maybe_render_image_from_row(details)
        if not rendered:
            st.markdown("<div style='font-size:48px'>🧑‍🔧</div>", unsafe_allow_html=True)

    with cols[1]:
        st.markdown(f"## {name}")
        st.markdown(f"**Code:** {code}  ")
        st.markdown(f"**Role:** {role}  ")
        st.markdown("---")

        skip_keys = {
            "employee_name",
            "name",
            "full_name",
            "employee_code",
            "emp_code",
            "code",
            "user_role",
            "role",
            "profile_image_path",
            "photo_path",
            "image_path",
            "profile_photo",
            "photo",
            "profile_image_blob",
            "photo_blob",
            "image_blob",
            "profile_photo_blob",
        }
        items = [(k, v) for k, v in details.items() if k not in skip_keys and v not in (None, "")]

        if items:
            for i in range(0, len(items), 2):
                left = items[i]
                right = items[i + 1] if i + 1 < len(items) else None
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.write(f"**{left[0].replace('_', ' ').title()}:**")
                    st.markdown(f"<span class='profile-value'>{left[1]}</span>", unsafe_allow_html=True)
                with c2:
                    if right:
                        st.write(f"**{right[0].replace('_', ' ').title()}:**")
                        st.markdown(f"<span class='profile-value'>{right[1]}</span>", unsafe_allow_html=True)
        else:
            st.write("No additional details available.")


def build_menu_for_role(role: str):
    # Profile visible to all users
    base = ["Attendance", "Profile"]

    # Insert role-specific pages in addition to Profile
    if role == 'TeamLeader':
        base.insert(1, "Mark attendance for the other")
    elif role == 'Admin':
        base.insert(1, "Workstation")
    elif role == 'Super Admin':
        base.insert(1, "Daily Advisor Data Entry")

    # Add Administration for Admin and Super Admin (if your main UI includes it)
    # If you already add Admin in sidebar elsewhere, ensure not duplicated
    if role in ("Admin", "Super Admin"):
        # put Administration at position 1 (after Attendance)
        if "Administration" not in base:
            base.insert(1, "Administration")
        # Add Attendance Records after Administration
        if "Attendance Records" not in base:
            idx = base.index("Administration") + 1
            base.insert(idx, "Attendance Records")

    return base


def user_interface():
    # Expect st.session_state['user'] is set by login flow
    user = st.session_state.get("user")
    if not user:
        st.warning("No user found in session state. Please log in.")
        return

    st.sidebar.title(f"👤 {user.get('employee_name', 'Unknown')}")
    st.sidebar.markdown(
        f"**Role:** {user.get('user_role', 'Unknown')}"
        f"\n\n**Code:** {user.get('employee_code', '')}"
    )

    role = user.get("user_role")
    menu = build_menu_for_role(role)

    choice = st.sidebar.radio("Please select an option", menu)

    # Logout button (separate)
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.success("Logged out successfully.")
        st.experimental_rerun()

    # Handle menu choices
    if choice == "Attendance":
        attendance_page(user)

    elif choice == "Profile":
        emp_code = user.get("employee_code")
        details = None
        try:
            details = fetch_employee_details(emp_code)
        except Exception as e:
            st.error(f"Error fetching profile: {e}")
        render_profile_card(details)

    elif choice == "Administration":
        # admin_page must exist and user must be Admin or Super Admin
        if admin_page is None:
            st.error("Administration module not available. Make sure admin.py exists and is importable.")
        else:
            current_user = st.session_state.get("user") or user
            # quick permission check to give clearer feedback earlier
            if current_user.get("user_role") not in ("Admin", "Super Admin"):
                st.error("Access denied. This page is only available to Admin or Super Admin.")
            else:
                try:
                    # call admin_page() which itself enforces server-side permissions
                    admin_page()
                except Exception as e:
                    st.error(f"Failed to render Administration page: {e}")

    elif choice == "Mark attendance for the other":
        if teamlead_page is None:
            st.error("TeamLead module not available. Make sure teamlead.py exists and is importable.")
        else:
            # prepare session keys teamlead expects
            st.session_state["logged_in"] = True
            st.session_state["user_data"] = {
                "role": user.get("user_role"),
                "code": user.get("employee_code"),
                "name": user.get("employee_name"),
            }
            st.session_state["user_role"] = user.get("user_role")
            st.session_state["user_code"] = user.get("employee_code")
            try:
                teamlead_page()
            except Exception as e:
                st.error(f"Failed to render TeamLead page: {e}")

    elif choice == "Attendance Records":
        if admin_attendance_page is None:
            st.error("Attendance module not available. Make sure admin_attendance.py exists and is importable.")
        else:
            admin_attendance_page()


    elif choice == "Workstation":
        st.write("Workstation page - to be implemented or wired to your workstation module.")

    elif choice == "Daily Advisor Data Entry":
        st.write("Daily Advisor Data Entry - to be implemented or linked to the advisor page.")


if __name__ == "__main__":
    user_interface()
