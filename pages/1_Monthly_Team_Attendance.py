import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from utils.data_loader import load_attendance
from utils.compliance import compute_weekly_compliance, compute_team_weekly

st.set_page_config(page_title="Monthly Team Attendance", page_icon="📅", layout="wide")

st.title("📅 Monthly Team Attendance")
st.caption("Office presence per team, broken down by week and individual employee.")
st.divider()

att = load_attendance()
weekly = compute_weekly_compliance()
team_weekly = compute_team_weekly()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔎 Filters")
    month_options = sorted(att["month_year"].unique())
    month_labels = {m: pd.Period(m).strftime("%B %Y") for m in month_options}
    sel_month = st.selectbox(
        "Month",
        month_options,
        format_func=lambda m: month_labels[m],
        index=len(month_options) - 1,
    )
    all_teams = sorted(weekly["team"].dropna().unique())
    sel_teams = st.multiselect("Team(s)", all_teams, default=all_teams)

# Filter to selected month
att_m = att[att["month_year"] == sel_month].copy()
weekly_m = weekly[weekly["month_year"] == sel_month]
tw_m = team_weekly[(team_weekly["month_year"] == sel_month) & team_weekly["team"].isin(sel_teams)]

month_label = month_labels[sel_month]
st.subheader(f"📆 {month_label}")

# ── Team weekly summary table ─────────────────────────────────────────────────
st.markdown("### Team Summary — Office Days vs Required")

if len(tw_m):
    pivot_team = tw_m.pivot_table(
        index="team", columns="week_number", values="compliance_pct", aggfunc="first"
    ).round(0)
    pivot_team.columns = [f"Wk {c}" for c in pivot_team.columns]

    def style_cell(val):
        if pd.isna(val):
            return ""
        if val >= 100:
            return "background-color: #d4edda; color: #155724; font-weight:600"
        if val >= 60:
            return "background-color: #fff3cd; color: #856404"
        return "background-color: #f8d7da; color: #721c24"

    styled = pivot_team.style.map(style_cell).format("{:.0f}%", na_rep="-")
    st.dataframe(styled, use_container_width=True)
    st.caption("🟢 ≥100%  🟡 60–99%  🔴 <60%   (% of team members who were compliant that week)")

st.divider()

# ── Individual attendance heatmap ─────────────────────────────────────────────
st.markdown("### Individual Attendance Heatmap")

team_choice = st.selectbox("Show team", sel_teams) if sel_teams else None

if team_choice:
    team_att = att_m[att_m["team"] == team_choice].copy()

    STATUS_NUM = {"IN_OFFICE": 0, "WFH": 1, "ON_LEAVE": 2}
    STATUS_LABEL = {0: "In Office", 1: "WFH", 2: "On Leave"}
    STATUS_COLOR = {0: "#28a745", 1: "#4a90d9", 2: "#adb5bd"}

    team_att["status_num"] = team_att["day_status"].map(STATUS_NUM).fillna(1)
    team_att["date_label"] = team_att["log_date"].dt.strftime("%b %d (%a)")

    dates_sorted = sorted(team_att["log_date"].unique())
    date_labels = [pd.Timestamp(d).strftime("%b %d (%a)") for d in dates_sorted]
    employees_sorted = sorted(team_att["full_name"].unique())

    # Build z matrix and hover text
    z_matrix = []
    text_matrix = []
    for emp in employees_sorted:
        row_z = []
        row_t = []
        emp_data = team_att[team_att["full_name"] == emp].set_index("log_date")
        for d in dates_sorted:
            ts = pd.Timestamp(d)
            if ts in emp_data.index:
                sn = int(emp_data.loc[ts, "status_num"].values[0] if hasattr(emp_data.loc[ts, "status_num"], "values") else emp_data.loc[ts, "status_num"])
                row_z.append(sn)
                dur = emp_data.loc[ts, "login_duration_mins"]
                if hasattr(dur, "values"):
                    dur = dur.values[0]
                row_t.append(f"{STATUS_LABEL[sn]}<br>{int(dur)} min")
            else:
                row_z.append(-1)
                row_t.append("No data")
        z_matrix.append(row_z)
        text_matrix.append(row_t)

    colorscale = [
        [0.0, "#e0e0e0"],   # -1 no data
        [0.2, "#e0e0e0"],
        [0.21, "#28a745"],  # 0 in office
        [0.45, "#28a745"],
        [0.46, "#4a90d9"],  # 1 WFH
        [0.70, "#4a90d9"],
        [0.71, "#adb5bd"],  # 2 on leave
        [1.0, "#adb5bd"],
    ]

    fig = go.Figure(
        go.Heatmap(
            z=z_matrix,
            x=date_labels,
            y=employees_sorted,
            text=text_matrix,
            hovertemplate="%{y} · %{x}<br>%{text}<extra></extra>",
            colorscale=colorscale,
            zmin=-1,
            zmax=2,
            showscale=False,
            xgap=2,
            ygap=2,
        )
    )
    fig.update_layout(
        height=max(200, len(employees_sorted) * 45 + 80),
        margin=dict(l=10, r=10, t=20, b=60),
        xaxis=dict(tickangle=-45, tickfont_size=11),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Legend
    lcols = st.columns(3)
    with lcols[0]:
        st.markdown("🟩 **In Office**")
    with lcols[1]:
        st.markdown("🟦 **Work From Home**")
    with lcols[2]:
        st.markdown("⬜ **On Leave / No Data**")

st.divider()

# ── Weekly breakdown table ────────────────────────────────────────────────────
st.markdown("### Weekly Detail")

wm_filtered = weekly_m[weekly_m["team"].isin(sel_teams)].copy()
wm_filtered["week_start"] = wm_filtered["week_start"].dt.strftime("%b %d")
wm_filtered["Status"] = wm_filtered["is_compliant"].apply(
    lambda c: "✅ Compliant" if c else "❌ Non-Compliant"
)

st.dataframe(
    wm_filtered[
        ["full_name", "team", "week_number", "week_start", "office_days",
         "required_days", "wfh_days", "leave_days", "Status"]
    ].rename(
        columns={
            "full_name": "Employee",
            "team": "Team",
            "week_number": "Week",
            "week_start": "Week of",
            "office_days": "Office Days",
            "required_days": "Required",
            "wfh_days": "WFH Days",
            "leave_days": "Leave Days",
        }
    ).sort_values(["Team", "Employee", "Week"]),
    use_container_width=True,
    hide_index=True,
)
