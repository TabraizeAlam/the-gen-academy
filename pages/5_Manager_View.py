import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import plotly.express as px
import pandas as pd

from utils.data_loader import load_employees
from utils.compliance import compute_weekly_compliance, compute_employee_stats

st.set_page_config(page_title="Manager View", page_icon="👔", layout="wide")

st.title("👔 Manager View")
st.caption("A manager sees compliance for their direct reports only.")
st.divider()

employees = load_employees()
weekly = compute_weekly_compliance()
emp_stats = compute_employee_stats()

# Build manager list (employees with at least one direct report)
managers_df = employees[employees["manager_id"].notna() & (employees["manager_id"] != "")]
manager_ids = managers_df["manager_id"].unique().tolist()
manager_info = employees[employees["employee_id"].isin(manager_ids)][
    ["employee_id", "full_name", "team", "department"]
]

# ── Sidebar: manager selector ─────────────────────────────────────────────────
with st.sidebar:
    st.header("Select Manager")
    manager_options = {
        row["employee_id"]: f"{row['full_name']} ({row['team']})"
        for _, row in manager_info.iterrows()
    }
    if not manager_options:
        st.warning("No managers found.")
        st.stop()

    sel_mgr_id = st.selectbox(
        "Manager",
        list(manager_options.keys()),
        format_func=lambda eid: manager_options[eid],
    )
    st.divider()
    all_months = sorted(weekly["month_year"].unique())
    sel_months = st.multiselect("Month(s)", all_months, default=all_months)

# Direct reports of the selected manager
direct_reports = employees[employees["manager_id"] == sel_mgr_id]["employee_id"].tolist()
mgr_row = manager_info[manager_info["employee_id"] == sel_mgr_id].iloc[0]

st.subheader(f"Manager: {mgr_row['full_name']} — {mgr_row['team']}, {mgr_row['department']}")
st.caption(f"**{len(direct_reports)}** direct reports")

if not direct_reports:
    st.info("This manager has no direct reports in the dataset.")
    st.stop()

# Filter data to direct reports
dr_weekly = weekly[
    weekly["employee_id"].isin(direct_reports) & weekly["month_year"].isin(sel_months)
]
dr_stats = emp_stats[emp_stats["employee_id"].isin(direct_reports)]

# ── Team KPIs ──────────────────────────────────────────────────────────────────
trackable = dr_weekly[dr_weekly["required_days"] > 0]
team_pct = round(trackable["is_compliant"].mean() * 100, 1) if len(trackable) else 0.0
avg_office = round(float(dr_weekly["office_days"].mean()), 1) if len(dr_weekly) else 0.0
nc_weeks = int((~trackable["is_compliant"]).sum())

k1, k2, k3, k4 = st.columns(4)
k1.metric("Direct Reports", len(direct_reports))
k2.metric("Team Compliance", f"{team_pct}%")
k3.metric("Avg Office Days/Wk", avg_office)
k4.metric("Non-Compliant Employee-Weeks", nc_weeks)

st.markdown("<br>", unsafe_allow_html=True)

