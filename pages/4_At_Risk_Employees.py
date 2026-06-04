import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import plotly.express as px
import pandas as pd

from utils.compliance import compute_weekly_compliance, compute_employee_stats

st.set_page_config(page_title="At-Risk Employees", page_icon="⚠️", layout="wide")

st.title("⚠️ At-Risk Employees")
st.caption(
    "Employees trending toward or already in non-compliance. "
    "Based on the most recent weeks of data."
)
st.divider()

weekly = compute_weekly_compliance()
emp_stats = compute_employee_stats()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔎 Filters")
    all_teams = sorted(weekly["team"].dropna().unique())
    sel_teams = st.multiselect("Team(s)", all_teams, default=all_teams)
    risk_threshold = st.slider(
        "Flag employees below compliance %", min_value=50, max_value=100, value=80, step=5
    )
    streak_threshold = st.slider(
        "Non-compliant streak ≥ weeks", min_value=1, max_value=8, value=2
    )

# ── Most recent week analysis ─────────────────────────────────────────────────
last_week = int(weekly["week_number"].max())
last_week_start = weekly[weekly["week_number"] == last_week]["week_start"].iloc[0]
last_week_label = pd.Timestamp(last_week_start).strftime("%b %d, %Y")

st.info(f"**Latest data:** ISO Week {last_week} · week of {last_week_label}")

lw = weekly[weekly["week_number"] == last_week]
lw_filtered = lw[lw["team"].isin(sel_teams)]

# KPIs for last week
nc_last = lw_filtered[~lw_filtered["is_compliant"] & (lw_filtered["required_days"] > 0)]
on_leave_last = lw_filtered[lw_filtered["leave_days"] >= lw_filtered["total_days"]]
total_last = lw_filtered["employee_id"].nunique()
compliant_last = int(lw_filtered["is_compliant"].sum())

k1, k2, k3, k4 = st.columns(4)
k1.metric("Employees (last week)", total_last)
k2.metric("Compliant", compliant_last, delta=f"{compliant_last - total_last} vs full compliance")
k3.metric("Non-Compliant", len(nc_last))
k4.metric("Fully on Leave", len(on_leave_last))

st.markdown("<br>", unsafe_allow_html=True)

# ── Risk categories ───────────────────────────────────────────────────────────
es = emp_stats[emp_stats["team"].isin(sel_teams)].copy()

def risk_level(row) -> tuple[str, str]:
    """Return (risk_label, color) for an employee."""
    is_nc_streak = row["streak_type"] == "non_compliant" and row["current_streak"] >= streak_threshold
    is_low_compliance = row["compliance_pct"] < risk_threshold
    last_week_nc = row["employee_id"] in nc_last["employee_id"].values

    if is_nc_streak and last_week_nc:
        return "🔴 Critical", "#f8d7da"
    if is_nc_streak or (last_week_nc and is_low_compliance):
        return "🟠 High Risk", "#fde8d0"
    if is_low_compliance or last_week_nc:
        return "🟡 Moderate", "#fff3cd"
    return "🟢 On Track", "#d4edda"

es[["risk_label", "risk_color"]] = es.apply(
    lambda r: pd.Series(risk_level(r)), axis=1
)

# ── Critical & High-risk employees panel ─────────────────────────────────────
at_risk = es[es["risk_label"].isin(["🔴 Critical", "🟠 High Risk", "🟡 Moderate"])].copy()
on_track = es[es["risk_label"] == "🟢 On Track"].copy()

st.subheader(f"🚨 Flagged Employees ({len(at_risk)} of {len(es)})")

