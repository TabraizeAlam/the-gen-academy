from pathlib import Path
import pandas as pd
import yaml
import streamlit as st

BASE_DIR = Path(__file__).parent.parent


@st.cache_data
def load_config() -> dict:
    with open(BASE_DIR / "config.yaml") as f:
        return yaml.safe_load(f)


@st.cache_data
def load_employees() -> pd.DataFrame:
    return pd.read_csv(BASE_DIR / "data" / "employees.csv")


@st.cache_data
def load_public_holidays() -> pd.DataFrame:
    df = pd.read_csv(BASE_DIR / "data" / "public_holidays.csv")
    df["holiday_date"] = pd.to_datetime(df["holiday_date"])
    return df


@st.cache_data
def load_attendance() -> pd.DataFrame:
    att = pd.read_csv(BASE_DIR / "wfo_attendance_log.csv")
    att["log_date"] = pd.to_datetime(att["log_date"])
    att["week_number"] = att["week_number"].astype(int)
    att["login_duration_mins"] = (
        pd.to_numeric(att["login_duration_mins"], errors="coerce").fillna(0).astype(int)
    )

    emp = load_employees()
    holidays = load_public_holidays()

    # Merge enriched metadata (dept, team name, manager, role) — no column conflicts
    att = att.merge(
        emp[["employee_id", "department", "team", "manager_id", "role", "hire_date"]],
        on="employee_id",
        how="left",
    )

    att["department"] = att["department"].fillna("Unknown")
    att["team"] = att["team"].fillna("Unknown")
    att["manager_id"] = att["manager_id"].fillna("")
    att["role"] = att["role"].fillna("employee")

    # Flag rows that fall on a public holiday date
    holiday_dates = set(holidays["holiday_date"].dt.date)
    att["is_holiday"] = att["log_date"].dt.date.apply(lambda d: d in holiday_dates)

    # Derived time / calendar columns
    att["week_start"] = att["log_date"] - pd.to_timedelta(
        att["log_date"].dt.dayofweek, unit="D"
    )
    att["month"] = att["log_date"].dt.month
    att["month_name"] = att["log_date"].dt.strftime("%B")
    att["year"] = att["log_date"].dt.year
    att["month_year"] = att["log_date"].dt.to_period("M").astype(str)
    att["day_of_week"] = att["log_date"].dt.day_name()
    att["day_num"] = att["log_date"].dt.dayofweek  # 0 = Monday

    # Deduplicate multiple logins per day: keep best status, sum duration.
    # Priority: IN_OFFICE (0) > WFH (1) > ON_LEAVE (2).
    STATUS_PRIORITY = {"IN_OFFICE": 0, "WFH": 1, "ON_LEAVE": 2}
    att["_status_pri"] = att["day_status"].map(STATUS_PRIORITY).fillna(1)

    # Non-aggregated columns: pick from the best-priority row
    meta_cols = [
        "log_id", "full_name", "team_id", "login_time", "logout_time",
        "ip_address", "location_type", "day_status", "week_number", "leave_type",
        "notes", "department", "team", "manager_id", "role", "hire_date",
        "is_holiday", "week_start", "month", "month_name", "year", "month_year",
        "day_of_week", "day_num", "_status_pri",
    ]
    idx_best = att.groupby(["employee_id", "log_date"])["_status_pri"].idxmin()
    att_best = att.loc[idx_best, ["employee_id", "log_date"] + meta_cols].copy()

    # Sum durations across all sessions on the same day
    dur_sum = att.groupby(["employee_id", "log_date"])["login_duration_mins"].sum().reset_index()
    att = att_best.merge(dur_sum, on=["employee_id", "log_date"], how="left")
    att = att.drop(columns=["_status_pri"]).reset_index(drop=True)

    return att
