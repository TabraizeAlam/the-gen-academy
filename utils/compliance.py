from __future__ import annotations
import pandas as pd
import streamlit as st
from utils.data_loader import load_attendance, load_config


def _required_days(leave_days: int, available_days: int, config: dict) -> int:
    """Return required office days, adjusted for leave taken and capped at available days."""
    table: dict = config["leave_adjusted_requirements"]
    key = min(leave_days, 5)
    required = int(table.get(key, 3))
    return min(required, max(available_days, 0))


@st.cache_data
def compute_weekly_compliance() -> pd.DataFrame:
    """One row per (employee, week) with office-day counts and compliance flag."""
    att = load_attendance()
    config = load_config()
    min_dur: int = config["policy"]["min_login_duration_minutes"]

    rows = []
    for (emp_id, week_num), grp in att.groupby(["employee_id", "week_number"]):
        leave_days = int((grp["day_status"] == "ON_LEAVE").sum())
        total_days = len(grp)
        available_days = total_days - leave_days

        office_days = int(
            (
                (grp["day_status"] == "IN_OFFICE")
                & (grp["login_duration_mins"] >= min_dur)
            ).sum()
        )
        wfh_days = int((grp["day_status"] == "WFH").sum())
        required = _required_days(leave_days, available_days, config)
        is_compliant = bool(office_days >= required)

        r0 = grp.iloc[0]
        rows.append(
            {
                "employee_id": emp_id,
                "full_name": r0["full_name"],
                "department": r0["department"],
                "team": r0["team"],
                "team_id": r0["team_id"],
                "manager_id": r0["manager_id"],
                "role": r0["role"],
                "week_number": int(week_num),
                "week_start": r0["week_start"],
                "month_year": r0["month_year"],
                "month": int(r0["month"]),
                "year": int(r0["year"]),
                "total_days": total_days,
                "leave_days": leave_days,
                "available_days": available_days,
                "required_days": required,
                "office_days": office_days,
                "wfh_days": wfh_days,
                "is_compliant": is_compliant,
                "compliance_gap": max(0, required - office_days),
            }
        )

    df = pd.DataFrame(rows)
    df["week_start"] = pd.to_datetime(df["week_start"])
    return df


@st.cache_data
def compute_employee_stats() -> pd.DataFrame:
    """Per-employee compliance summary with streak tracking."""
    weekly = compute_weekly_compliance()
    rows = []

    for emp_id, grp in weekly.groupby("employee_id"):
        # Only count weeks where something was required of the employee
        trackable = grp[grp["required_days"] > 0]
        total = len(trackable)
        compliant = int(trackable["is_compliant"].sum())
        pct = round(compliant / total * 100, 1) if total > 0 else 0.0

        # Streak: consecutive same-compliance weeks from most recent
        sorted_grp = grp.sort_values("week_number", ascending=False)
        streak = 0
        streak_type: str | None = None
        for _, row in sorted_grp.iterrows():
            if row["required_days"] == 0:
                continue
            current = bool(row["is_compliant"])
            if streak_type is None:
                streak_type = "compliant" if current else "non_compliant"
                streak = 1
            elif (streak_type == "compliant") == current:
                streak += 1
            else:
                break

        r0 = grp.iloc[0]
        rows.append(
            {
                "employee_id": emp_id,
                "full_name": r0["full_name"],
                "department": r0["department"],
                "team": r0["team"],
                "team_id": r0["team_id"],
                "manager_id": r0["manager_id"],
                "role": r0["role"],
                "total_weeks": total,
                "compliant_weeks": compliant,
                "non_compliant_weeks": total - compliant,
                "compliance_pct": pct,
                "current_streak": streak,
                "streak_type": streak_type or "compliant",
                "avg_office_days": round(float(grp["office_days"].mean()), 1),
                "avg_wfh_days": round(float(grp["wfh_days"].mean()), 1),
                "avg_leave_days": round(float(grp["leave_days"].mean()), 1),
            }
        )

    return pd.DataFrame(rows).sort_values("compliance_pct", ascending=False).reset_index(drop=True)


@st.cache_data
def compute_team_weekly() -> pd.DataFrame:
    """Per-team per-week compliance aggregation."""
    weekly = compute_weekly_compliance()
    rows = []

    for (team_id, week_num), grp in weekly.groupby(["team_id", "week_number"]):
        total_emp = len(grp)
        compliant_emp = int(grp["is_compliant"].sum())
        r0 = grp.iloc[0]
        rows.append(
            {
                "team_id": team_id,
                "team": r0["team"],
                "department": r0["department"],
                "week_number": int(week_num),
                "week_start": r0["week_start"],
                "month_year": r0["month_year"],
                "month": int(r0["month"]),
                "year": int(r0["year"]),
                "total_employees": total_emp,
                "compliant_employees": compliant_emp,
                "non_compliant_employees": total_emp - compliant_emp,
                "compliance_pct": round(compliant_emp / total_emp * 100, 1) if total_emp > 0 else 0.0,
                "avg_office_days": round(float(grp["office_days"].mean()), 1),
            }
        )

    df = pd.DataFrame(rows)
    df["week_start"] = pd.to_datetime(df["week_start"])
    return df
