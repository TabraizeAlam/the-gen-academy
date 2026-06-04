# WFH → WFO Attendance Tracking Dashboard

A multi-page Streamlit dashboard built for **TechCorp Solutions** to manage and monitor the company-wide transition from remote work back to office attendance.

## Problem Statement

When a company mandates a return-to-office policy, HR and managers need visibility into who is complying, who is at risk, and whether patterns like strategic leave usage are undermining the policy. Manual tracking via spreadsheets doesn't scale.

## Policy Rules Tracked

| Rule | Value |
|---|---|
| Required office days per week | 3 days |
| Minimum login duration to count as an office day | 30 minutes |
| Leave adjustment (3+ leave days in a week) | Reduced requirement |
| Policy start date | 6 January 2025 |

## Scenarios Covered

### 1. Weekly Compliance Tracking
Each employee's week is evaluated: how many days did they come in, how many were required (adjusted for leave), and were they compliant? Results feed every view in the dashboard.

### 2. Leave-Adjusted Requirements
Employees on 3+ days of approved leave in a week have their office-day requirement automatically scaled down — so they're not penalised for genuine absence.

| Leave Days | Required Office Days |
|---|---|
| 0–2 | 3 |
| 3 | 2 |
| 4 | 1 |
| 5 | 0 |

### 3. Short Login Detection
Office days where an employee logged in for less than 30 minutes are excluded from the compliance count — preventing "badge and leave" behaviour from inflating compliance numbers.

### 4. Strategic Leave Analysis
The Individual Compliance page plots average leave days vs. average office days per employee. Employees who consistently combine high leave with low office attendance are surfaced for review.

### 5. Non-Compliance Streak Tracking
Consecutive weeks of non-compliance are tracked per employee. A configurable threshold (default: 2 weeks) triggers risk escalation, independent of overall compliance percentage.

### 6. At-Risk Employee Identification
Employees are automatically categorised into four risk tiers:

| Tier | Trigger |
|---|---|
| 🔴 Critical | Non-compliant last week AND on a non-compliant streak |
| 🟠 High Risk | On a streak OR (low compliance + non-compliant last week) |
| 🟡 Moderate | Below compliance threshold OR non-compliant last week |
| 🟢 On Track | None of the above |

### 7. Manager Accountability
The Manager View shows a manager's own compliance score alongside their direct reports — making it explicit when a manager is setting a poor example.

### 8. Public Holiday Awareness
The Analytics page marks public holidays on the daily occupancy chart so dips in attendance are understood in context.

## Dashboard Pages

| Page | Purpose |
|---|---|
| **Home** | KPI overview, weekly team compliance trend, department compliance bars, recent non-compliance flags |
| **Individual Compliance** | Per-employee score cards, non-compliance detail table, leave vs WFH scatter plot, export to Excel |
| **At-Risk Employees** | Risk tier panel, non-compliant streak bar chart, weekly trend grid for flagged employees |
| **Manager View** | Manager selector, direct-report compliance cards, weekly attendance detail, office-days trend line |
| **Analytics** | Daily office occupancy (with holiday markers), peak-day heatmap, WFH vs Office weekly stacked bar, login duration histogram, month-over-month compliance trend, leave patterns |

## Tech Stack

- **Python** — data processing and compliance logic
- **Streamlit** — multi-page web application
- **Pandas** — attendance and compliance computations
- **Plotly** — interactive charts
- **uv** — dependency and environment management

## Getting Started

```bash
uv run streamlit run app.py
```

## Data

- `data/employees.csv` — employee roster with team, department, manager, and role
- `data/public_holidays.csv` — public holidays for exclusion from occupancy charts
- `wfo_attendance_log.csv` — daily attendance log with login durations and day status (`IN_OFFICE`, `WFH`, `ON_LEAVE`)
- `config.yaml` — policy parameters (required days, minimum login duration, leave adjustment table)