# Also show if the manager themselves is compliant
mgr_stats = emp_stats[emp_stats["employee_id"] == sel_mgr_id]
if len(mgr_stats):
    mgr = mgr_stats.iloc[0]
    mgr_pct = mgr["compliance_pct"]
    bgc = "#d4edda" if mgr_pct >= 80 else "#fff3cd" if mgr_pct >= 60 else "#f8d7da"
    bdc = "#28a745" if mgr_pct >= 80 else "#ffc107" if mgr_pct >= 60 else "#dc3545"
    st.markdown(
        f"""
        <div style="background:{bgc};border-left:5px solid {bdc};
                    padding:12px 16px;border-radius:8px;margin-bottom:16px;">
          <b>Manager's own compliance:</b> {mgr_pct}% &nbsp;
          ({mgr['compliant_weeks']}/{mgr['total_weeks']} weeks) &nbsp;
          {'⚠️ <b>This manager is non-compliant — sets a poor example.</b>' if mgr_pct < 80 else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# ── Direct report cards ───────────────────────────────────────────────────────
st.subheader("Direct Report Compliance Cards")

num_cols = min(len(direct_reports), 3)
rows_needed = (len(direct_reports) + num_cols - 1) // num_cols
dr_list = dr_stats.to_dict("records")

for r in range(rows_needed):
    cols = st.columns(num_cols)
    for c in range(num_cols):
        idx = r * num_cols + c
        if idx >= len(dr_list):
            break
        emp = dr_list[idx]
        pct = emp["compliance_pct"]
        bg = "#d4edda" if pct >= 80 else "#fff3cd" if pct >= 60 else "#f8d7da"
        border = "#28a745" if pct >= 80 else "#ffc107" if pct >= 60 else "#dc3545"
        streak_icon = "✅" if emp["streak_type"] == "compliant" else "❌"

        # Last week status
        last_wk = int(weekly["week_number"].max())
        lw_entry = weekly[
            (weekly["employee_id"] == emp["employee_id"])
            & (weekly["week_number"] == last_wk)
        ]
        if len(lw_entry):
            lw_row = lw_entry.iloc[0]
            last_wk_str = f"Last wk: {int(lw_row['office_days'])} office / {int(lw_row['required_days'])} req'd"
            last_wk_ok = bool(lw_row["is_compliant"])
        else:
            last_wk_str = "Last wk: no data"
            last_wk_ok = True

        with cols[c]:
            st.markdown(
                f"""
                <div style="background:{bg};border:2px solid {border};
                            border-radius:10px;padding:16px;margin-bottom:12px;">
                  <div style="font-weight:700;font-size:1rem">{emp['full_name']}</div>
                  <div style="font-size:0.8rem;color:#555;margin-bottom:8px">{emp['role'].replace('_',' ')}</div>
                  <div style="font-size:2rem;font-weight:800;color:{border}">{pct}%</div>
                  <div style="font-size:0.8rem">{emp['compliant_weeks']}/{emp['total_weeks']} weeks compliant</div>
                  <div style="font-size:0.8rem;margin-top:4px">{streak_icon} {emp['current_streak']}w {emp['streak_type'].replace('_',' ')}</div>
                  <div style="font-size:0.78rem;margin-top:6px;color:{'#721c24' if not last_wk_ok else '#155724'}">
                    {'⚠️' if not last_wk_ok else '✅'} {last_wk_str}
                  </div>
                  <div style="font-size:0.78rem;margin-top:2px">
                    🏢 {emp['avg_office_days']} avg &nbsp; 💻 {emp['avg_wfh_days']} avg WFH
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.divider()

# ── Weekly breakdown for this team ───────────────────────────────────────────
st.subheader("📋 Weekly Attendance Detail")

disp = dr_weekly.copy()
disp["week_start"] = disp["week_start"].dt.strftime("%b %d")
disp["Status"] = disp["is_compliant"].apply(lambda c: "✅" if c else "❌")

st.dataframe(
    disp[["full_name", "week_number", "week_start", "office_days",
          "required_days", "wfh_days", "leave_days", "Status"]]
    .rename(
        columns={
            "full_name": "Employee",
            "week_number": "Week",
            "week_start": "Week of",
            "office_days": "Office",
            "required_days": "Req'd",
            "wfh_days": "WFH",
            "leave_days": "Leave",
        }
    )
    .sort_values(["Employee", "Week"]),
    use_container_width=True,
    hide_index=True,
    height=380,
)

st.divider()

# ── Weekly compliance trend for this team ────────────────────────────────────
st.subheader("📈 Weekly Compliance Trend")

fig = px.line(
    dr_weekly.sort_values("week_number"),
    x="week_number",
    y="office_days",
    color="full_name",
    markers=True,
    labels={"week_number": "ISO Week", "office_days": "Office Days", "full_name": "Employee"},
    color_discrete_sequence=px.colors.qualitative.Pastel,
)
fig.add_hline(y=3, line_dash="dash", line_color="red", annotation_text="Target: 3 days")
fig.update_layout(
    yaxis_range=[0, 6],
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(l=10, r=10, t=40, b=10),
    height=300,
)
st.plotly_chart(fig, use_container_width=True)
