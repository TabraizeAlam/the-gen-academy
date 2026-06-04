import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import streamlit as st
import plotly.express as px
import pandas as pd

from utils.compliance import compute_weekly_compliance, compute_employee_stats

st.set_page_config(page_title="Individual Compliance", page_icon="👤", layout="wide")

st.title("👤 Individual Non-Compliance Flags")
st.caption(
    "Employees who worked from home more than 2 days in a given week "
    "without sufficient approved leave to justify it."
)
st.divider()

weekly = compute_weekly_compliance()
emp_stats = compute_employee_stats()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔎 Filters")
    all_months = sorted(weekly["month_year"].unique())
    sel_months = st.multiselect("Month(s)", all_months, default=all_months)
    all_teams = sorted(weekly["team"].dropna().unique())
    sel_teams = st.multiselect("Team(s)", all_teams, default=all_teams)
    all_depts = sorted(weekly["department"].dropna().unique())
    sel_depts = st.multiselect("Department(s)", all_depts, default=all_depts)
    show_only_nc = st.checkbox("Show only non-compliant weeks", value=True)

wf = weekly[
    weekly["month_year"].isin(sel_months)
    & weekly["team"].isin(sel_teams)
    & weekly["department"].isin(sel_depts)
]
if show_only_nc:
    wf = wf[~wf["is_compliant"] & (wf["required_days"] > 0)]

# ── Employee compliance score cards ──────────────────────────────────────────
st.subheader("Employee Compliance Scores")

es = emp_stats[emp_stats["team"].isin(sel_teams) & emp_stats["department"].isin(sel_depts)]

cols = st.columns(5)
for i, (_, row) in enumerate(es.iterrows()):
    with cols[i % 5]:
        pct = row["compliance_pct"]
        bg = "#d4edda" if pct >= 80 else "#fff3cd" if pct >= 60 else "#f8d7da"
        border = "#28a745" if pct >= 80 else "#ffc107" if pct >= 60 else "#dc3545"
        streak_icon = "✅" if row["streak_type"] == "compliant" else "❌"
        role_icon = "👔" if row["role"] == "manager" else "⭐" if row["role"] == "senior_employee" else "👤"
        st.markdown(
            f"""
            <div style="background:{bg};border-left:4px solid {border};
                        padding:10px 12px;border-radius:8px;margin-bottom:8px;">
              <div style="font-weight:700;font-size:0.88rem">{role_icon} {row['full_name']}</div>
              <div style="font-size:0.75rem;color:#666">{row['team']}</div>
              <div style="font-size:1.6rem;font-weight:800;color:{border}">{pct}%</div>
              <div style="font-size:0.75rem">{row['compliant_weeks']}/{row['total_weeks']} weeks</div>
              <div style="font-size:0.75rem">{streak_icon} {row['current_streak']}w streak</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()

# ── Non-compliance detail table ───────────────────────────────────────────────
st.subheader(f"Non-Compliance Detail ({len(wf)} rows)")

if len(wf):
    display = wf.copy()
    display["week_start"] = display["week_start"].dt.strftime("%b %d, %Y")
    display["Status"] = display["is_compliant"].apply(
        lambda c: "✅ Compliant" if c else "❌ Non-Compliant"
    )
    display["Shortfall"] = display["required_days"] - display["office_days"]
    display["Shortfall"] = display["Shortfall"].apply(lambda v: f"-{v} day(s)" if v > 0 else "—")

    st.dataframe(
        display[
            [
                "full_name", "department", "team", "role",
                "week_number", "week_start",
                "office_days", "required_days", "wfh_days", "leave_days",
                "Shortfall", "Status",
            ]
        ].rename(
            columns={
                "full_name": "Employee",
                "department": "Dept",
                "team": "Team",
                "role": "Role",
                "week_number": "Week",
                "week_start": "Week of",
                "office_days": "Office",
                "required_days": "Req'd",
                "wfh_days": "WFH",
                "leave_days": "Leave",
            }
        ).sort_values(["Employee", "Week"]),
        use_container_width=True,
        hide_index=True,
        height=400,
    )

    # ── Export ────────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    display.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    st.download_button(
        "⬇️ Export to Excel",
        data=buf,
        file_name="non_compliance_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.success("No records match the current filters.")

st.divider()

# ── Trend: weekly non-compliance count ───────────────────────────────────────
st.subheader("📉 Non-Compliance Count Over Time")

nc_weekly = (
    weekly[weekly["team"].isin(sel_teams) & weekly["department"].isin(sel_depts)]
    .groupby(["week_number", "team"])
    .apply(lambda g: (~g["is_compliant"] & (g["required_days"] > 0)).sum())
    .reset_index(name="non_compliant_count")
)

if len(nc_weekly):
    fig = px.bar(
        nc_weekly.sort_values("week_number"),
        x="week_number",
        y="non_compliant_count",
        color="team",
        barmode="stack",
        labels={"week_number": "ISO Week", "non_compliant_count": "Non-Compliant Employees", "team": "Team"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), height=280)
    st.plotly_chart(fig, use_container_width=True)

# ── Leave vs WFH abuse check ─────────────────────────────────────────────────
st.subheader("🗓️ Leave vs WFH — Strategic Leave Analysis")
st.caption(
    "High leave days combined with low office days in the same weeks may indicate "
    "strategic use of leave to avoid coming in."
)

emp_leave = (
    weekly[weekly["team"].isin(sel_teams)]
    .groupby("employee_id")
    .agg(
        full_name=("full_name", "first"),
        team=("team", "first"),
        avg_leave=("leave_days", "mean"),
        avg_office=("office_days", "mean"),
        compliance_pct=("is_compliant", lambda x: round(x.mean() * 100, 1)),
    )
    .reset_index()
)

if len(emp_leave):
    fig2 = px.scatter(
        emp_leave,
        x="avg_leave",
        y="avg_office",
        color="compliance_pct",
        size="avg_leave",
        hover_name="full_name",
        hover_data={"team": True, "compliance_pct": True},
        labels={
            "avg_leave": "Avg Leave Days / Week",
            "avg_office": "Avg Office Days / Week",
            "compliance_pct": "Compliance %",
        },
        color_continuous_scale=["#dc3545", "#ffc107", "#28a745"],
        range_color=[0, 100],
        text="full_name",
    )
    fig2.update_traces(textposition="top center", textfont_size=9)
    fig2.add_hline(y=3, line_dash="dash", line_color="gray", annotation_text="3-day target")
    fig2.update_layout(margin=dict(l=10, r=10, t=20, b=10), height=340)
    st.plotly_chart(fig2, use_container_width=True)
