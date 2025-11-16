# database.py
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

@st.cache_resource
def get_db_engine():
    """Create and cache SQLAlchemy engine using Streamlit secrets."""
    mysql_conf = st.secrets["mysql"]
    connection_string = (
        f"mysql+pymysql://{mysql_conf['user']}:{mysql_conf['password']}"
        f"@{mysql_conf['host']}/{mysql_conf['database']}"
        "?charset=utf8mb4"
    )
    engine = create_engine(connection_string, pool_pre_ping=True)
    return engine


def run_query(query: str, params: dict | None = None, fetch_one: bool = False):
    """
    Run a SQL query safely with optional parameters.
    - For SELECTs: returns dict (fetch_one=True) or list[dict] (fetch_one=False)
    - For non-SELECTs: returns {"rowcount": <n>} on success
    This implementation uses engine.begin() so updates/inserts/deletes are committed.
    """
    engine = get_db_engine()
    try:
        # Use a transactional context for everything. SELECTs inside a transaction are fine;
        # non-SELECTs will be committed when the context exits.
        with engine.begin() as conn:
            result = conn.execute(text(query), params or {})
            if result.returns_rows:
                if fetch_one:
                    row = result.mappings().fetchone()
                    return dict(row) if row else None
                else:
                    rows = result.mappings().all()
                    return [dict(r) for r in rows]
            else:
                # non-select query - return rowcount
                return {"rowcount": result.rowcount}
    except SQLAlchemyError as e:
        st.error(f"Database error: {e}")
        return None


def fetch_employee_details(employee_code: str):
    """
    Fetch a single employee's details from the employee_details table using the project DB engine.
    Returns a dict or None.
    """
    query = """
        SELECT *
        FROM employee_details
        WHERE employee_code = :emp_code
        LIMIT 1
    """
    return run_query(query, {"emp_code": employee_code}, fetch_one=True)
