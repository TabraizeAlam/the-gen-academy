import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from utils.data_loader import load_attendance, load_public_holidays
from utils.compliance import compute_weekly_compliance

st.set_page_config(page_title="Analytics", page_icon="📊", layout="wide")

st.title("📊 Analytics & Insights")
st.caption("Occupancy trends, peak days, and behavioural patterns.")
st.divider()

att = load_attendance()
weekly = compute_weekly_compliance()
holidays = load_public_holidays()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔎 Filters")
    all_months = sorted(att["month_year"].unique())
    sel_months = st.multiselect("Month(s)", all_months, default=all_months)
    all_teams = sorted(att["team"].dropna().unique())
    sel_teams = st.multiselect("Team(s)", all_teams, default=all_teams)

att_f = att[att["month_year"].isin(sel_months) & att["team"].isin(sel_teams)]
wf = weekly[weekly["month_year"].isin(sel_months) & weekly["team"].isin(sel_teams)]

# ── Section 1: Daily Office Occupancy ────────────────────────────────────────
st.subheader("🏢 Daily Office Occupancy")

daily_occ = (
    att_f[att_f["day_status"] == "IN_OFFICE"]
    .groupby("log_date")["employee_id"]
    .nunique()
    .reset_index(name="in_office_count")
)
daily_occ["log_date"] = pd.to_datetime(daily_occ["log_date"])
total_emp = att_f["employee_id"].nunique()
daily_occ["occupancy_pct"] = (daily_occ["in_office_count"] / total_emp * 100).round(1)

if len(daily_occ):
    fig1 = go.Figure()
    fig1.add_trace(
        go.Bar(
            x=daily_occ["log_date"],
            y=daily_occ["in_office_count"],
            name="Headcount",
            marker_color="#4a90d9",
            hovertemplate="%{x|%b %d (%a)}<br>%{y} employees in office<extra></extra>",
        )
    )
    fig1.add_trace(
        go.Scatter(
            x=daily_occ["log_date"],
            y=daily_occ["occupancy_pct"],
            name="Occupancy %",
            yaxis="y2",
            line=dict(color="#fda085", width=2),
            mode="lines+markers",
            hovertemplate="%{y:.1f}%<extra></extra>",
        )
    )

    # Mark public holidays
    holiday_dates = holidays[
        (holidays["holiday_date"] >= daily_occ["log_date"].min())
        & (holidays["holiday_date"] <= daily_occ["log_date"].max())
    ]
    for _, hrow in holiday_dates.iterrows():
        fig1.add_vline(
            x=hrow["holiday_date"].timestamp() * 1000,
            line_dash="dot",
            line_color="purple",
            annotation_text=hrow["holiday_name"],
            annotation_position="top right",
        )

    fig1.update_layout(
        yaxis=dict(title="Employees In Office"),
        yaxis2=dict(title="Occupancy %", overlaying="y", side="right", range=[0, 110]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=40, b=10),
        height=320,
        hovermode="x unified",
    )
    st.plotly_chart(fig1, use_container_width=True)

st.divider()

# ── Section 2: Peak Days Heatmap ──────────────────────────────────────────────
left, right = st.columns(2, gap="large")

with left:
    st.subheader("📅 Peak Days Heatmap")
    st.caption("Which day-of-week × week combinations have highest office attendance?")

    heat_data = (
        att_f[att_f["day_status"] == "IN_OFFICE"]
        .groupby(["week_number", "day_of_week", "day_num"])["employee_id"]
        .nunique()
        .reset_index(name="count")
    )

    if len(heat_data):
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        pivot_heat = heat_data.pivot_table(
            index="day_of_week", columns="week_number", values="count", aggfunc="first"
        ).reindex(day_order)

        fig2 = px.imshow(
            pivot_heat,
            aspect="auto",
            color_continuous_scale=["#eaf4fb", "#4a90d9", "#003366"],
            labels={"x": "ISO Week", "y": "Day", "color": "Employees"},
            text_auto=True,
        )
        fig2.update_layout(
            margin=dict(l=10, r=10, t=20, b=10),
            height=280,
            coloraxis_colorbar=dict(title="Count"),
        )
        st.plotly_chart(fig2, use_container_width=True)

with right:
    st.subheader("📆 Most Popular Office Days")
    st.caption("Average number of employees in office per day of week.")

    day_avg = (
        att_f[att_f["day_status"] == "IN_OFFICE"]
        .groupby(["log_date", "day_of_week", "day_num"])["employee_id"]
        .nunique()
        .reset_index(name="count")
        .groupby(["day_of_week", "day_num"])["count"]
        .mean()
        .reset_index()
        .sort_values("day_num")
    )

    if len(day_avg):
        fig3 = px.bar(
            day_avg,
            x="day_of_week",
            y="count",
            text="count",
            color="count",
            color_continuous_scale=["#cce5ff", "#004085"],
            labels={"day_of_week": "Day", "count": "Avg Employees In Office"},
        )
        fig3.update_traces(texttemplate="%{text:.1f}", textposition="outside")
        fig3.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            margin=dict(l=10, r=10, t=20, b=10),
            height=280,
        )
        st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ── Section 3: WFH vs Office trend ───────────────────────────────────────────
