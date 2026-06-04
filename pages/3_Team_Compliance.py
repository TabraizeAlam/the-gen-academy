import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from utils.compliance import compute_weekly_compliance, compute_team_weekly

st.set_page_config(page_title="Team Compliance Summary", page_icon="👥", layout="wide")

st.title("👥 Team Compliance Summary")
st.caption("Which teams are consistently meeting the 3-day office requirement?")
st.divider()

weekly = compute_weekly_compliance()
team_weekly = compute_team_weekly()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔎 Filters")
    all_months = sorted(team_weekly["month_year"].unique())
    sel_months = st.multiselect("Month(s)", all_months, default=all_months)

tw = team_weekly[team_weekly["month_year"].isin(sel_months)]
wf = weekly[weekly["month_year"].isin(sel_months)]

# ── Team KPI cards ────────────────────────────────────────────────────────────
teams = sorted(tw["team"].unique())
team_summary = (
    tw.groupby(["team", "department"])
    .agg(
        total_emp_weeks=("total_employees", "sum"),
        compliant_emp_weeks=("compliant_employees", "sum"),
        avg_office_days=("avg_office_days", "mean"),
        weeks_tracked=("week_number", "nunique"),
    )
    .reset_index()
)
team_summary["compliance_pct"] = (
    team_summary["compliant_emp_weeks"] / team_summary["total_emp_weeks"] * 100
).round(1)
team_summary["avg_office_days"] = team_summary["avg_office_days"].round(1)

cols = st.columns(len(teams))
for i, (_, row) in enumerate(team_summary.iterrows()):
    pct = row["compliance_pct"]
    bg = "linear-gradient(135deg,#11998e,#38ef7d)" if pct >= 80 \
        else "linear-gradient(135deg,#f6d365,#fda085)" if pct >= 60 \
        else "linear-gradient(135deg,#f5576c,#f093fb)"
    with cols[i]:
        st.markdown(
            f"""
            <div style="background:{bg};color:white;padding:16px;border-radius:10px;text-align:center;">
              <div style="font-size:0.85rem;opacity:0.9">{row['department']}</div>
              <div style="font-weight:700;font-size:1rem">{row['team']}</div>
              <div style="font-size:2.4rem;font-weight:800">{pct}%</div>
              <div style="font-size:0.8rem">compliance rate</div>
              <div style="font-size:0.8rem;margin-top:4px">
                🏢 {row['avg_office_days']} avg office days
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)
st.divider()

# ── Weekly compliance trend per team ─────────────────────────────────────────
left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader("📈 Weekly Compliance Trend")
    fig = px.line(
        tw.sort_values("week_number"),
        x="week_number",
        y="compliance_pct",
        color="team",
        markers=True,
        labels={"week_number": "ISO Week", "compliance_pct": "% Compliant", "team": "Team"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.add_hrect(
        y0=80, y1=100,
        fillcolor="green", opacity=0.05,
        annotation_text="Good zone (≥80%)", annotation_position="right",
    )
    fig.update_layout(
        yaxis_range=[0, 110],
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=40, b=10),
        height=340,
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("👤 Employees Per Team")
    emp_count = (
        wf.groupby("team")["employee_id"].nunique().reset_index(name="employees")
    )
    fig2 = px.bar(
        emp_count,
        x="team",
        y="employees",
        color="team",
        text="employees",
        labels={"team": "", "employees": "# Employees"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig2.update_traces(textposition="outside")
    fig2.update_layout(showlegend=False, margin=dict(l=10, r=10, t=20, b=10), height=200)
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("📊 Avg Office Days per Team")
    fig3 = px.bar(
        tw.sort_values("week_number").groupby("team")["avg_office_days"].mean().reset_index(),
        x="team",
        y="avg_office_days",
        color="team",
        text="avg_office_days",
        labels={"team": "", "avg_office_days": "Avg Office Days"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig3.add_hline(y=3, line_dash="dash", line_color="red", annotation_text="Target: 3")
    fig3.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    fig3.update_layout(showlegend=False, margin=dict(l=10, r=10, t=20, b=10), height=200)
    st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ── Weekly compliance table (pivot) ──────────────────────────────────────────
st.subheader("📋 Compliance % — Weekly Pivot by Team")

pivot = tw.pivot_table(
    index="team", columns="week_number", values="compliance_pct", aggfunc="first"
).round(1)
pivot.columns = [f"Wk {c}" for c in pivot.columns]

# Add row totals
pivot["Overall"] = team_summary.set_index("team")["compliance_pct"]

def style_pct(val):
    if pd.isna(val):
        return ""
    if val >= 80:
        return "background-color:#d4edda;color:#155724;font-weight:600"
    if val >= 60:
        return "background-color:#fff3cd;color:#856404"
    return "background-color:#f8d7da;color:#721c24"

st.dataframe(
    pivot.style.map(style_pct).format("{:.1f}%", na_rep="—"),
    use_container_width=True,
)

st.divider()

# ── Month-over-month comparison ───────────────────────────────────────────────
st.subheader("📅 Month-over-Month Compliance (%)")

monthly_team = (
    tw.groupby(["team", "month_year"])
    .agg(
        compliant=("compliant_employees", "sum"),
        total=("total_employees", "sum"),
    )
    .reset_index()
)
monthly_team["compliance_pct"] = (monthly_team["compliant"] / monthly_team["total"] * 100).round(1)
monthly_team["month_label"] = monthly_team["month_year"].apply(
    lambda m: pd.Period(m).strftime("%b %Y")
)

fig4 = px.bar(
    monthly_team.sort_values("month_year"),
    x="month_label",
    y="compliance_pct",
    color="team",
    barmode="group",
    text="compliance_pct",
    labels={"month_label": "Month", "compliance_pct": "Compliance %", "team": "Team"},
    color_discrete_sequence=px.colors.qualitative.Set2,
)
fig4.add_hline(y=100, line_dash="dot", line_color="green")
fig4.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
fig4.update_layout(
    yaxis_range=[0, 115],
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(l=10, r=10, t=40, b=10),
    height=320,
)
st.plotly_chart(fig4, use_container_width=True)
