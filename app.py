import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import plotly.express as px
import pandas as pd

from utils.data_loader import load_attendance, load_config
from utils.compliance import compute_weekly_compliance, compute_employee_stats, compute_team_weekly

st.set_page_config(
    page_title="Attendance Dashboard — TechCorp",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
.kpi-card {
    padding: 1.2rem 1rem;
    border-radius: 10px;
    text-align: center;
    color: white;
}
.kpi-blue  { background: linear-gradient(135deg,#4facfe,#00f2fe); }
.kpi-green { background: linear-gradient(135deg,#11998e,#38ef7d); }
.kpi-red   { background: linear-gradient(135deg,#f5576c,#f093fb); }
.kpi-amber { background: linear-gradient(135deg,#f6d365,#fda085); }
.kpi-val { font-size: 2rem; font-weight: 800; }
.kpi-lbl { font-size: 0.82rem; opacity: .9; margin-top: 2px; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────
config = load_config()
company_name: str = config["company"]["name"]
req_days: int = config["policy"]["required_office_days"]
min_dur: int = config["policy"]["min_login_duration_minutes"]

st.title(f"🏢 {company_name}")
st.subheader("WFH → WFO Transition — Attendance Dashboard")
st.caption(
    f"Policy · **{req_days} office days / week** minimum · "
    f"minimum login **{min_dur} min** to count as office day"
)
st.divider()

# ── Load & compute ────────────────────────────────────────────────────────────
att = load_attendance()
weekly = compute_weekly_compliance()
emp_stats = compute_employee_stats()
team_weekly = compute_team_weekly()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔎 Filters")
    all_months = sorted(weekly["month_year"].unique())
    sel_months = st.multiselect("Month(s)", all_months, default=all_months, key="home_months")
    all_teams = sorted(weekly["team"].dropna().unique())
    sel_teams = st.multiselect("Team(s)", all_teams, default=all_teams, key="home_teams")
    st.divider()
    st.caption("Navigate using the pages in the sidebar above.")

wf = weekly[weekly["month_year"].isin(sel_months) & weekly["team"].isin(sel_teams)]
tw = team_weekly[team_weekly["month_year"].isin(sel_months) & team_weekly["team"].isin(sel_teams)]
es = emp_stats[emp_stats["team"].isin(sel_teams)]

# ── KPI cards ─────────────────────────────────────────────────────────────────
trackable = wf[wf["required_days"] > 0]
overall_pct = round(trackable["is_compliant"].mean() * 100, 1) if len(trackable) else 0.0
total_emp = wf["employee_id"].nunique()
nc_weeks = int((~trackable["is_compliant"]).sum())
avg_office = round(float(wf["office_days"].mean()), 1) if len(wf) else 0.0

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(
        f'<div class="kpi-card kpi-blue"><div class="kpi-val">{total_emp}</div>'
        f'<div class="kpi-lbl">Employees Tracked</div></div>',
        unsafe_allow_html=True,
    )
with c2:
    colour = "kpi-green" if overall_pct >= 75 else "kpi-amber" if overall_pct >= 50 else "kpi-red"
    st.markdown(
        f'<div class="kpi-card {colour}"><div class="kpi-val">{overall_pct}%</div>'
        f'<div class="kpi-lbl">Overall Compliance Rate</div></div>',
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f'<div class="kpi-card kpi-red"><div class="kpi-val">{nc_weeks}</div>'
        f'<div class="kpi-lbl">Non-Compliant Employee-Weeks</div></div>',
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        f'<div class="kpi-card kpi-amber"><div class="kpi-val">{avg_office}</div>'
        f'<div class="kpi-lbl">Avg Office Days / Week</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── Row 2: weekly compliance trend + employee scoreboard ─────────────────────
left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader("📈 Weekly Team Compliance (%)")
    if len(tw):
        fig = px.line(
            tw.sort_values("week_number"),
            x="week_number",
            y="compliance_pct",
            color="team",
            markers=True,
            labels={"week_number": "ISO Week", "compliance_pct": "Compliance %", "team": "Team"},
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.add_hline(
            y=100,
            line_dash="dot",
            line_color="green",
            annotation_text="100%",
            annotation_position="right",
        )
        fig.update_layout(
            yaxis_range=[0, 110],
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=10, r=10, t=40, b=10),
            height=320,
        )
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("🏅 Compliance Scores")

    def score_badge(pct: float) -> str:
        if pct >= 80:
            return f"🟢 {pct}%"
        if pct >= 60:
            return f"🟡 {pct}%"
        return f"🔴 {pct}%"

    def streak_badge(row) -> str:
        icon = "✅" if row["streak_type"] == "compliant" else "❌"
        return f"{icon} {row['current_streak']}w"

    display = es[["full_name", "team", "compliance_pct", "compliant_weeks", "total_weeks", "current_streak", "streak_type"]].copy()
    display["Score"] = display["compliance_pct"].apply(score_badge)
    display["Streak"] = display.apply(streak_badge, axis=1)
    st.dataframe(
        display[["full_name", "team", "Score", "compliant_weeks", "total_weeks", "Streak"]].rename(
            columns={
                "full_name": "Employee",
                "team": "Team",
                "compliant_weeks": "✅ Wks",
                "total_weeks": "Total",
            }
        ),
        use_container_width=True,
        hide_index=True,
        height=320,
    )

st.divider()

# ── Row 3: department compliance bars + recent flags ─────────────────────────
left2, right2 = st.columns([2, 3], gap="large")

with left2:
    st.subheader("🏢 Compliance by Department")
    dept_df = (
        trackable.groupby("department")
        .agg(compliant=("is_compliant", "sum"), total=("is_compliant", "count"))
        .reset_index()
    )
    dept_df["pct"] = (dept_df["compliant"] / dept_df["total"] * 100).round(1)
    fig2 = px.bar(
        dept_df,
        x="pct",
        y="department",
        orientation="h",
        text="pct",
        labels={"pct": "Compliance %", "department": ""},
        color="pct",
        color_continuous_scale=["#f5576c", "#fda085", "#38ef7d"],
        range_color=[0, 100],
    )
    fig2.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig2.update_layout(
        showlegend=False,
        coloraxis_showscale=False,
        margin=dict(l=10, r=40, t=10, b=10),
        height=200,
        xaxis_range=[0, 115],
    )
    st.plotly_chart(fig2, use_container_width=True)

with right2:
    st.subheader("⚠️ Recent Non-Compliance Flags")
    recent_nc = (
        wf[~wf["is_compliant"] & (wf["required_days"] > 0)]
        .sort_values("week_number", ascending=False)
        .head(15)
    )
    if len(recent_nc):
        disp = recent_nc[
            ["full_name", "team", "week_number", "week_start", "office_days", "required_days", "wfh_days", "leave_days"]
        ].copy()
        disp["week_start"] = disp["week_start"].dt.strftime("%b %d")
        disp["Gap"] = disp["required_days"] - disp["office_days"]
        st.dataframe(
            disp.rename(
                columns={
                    "full_name": "Employee",
                    "team": "Team",
                    "week_number": "Wk",
                    "week_start": "Week of",
                    "office_days": "Office",
                    "required_days": "Req'd",
                    "wfh_days": "WFH",
                    "leave_days": "Leave",
                }
            ),
            use_container_width=True,
            hide_index=True,
            height=220,
        )
    else:
        st.success("No non-compliance flags in selected period.")
