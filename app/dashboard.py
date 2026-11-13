"""Job Radar dashboard.

Run:  streamlit run app/dashboard.py
It reads data/job_radar.db if it exists (your real data, private), otherwise data/demo.db (fake data, public).
"""
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
REAL, DEMO = ROOT / "data" / "job_radar.db", ROOT / "data" / "demo.db"
DB = REAL if REAL.exists() else DEMO

BLUE = "#2a78d6"   # one hue for every single-series chart
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e7e6e2"
SOURCE_LABEL = {"indeed": "Indeed", "seek": "Seek", "linkedin": "LinkedIn", "email": "Direct email",
                "company_site": "Company website", "other": "Other"}
STATUS_LABEL = {"applied": "Applied", "viewed": "Viewed", "assessment": "Assessment", "interview": "Interview",
                "offer": "Offer", "rejected": "Rejected", "no_response": "No response (21+ days)"}

st.set_page_config(page_title="Job Radar", layout="wide")


@st.cache_data(ttl=600)
def q(sql: str) -> pd.DataFrame:
    with sqlite3.connect(DB) as con:
        return pd.read_sql(sql, con)


def style(fig, height=320):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=8, b=8), plot_bgcolor="white",
                      paper_bgcolor="white", font=dict(color=INK, size=13), showlegend=False)
    fig.update_xaxes(gridcolor=GRID, zeroline=False, title_font_color=MUTED, tickfont_color=MUTED)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, title_font_color=MUTED, tickfont_color=MUTED)
    return fig


status = q("SELECT * FROM v_current_status")
events = q("SELECT * FROM events")
funnel = q("SELECT stage, n FROM v_funnel ORDER BY stage_order")
by_source = q("SELECT * FROM v_by_source").assign(source=lambda d: d.source.map(SOURCE_LABEL))

st.title("Job Radar")
st.caption(("Demo data. Every company and email here is made up." if DB == DEMO else "Your real applications.")
           + " Updated daily by an AI agent that reads job emails, so nothing is typed in by hand.")

# ---- headline numbers -------------------------------------------------------
first_reply = (events[events.event_type != "applied"].groupby("application_id").event_date.min().rename("first_reply")
               .to_frame().join(status.set_index("application_id").applied_date).dropna())
days_to_reply = (pd.to_datetime(first_reply.first_reply) - pd.to_datetime(first_reply.applied_date)).dt.days

total = len(status)
replied = int(funnel.loc[funnel.stage == "Got any reply", "n"].iloc[0])
interviews = int(funnel.loc[funnel.stage == "Interview or test", "n"].iloc[0])
c1, c2, c3, c4 = st.columns(4)
c1.metric("Applications", total)
c2.metric("Got any reply", f"{replied / total:.0%}" if total else "–")
c3.metric("Reached interview or test", f"{interviews / total:.0%}" if total else "–")
c4.metric("Median days to first reply", f"{days_to_reply.median():.0f}" if len(days_to_reply) else "–")

# ---- funnel + sources -------------------------------------------------------
left, right = st.columns(2)
with left:
    st.subheader("How far applications get")
    fig = px.bar(funnel, x="n", y="stage", orientation="h", text="n", color_discrete_sequence=[BLUE])
    fig.update_layout(bargap=0.45)
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title="Applications")
    fig.update_traces(textposition="outside", hovertemplate="%{y}: %{x}<extra></extra>")
    st.plotly_chart(style(fig), width="stretch")

with right:
    st.subheader("Which job sites get you interviews")
    src = by_source.sort_values("interview_rate_pct")
    src["label"] = src.apply(lambda r: f"{r.interview_rate_pct:.0f}%  (of {r.applications})", axis=1)
    fig = px.bar(src, x="interview_rate_pct", y="source", orientation="h", text="label",
                 color_discrete_sequence=[BLUE])
    fig.update_layout(bargap=0.45)
    fig.update_xaxes(title="Applications that reached interview or test (%)", range=[0, max(src.interview_rate_pct.max() * 1.4, 10)])
    fig.update_yaxes(title=None)
    fig.update_traces(textposition="outside",
                      hovertemplate="%{y}: %{x:.1f}% of %{customdata[0]} applications<extra></extra>",
                      customdata=src[["applications"]])
    st.plotly_chart(style(fig), width="stretch")
    st.caption("Small samples swing a lot. Treat sites with under 10 applications as a guess.")

# ---- applications over time --------------------------------------------------
st.subheader("Applications per week")
weekly = (status.dropna(subset=["applied_date"]).assign(week=lambda d: pd.to_datetime(d.applied_date).dt.to_period("W").dt.start_time)
          .groupby("week").size().rename("applications").reset_index())
fig = px.line(weekly, x="week", y="applications", markers=True, color_discrete_sequence=[BLUE])
fig.update_traces(line_width=2, marker_size=8, hovertemplate="Week of %{x|%d %b}: %{y}<extra></extra>")
fig.update_xaxes(title=None)
fig.update_yaxes(title="Applications", rangemode="tozero")
st.plotly_chart(style(fig, 260), width="stretch")

# ---- the list -----------------------------------------------------------------
st.subheader("Every application")
only_review = st.toggle("Only show ones the AI wasn't sure about", value=False)
table = status.assign(status=status.status.map(STATUS_LABEL), source=status.source.map(SOURCE_LABEL),
                      job_type=status.job_type.str.replace("_", " ").str.capitalize(),
                      needs_review=status.needs_review.astype(bool))
if only_review:
    table = table[table.needs_review]
table = (table.drop(columns=["application_id"]).sort_values("applied_date", ascending=False)
         .rename(columns={"company": "Company", "role": "Role", "source": "Applied via", "job_type": "Job type",
                          "applied_date": "Applied", "last_update": "Last update", "status": "Status",
                          "days_since_applied": "Days since applied", "needs_review": "Check this"}))
st.dataframe(table, width="stretch", hide_index=True)