if len(at_risk):
    for _, row in at_risk.sort_values("risk_label").iterrows():
        bg = row["risk_color"]
        streak_icon = "❌" if row["streak_type"] == "non_compliant" else "✅"
        nc_badge = "⚠️ non-compliant last week" if row["employee_id"] in nc_last["employee_id"].values else ""
        role_icon = "👔" if row["role"] == "manager" else "⭐" if row["role"] == "senior_employee" else "👤"

        with st.container():
            st.markdown(
                f"""
                <div style="background:{bg};border-radius:8px;padding:12px 16px;margin-bottom:8px;
                            display:flex;align-items:center;gap:16px;">
                  <div style="flex:0 0 30px;font-size:1.4rem">{row['risk_label'].split()[0]}</div>
                  <div style="flex:1">
                    <div style="font-weight:700">{role_icon} {row['full_name']}</div>
                    <div style="font-size:0.8rem;color:#555">{row['department']} · {row['team']}</div>
                  </div>
                  <div style="text-align:center;min-width:80px">
                    <div style="font-size:1.5rem;font-weight:800">{row['compliance_pct']}%</div>
                    <div style="font-size:0.75rem">compliance</div>
                  </div>
                  <div style="text-align:center;min-width:100px">
                    <div style="font-weight:700">{streak_icon} {row['current_streak']}w streak</div>
                    <div style="font-size:0.75rem">{row['streak_type'].replace('_',' ')}</div>
                  </div>
                  <div style="text-align:center;min-width:80px">
                    <div style="font-weight:600">{row['compliant_weeks']}/{row['total_weeks']}</div>
                    <div style="font-size:0.75rem">compliant wks</div>
                  </div>
                  <div style="text-align:right;min-width:100px;font-size:0.8rem;color:#c00">
                    {nc_badge}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    st.success("No at-risk employees under current thresholds.")

st.divider()

# ── Streak tracker chart ──────────────────────────────────────────────────────
st.subheader("📊 Non-Compliance Streak Tracker")

streak_data = es[es["streak_type"] == "non_compliant"][
    ["full_name", "team", "current_streak", "compliance_pct"]
].sort_values("current_streak", ascending=False)

if len(streak_data):
    fig = px.bar(
        streak_data,
        x="full_name",
        y="current_streak",
        color="compliance_pct",
        text="current_streak",
        hover_data={"team": True, "compliance_pct": True},
        labels={
            "full_name": "Employee",
            "current_streak": "Non-Compliant Streak (weeks)",
            "compliance_pct": "Compliance %",
        },
        color_continuous_scale=["#dc3545", "#ffc107", "#28a745"],
        range_color=[0, 100],
    )
    fig.update_traces(texttemplate="%{text}w", textposition="outside")
    fig.add_hline(
        y=streak_threshold,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Risk threshold ({streak_threshold}w)",
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        height=300,
        xaxis_tickangle=-30,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.success("No employees currently on a non-compliant streak.")

st.divider()

# ── Weekly compliance per at-risk employee ────────────────────────────────────
st.subheader("📉 Weekly Compliance Trend — At-Risk Employees")

at_risk_ids = at_risk["employee_id"].tolist()
if at_risk_ids:
    trend_data = weekly[weekly["employee_id"].isin(at_risk_ids)].copy()
    trend_data["Compliance"] = trend_data["is_compliant"].apply(
        lambda c: "Compliant" if c else "Non-Compliant"
    )
    fig2 = px.scatter(
        trend_data,
        x="week_number",
        y="full_name",
        color="Compliance",
        symbol="Compliance",
        size="office_days",
        size_max=18,
        hover_data={
            "office_days": True,
            "required_days": True,
            "wfh_days": True,
            "leave_days": True,
        },
        color_discrete_map={"Compliant": "#28a745", "Non-Compliant": "#dc3545"},
        labels={"week_number": "ISO Week", "full_name": "Employee"},
    )
    fig2.update_layout(
        margin=dict(l=10, r=10, t=20, b=10),
        height=max(200, len(at_risk_ids) * 50 + 80),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("Dot size = office days that week")

st.divider()

# ── On-track employees ────────────────────────────────────────────────────────
with st.expander(f"✅ On-Track Employees ({len(on_track)})", expanded=False):
    st.dataframe(
        on_track[["full_name", "team", "compliance_pct", "compliant_weeks", "total_weeks", "current_streak"]].rename(
            columns={
                "full_name": "Employee",
                "team": "Team",
                "compliance_pct": "Compliance %",
                "compliant_weeks": "✅ Weeks",
                "total_weeks": "Total",
                "current_streak": "Streak (wks)",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