st.subheader("💻 WFH vs Office — Weekly Trend")

status_weekly = (
    att_f[att_f["day_status"].isin(["IN_OFFICE", "WFH"])]
    .groupby(["week_number", "day_status"])["employee_id"]
    .count()
    .reset_index(name="days")
)

if len(status_weekly):
    fig4 = px.bar(
        status_weekly.sort_values("week_number"),
        x="week_number",
        y="days",
        color="day_status",
        barmode="stack",
        color_discrete_map={"IN_OFFICE": "#28a745", "WFH": "#4a90d9"},
        labels={
            "week_number": "ISO Week",
            "days": "Employee-Days",
            "day_status": "Status",
        },
    )
    fig4.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=40, b=10),
        height=280,
    )
    st.plotly_chart(fig4, use_container_width=True)

st.divider()

# ── Section 4: Login Duration Analysis ───────────────────────────────────────
left2, right2 = st.columns(2, gap="large")

with left2:
    st.subheader("⏱️ Login Duration Distribution")
    st.caption("Short office logins (< 30 min) don't count toward compliance.")

    dur_data = att_f[att_f["day_status"] == "IN_OFFICE"]["login_duration_mins"]
    if len(dur_data):
        fig5 = px.histogram(
            dur_data,
            nbins=30,
            labels={"value": "Duration (minutes)", "count": "Days"},
            color_discrete_sequence=["#4a90d9"],
        )
        fig5.add_vline(x=30, line_dash="dash", line_color="red", annotation_text="30 min threshold")
        fig5.update_layout(
            showlegend=False, margin=dict(l=10, r=10, t=20, b=10), height=260
        )
        st.plotly_chart(fig5, use_container_width=True)

with right2:
    st.subheader("📊 Avg Login Duration by Team")

    dur_team = (
        att_f[att_f["day_status"] == "IN_OFFICE"]
        .groupby("team")["login_duration_mins"]
        .mean()
        .reset_index()
    )
    dur_team["login_duration_mins"] = dur_team["login_duration_mins"].round(0)

    if len(dur_team):
        fig6 = px.bar(
            dur_team.sort_values("login_duration_mins", ascending=False),
            x="team",
            y="login_duration_mins",
            text="login_duration_mins",
            color="login_duration_mins",
            color_continuous_scale=["#4a90d9", "#003366"],
            labels={"team": "Team", "login_duration_mins": "Avg Minutes In Office"},
        )
        fig6.add_hline(
            y=30, line_dash="dash", line_color="red", annotation_text="Min threshold"
        )
        fig6.update_traces(texttemplate="%{text:.0f} min", textposition="outside")
        fig6.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            margin=dict(l=10, r=10, t=20, b=10),
            height=260,
        )
        st.plotly_chart(fig6, use_container_width=True)

st.divider()

# ── Section 5: Month-over-month compliance trend ──────────────────────────────
st.subheader("📅 Month-over-Month Compliance Trend")

monthly_comp = (
    wf[wf["required_days"] > 0]
    .groupby("month_year")
    .apply(lambda g: round(g["is_compliant"].mean() * 100, 1))
    .reset_index(name="compliance_pct")
)
monthly_comp["month_label"] = monthly_comp["month_year"].apply(
    lambda m: pd.Period(m).strftime("%b %Y")
)

if len(monthly_comp) > 1:
    fig7 = px.line(
        monthly_comp.sort_values("month_year"),
        x="month_label",
        y="compliance_pct",
        markers=True,
        text="compliance_pct",
        labels={"month_label": "Month", "compliance_pct": "Compliance %"},
        color_discrete_sequence=["#764ba2"],
    )
    fig7.update_traces(texttemplate="%{text:.1f}%", textposition="top center")
    fig7.add_hline(y=100, line_dash="dot", line_color="green", annotation_text="100%")
    fig7.update_layout(
        yaxis_range=[0, 115],
        margin=dict(l=10, r=10, t=20, b=10),
        height=260,
    )
    st.plotly_chart(fig7, use_container_width=True)
elif len(monthly_comp) == 1:
    st.info("Month-over-month trend requires data for 2+ months. Select all months to view.")

st.divider()

# ── Section 6: Leave summary ──────────────────────────────────────────────────
st.subheader("🗓️ Leave Patterns")

leave_by_emp = (
    att_f[att_f["day_status"] == "ON_LEAVE"]
    .groupby(["full_name", "team"])["log_date"]
    .count()
    .reset_index(name="leave_days")
    .sort_values("leave_days", ascending=False)
)

if len(leave_by_emp):
    fig8 = px.bar(
        leave_by_emp,
        x="full_name",
        y="leave_days",
        color="team",
        text="leave_days",
        labels={"full_name": "Employee", "leave_days": "Total Leave Days", "team": "Team"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig8.update_traces(textposition="outside")
    fig8.update_layout(
        xaxis_tickangle=-30,
        margin=dict(l=10, r=10, t=20, b=80),
        height=320,
        showlegend=True,
    )
    st.plotly_chart(fig8, use_container_width=True)
else:
    st.info("No leave days recorded in the selected period.")
