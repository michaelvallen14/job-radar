"""Job Radar dashboard.

Run:  streamlit run app/dashboard.py
It reads data/job_radar.db if it exists (your real data, private), otherwise data/demo.db (fake data, public).
"""
import calendar
import html
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
REAL, DEMO = ROOT / "data" / "job_radar.db", ROOT / "data" / "demo.db"
DB = REAL if REAL.exists() else DEMO
NAME = "Michael"

BLUE = "#3987e5"   # one hue for every single-series chart (the dark-mode step of #2a78d6)
INK, MUTED, GRID = "#f0efec", "#898781", "#2c2c2a"
SURFACE = "#1a1a19"  # card background; charts draw on the same color so they sit flush
SOURCE_LABEL = {"indeed": "Indeed", "seek": "Seek", "linkedin": "LinkedIn", "email": "Direct email",
                "company_site": "Company website", "other": "Other"}
# status -> (label, mark color, pill background). Colors passed the dataviz palette check;
# every pill and legend entry also carries a text label, so color never works alone.
STATUS = {
    "applied":     ("Applied", BLUE, "rgba(57,135,229,.16)"),
    "viewed":      ("Viewed", BLUE, "rgba(57,135,229,.16)"),
    "assessment":  ("Assessment", "#c98500", "rgba(201,133,0,.18)"),
    "interview":   ("Interview", "#c98500", "rgba(201,133,0,.18)"),
    "offer":       ("Offer", "#199e70", "rgba(25,158,112,.18)"),
    "rejected":    ("Rejected", "#e66767", "rgba(230,103,103,.16)"),
    "no_response": ("No response", "#898781", "rgba(137,135,129,.18)"),
}
# The donut groups statuses into five slices (a donut stays readable up to about six).
GROUP = {"applied": "Waiting", "viewed": "Waiting", "assessment": "Interview", "interview": "Interview",
         "offer": "Offer", "no_response": "No response", "rejected": "Rejected"}
GROUP_COLOR = {"Waiting": BLUE, "Interview": "#c98500", "Offer": "#199e70",
               "No response": "#898781", "Rejected": "#e66767"}

st.set_page_config(page_title="Job Radar", page_icon="◉", layout="wide")

st.markdown("""
<style>
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2.2rem; max-width: 1320px; }
/* Containers created with key="card_..." become cards */
div[class*="st-key-card"] { background: #1a1a19; border: 1px solid rgba(255,255,255,.08); border-radius: 16px;
                            padding: 20px 22px; }
.jr-title { font-size: 2rem; font-weight: 600; margin: 0; line-height: 1.2; color: #f0efec; letter-spacing: -.01em; }
.jr-sub { color: #898781; margin: 4px 0 0; font-size: 1rem; }
.jr-badge { float: right; margin-top: 10px; border: 1px solid rgba(255,255,255,.10); border-radius: 999px;
            padding: 7px 14px; color: #898781; font-size: .85rem; }
.jr-badge b { color: #f0efec; font-weight: 500; }
.jr-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #199e70; margin-right: 8px; }
.jr-h { font-size: 1.05rem; font-weight: 600; margin: 0 0 14px; color: #f0efec; }
.jr-h span { color: #898781; font-weight: 400; }
.jr-tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.jr-tile { background: #141413; border: 1px solid rgba(255,255,255,.06); border-radius: 12px; padding: 14px 16px; }
.jr-tile .v { font-size: 1.9rem; font-weight: 600; line-height: 1.1; color: #f0efec; }
.jr-tile .of { font-size: .95rem; font-weight: 400; color: #898781; }
.jr-tile .l { margin-top: 4px; color: #c3c2b7; font-size: .92rem; }
.jr-tile .d { margin-top: 6px; color: #898781; font-size: .8rem; }
.up { color: #0ca30c; } .down { color: #e66767; } .flat { color: #898781; }
.jr-note { background: #1a1a19; border: 1px solid rgba(255,255,255,.08); border-left: 3px solid #3987e5;
           border-radius: 16px; padding: 18px 22px; }
.jr-note h4 { margin: 0 0 6px; font-weight: 600; font-size: 1rem; color: #f0efec; }
.jr-note p { margin: 0; color: #c3c2b7; font-size: .95rem; line-height: 1.5; }
.jr-notif { display: flex; gap: 12px; align-items: flex-start; padding: 10px 0; font-size: .9rem; line-height: 1.45;
            color: #c3c2b7; border-bottom: 1px solid rgba(255,255,255,.06); }
.jr-notif:last-child { border-bottom: 0; }
.jr-notif b { color: #f0efec; font-weight: 500; }
.jr-notif .i { flex: none; width: 26px; height: 26px; border-radius: 50%; display: inline-flex; align-items: center;
               justify-content: center; background: #262624; color: #c3c2b7; font-size: .8rem; }
.jr-table { max-height: 440px; overflow-y: auto; }
.jr-table table { width: 100%; border-collapse: collapse; font-size: .88rem; }
.jr-table th { position: sticky; top: 0; background: #1a1a19; text-align: left; font-weight: 500; padding: 10px 8px;
               color: #898781; border-bottom: 1px solid rgba(255,255,255,.08); }
.jr-table td { padding: 11px 8px; border-bottom: 1px solid rgba(255,255,255,.05); color: #c3c2b7; }
.jr-table td b { color: #f0efec; font-weight: 500; }
.jr-table td.muted { color: #898781; }
.jr-table tr:hover td { background: #20201f; }
.pill { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 2px 10px;
        font-size: .78rem; font-weight: 500; color: #f0efec; white-space: nowrap; }
.pill i { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.flag { color: #e66767; margin-left: 5px; cursor: help; }
.jr-cal { width: 100%; border-collapse: collapse; text-align: center; font-size: .88rem; }
.jr-cal th { font-weight: 500; padding: 6px 0; color: #898781; }
.jr-cal td { padding: 3px 0; color: #c3c2b7; }
.jr-cal .day { display: inline-flex; align-items: center; justify-content: center;
               width: 32px; height: 32px; border-radius: 50%; position: relative; }
.jr-cal .out { color: #4a4945; }
.jr-cal .has { background: #3987e5; color: #fff; font-weight: 600; }
.jr-cal .today { box-shadow: 0 0 0 1.5px #f0efec; }
.jr-cal .reply::after { content: ""; position: absolute; bottom: 3px; width: 4px; height: 4px; border-radius: 50%;
                        background: #f0efec; }
.jr-legend { margin-top: 12px; color: #898781; font-size: .8rem; display: flex; gap: 16px; justify-content: center; }
.jr-legend i { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; vertical-align: -1px; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=600)
def q(sql: str, params: dict | None = None) -> pd.DataFrame:
    with sqlite3.connect(DB) as con:
        return pd.read_sql(sql, con, params=params)


def esc(v) -> str:
    # Company and role names come from emails, so escape them before putting them in HTML.
    return html.escape("" if v is None or pd.isna(v) else str(v))


def style(fig, height=300):
    fig.update_layout(height=height, margin=dict(l=4, r=4, t=4, b=4), plot_bgcolor=SURFACE,
                      paper_bgcolor=SURFACE, font=dict(color=INK, size=13), showlegend=False, barcornerradius=4)
    fig.update_xaxes(gridcolor=GRID, zeroline=False, title_font_color=MUTED, tickfont_color=MUTED)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, title_font_color=MUTED, tickfont_color=MUTED)
    return fig


PLOT_CONFIG = {"displayModeBar": False}

today = date.today()
this_month = today.strftime("%Y-%m")
last_month = (today.replace(day=1) - pd.Timedelta(days=1)).strftime("%Y-%m")
latest = q("SELECT MAX(event_date) AS d FROM events").d.iloc[0]
last_email = pd.to_datetime(latest).strftime("%d %b %Y") if latest else "never"

# ---- header ---------------------------------------------------------------------
badge = ("Demo data. Every company here is made up" if DB == DEMO
         else f"Updated by the AI agent &middot; latest email <b>{last_email}</b>")
st.markdown(f"""
<div class="jr-badge"><span class="jr-dot"></span>{badge}</div>
<p class="jr-title">Welcome back, {NAME}</p>
<p class="jr-sub">Here's an overview of your job search, filled in from your inbox.</p>
""", unsafe_allow_html=True)
# Deselecting a segmented control returns None, so fall back to All.
group = st.segmented_control("Job type", ["All", "Casual", "Office"], default="All",
                             label_visibility="collapsed") or "All"
st.write("")

# Every query below takes the same filter. job_group comes from v_current_status in sql/schema.sql.
G = {"g": group}
WHERE_GROUP = "(:g = 'All' OR job_group = :g)"
status = q(f"""SELECT s.*, n.next_step, n.follow_up FROM v_current_status s
               JOIN v_next_step n USING (application_id) WHERE {WHERE_GROUP}""", G)
events = q(f"""SELECT e.* FROM events e JOIN v_current_status USING (application_id)
               WHERE {WHERE_GROUP}""", G)
# The views hold counts per job_group; adding them up gives the numbers for the chosen group.
funnel = q(f"""SELECT stage, SUM(n) AS n FROM v_funnel WHERE {WHERE_GROUP}
               GROUP BY stage, stage_order ORDER BY stage_order""", G)
by_source = q(f"""SELECT source, SUM(applications) AS applications, SUM(got_real_reply) AS got_real_reply,
                         ROUND(100.0 * SUM(got_real_reply) / SUM(applications)) AS reply_rate_pct
                  FROM v_by_source WHERE {WHERE_GROUP}
                  GROUP BY source ORDER BY applications DESC""", G).assign(source=lambda d: d.source.map(SOURCE_LABEL))

if status.empty:
    st.info(f"No {group.lower()} applications yet. Pick another job type above.")
    st.stop()

applied_month = status.applied_date.str[:7]
all_total = int(q("SELECT COUNT(*) AS n FROM applications").n.iloc[0])

total = len(status)
replied = int(funnel.loc[funnel.stage == "Got any reply", "n"].iloc[0])
interviews = int(funnel.loc[funnel.stage == "Interview or test", "n"].iloc[0])
rejected = int((status.status == "rejected").sum())
new_this_month = int((applied_month == this_month).sum())
new_last_month = int((applied_month == last_month).sum())


def of(n: int) -> str:
    # Sample size next to each headline number: small groups give shaky percentages.
    return f'<span class="of"> of {n}</span>'


def delta(n: int, what: str, up_is_good: bool = True) -> str:
    if n == 0:
        return f'<span class="flat">&mdash;</span> no {what} this month'
    cls = "up" if up_is_good else "down"
    return f'<span class="{cls}">&#9650;</span> {n} {what} this month'


# ---- progress card + right column -------------------------------------------------
left, right = st.columns([2.15, 1], gap="medium")
with left:
    with st.container(key="card_progress"):
        st.markdown(f'<p class="jr-h">Your job hunt progress <span>&middot; {today.strftime("%B %Y")}</span></p>',
                    unsafe_allow_html=True)
        tiles, donut = st.columns([1.15, 1], gap="medium")
        reply_rate = f"{replied / total:.0%} of applications" if total else "&mdash;"
        rejected_now = int(((status.status == "rejected") & (status.last_update.str[:7] == this_month)).sum())
        tiles.markdown(f"""
        <div class="jr-tiles">
          <div class="jr-tile"><div class="v">{total}{of(all_total) if group != "All" else ""}</div>
            <div class="l">{"Total" if group == "All" else group} applications</div>
            <div class="d">{delta(new_this_month, "new")} (last month {new_last_month})</div></div>
          <div class="jr-tile"><div class="v">{replied}{of(total)}</div><div class="l">Got a reply</div>
            <div class="d">{reply_rate}</div></div>
          <div class="jr-tile"><div class="v">{interviews}{of(total)}</div><div class="l">Interviews or tests</div>
            <div class="d">{'<span class="flat">&mdash;</span> none yet, keep going' if interviews == 0
                            else f'{interviews / total:.0%} of applications'}</div></div>
          <div class="jr-tile"><div class="v">{rejected}{of(total)}</div><div class="l">Rejected</div>
            <div class="d">{delta(rejected_now, "new", up_is_good=False)}</div></div>
        </div>""", unsafe_allow_html=True)
        if total < 10:
            tiles.caption(f"Only {total} applications in this group, so treat the percentages as a rough guess.")

        groups = status.status.map(GROUP).value_counts().reindex(list(GROUP_COLOR)).fillna(0).astype(int)
        groups = groups[groups > 0]
        fig = go.Figure(go.Pie(labels=groups.index, values=groups.values, hole=.68, sort=False, direction="clockwise",
                               marker=dict(colors=[GROUP_COLOR[g] for g in groups.index],
                                           line=dict(color=SURFACE, width=2)),
                               textinfo="none", hovertemplate="%{label}: %{value} (%{percent})<extra></extra>"))
        fig.add_annotation(text=f"<span style='font-size:28px'>{total}</span><br><span style='color:{MUTED}'>applications</span>",
                           showarrow=False, font=dict(color=INK, size=13))
        fig.update_layout(height=260, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor=SURFACE, showlegend=True,
                          legend=dict(orientation="h", x=.5, xanchor="center", y=-.05, font=dict(color=MUTED)))
        donut.plotly_chart(fig, width="stretch", config=PLOT_CONFIG)

with right:
    st.markdown(f"""<div class="jr-note"><h4>Remember!</h4>
      <p>You've sent {total} applications. Every reply, even a no, means your search is moving.</p></div>""",
                unsafe_allow_html=True)
    st.write("")
    with st.container(key="card_notifications"):
        st.markdown('<p class="jr-h">Notifications</p>', unsafe_allow_html=True)
        notes = []
        chase = status[status.follow_up == 1].sort_values("days_since_applied", ascending=False)
        for _, r in chase.head(2).iterrows():
            notes.append(("↻", f"Follow up with <b>{esc(r.company)}</b> about {esc(r.role)}. "
                                f"You applied {r.days_since_applied} days ago."))
        if len(chase) > 2:
            notes.append(("+", f"{len(chase) - 2} more applications are ready for a follow-up."))
        waiting = status[status.status.isin(["applied", "viewed"]) & (status.follow_up == 0)]
        if len(waiting):
            first = waiting.next_step.min().replace("Follow up on ", "")
            notes.append(("◷", f"{len(waiting)} applications are waiting for a reply. First follow-up due {first}."))
        latest_reject = status[status.status == "rejected"].sort_values("last_update").tail(1)
        for _, r in latest_reject.iterrows():
            notes.append(("✕", f"Latest reply: <b>{esc(r.company)}</b> said no on {r.last_update}. On to the next one."))
        notes.append(("↗", f"You applied to {new_this_month} jobs this month. Keep going!"))
        st.markdown("".join(f'<div class="jr-notif"><span class="i">{i}</span><span>{t}</span></div>'
                            for i, t in notes[:4]), unsafe_allow_html=True)

st.write("")

# ---- application list + calendar ----------------------------------------------------
left, right = st.columns([2.15, 1], gap="medium")
with left:
    with st.container(key="card_table"):
        f1, f2 = st.columns([1.6, 1])
        choice = f1.segmented_control("Filter", ["All", "Waiting", "Interviews", "Offers", "Rejected", "No response",
                                                 "Needs a check"], default="All", label_visibility="collapsed")
        search = f2.text_input("Search", placeholder="Search company or role", label_visibility="collapsed")
        wanted = {"Waiting": ["applied", "viewed"], "Interviews": ["assessment", "interview"], "Offers": ["offer"],
                  "Rejected": ["rejected"], "No response": ["no_response"]}
        rows = status
        if choice in wanted:
            rows = rows[rows.status.isin(wanted[choice])]
        elif choice == "Needs a check":
            rows = rows[rows.needs_review == 1]
        if search:
            hit = (rows.company.str.contains(search, case=False, regex=False)
                   | rows.role.fillna("").str.contains(search, case=False, regex=False))
            rows = rows[hit]
        rows = rows.sort_values(["applied_date", "last_update"], ascending=False, na_position="last")

        body = []
        for _, r in rows.iterrows():
            label, color, bg = STATUS[r.status]
            flag = ('<span class="flag" title="The AI was not sure about this one. Check it by hand.">&#9873;</span>'
                    if r.needs_review else "")
            applied = pd.to_datetime(r.applied_date).strftime("%d %b %Y") if pd.notna(r.applied_date) else "&mdash;"
            body.append(f"<tr><td><b>{esc(r.company)}</b>{flag}</td><td>{esc(r.role)}</td>"
                        f"<td class='muted'>{SOURCE_LABEL.get(r.source, esc(r.source))}</td>"
                        f"<td><span class='pill' style='background:{bg}'><i style='background:{color}'></i>{label}</span></td>"
                        f"<td class='muted'>{applied}</td><td class='muted'>{esc(r.next_step)}</td></tr>")
        st.markdown(f"""<div class="jr-table"><table>
          <thead><tr><th>Company</th><th>Role</th><th>Applied via</th><th>Status</th><th>Date applied</th>
          <th>Next step</th></tr></thead><tbody>{''.join(body)}</tbody></table></div>""", unsafe_allow_html=True)
        st.caption(f"Showing {len(rows)} of {total} applications. ⚑ means the AI was not sure, so check it by hand.")

with right:
    with st.container(key="card_calendar"):
        applied_days = status.applied_date.dropna().value_counts().to_dict()
        reply_days = events[events.event_type != "applied"].event_date.value_counts().to_dict()
        months = sorted({d[:7] for d in list(applied_days) + list(reply_days)} | {this_month}, reverse=True)
        month = st.selectbox("Month", months, format_func=lambda m: pd.Timestamp(m + "-01").strftime("%B %Y"),
                             label_visibility="collapsed")
        y, m = map(int, month.split("-"))
        cells = []
        for week in calendar.Calendar(firstweekday=6).monthdatescalendar(y, m):
            tds = []
            for d in week:
                key = d.isoformat()
                n, r = applied_days.get(key, 0), reply_days.get(key, 0)
                cls = ["day"] + (["out"] if d.month != m else []) + (["has"] if n and d.month == m else []) \
                    + (["reply"] if r and d.month == m else []) + (["today"] if d == today else [])
                tip = ", ".join(t for t in [f"{n} applied" if n else "", f"{r} replies" if r else ""] if t)
                tds.append(f'<td><span class="{" ".join(cls)}" title="{tip}">{d.day}</span></td>')
            cells.append("<tr>" + "".join(tds) + "</tr>")
        heads = "".join(f'<th class="{"sun" if i == 0 else ""}">{d}</th>'
                        for i, d in enumerate(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]))
        st.markdown(f"""<p class="jr-h">Activity <span>&middot; {pd.Timestamp(month + "-01").strftime("%B %Y")}</span></p>
          <table class="jr-cal"><tr>{heads}</tr>{''.join(cells)}</table>
          <div class="jr-legend"><span><i style="background:{BLUE}"></i>Applied</span>
          <span><i style="background:{INK};width:5px;height:5px"></i>Got a reply</span>
          <span><i style="box-shadow:0 0 0 1.5px {INK}"></i>Today</span></div>""", unsafe_allow_html=True)

st.write("")

# ---- insights -----------------------------------------------------------------------
c1, c2, c3 = st.columns(3, gap="medium")
with c1, st.container(key="card_funnel"):
    st.markdown('<p class="jr-h">How far applications get</p>', unsafe_allow_html=True)
    fun = funnel.assign(label=lambda d: d.n.astype(str) + (" · " + (100 * d.n / max(total, 1)).round().astype(int).astype(str) + "%"))
    fig = px.bar(fun, x="n", y="stage", orientation="h", text="label", color_discrete_sequence=[BLUE])
    fig.update_layout(bargap=.45)
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title=None, range=[0, max(fun.n.max() * 1.35, 1)])
    fig.update_traces(textposition="outside", textfont_color=MUTED, hovertemplate="%{y}: %{x}<extra></extra>")
    st.plotly_chart(style(fig, 260), width="stretch", config=PLOT_CONFIG)

with c2, st.container(key="card_sources"):
    st.markdown('<p class="jr-h">Replies by job site</p>', unsafe_allow_html=True)
    src = by_source.rename(columns={"reply_rate_pct": "rate"}).sort_values("rate")
    src["label"] = src.apply(lambda r: f"{r.rate:.0f}%  ({r.got_real_reply} of {r.applications})", axis=1)
    fig = px.bar(src, x="rate", y="source", orientation="h", text="label", color_discrete_sequence=[BLUE])
    fig.update_layout(bargap=.45)
    fig.update_xaxes(title=None, range=[0, max(src.rate.max() * 1.6, 10)], ticksuffix="%")
    fig.update_yaxes(title=None)
    fig.update_traces(textposition="outside", textfont_color=MUTED, hovertemplate="%{y}: %{x:.0f}%<extra></extra>")
    st.plotly_chart(style(fig, 260), width="stretch", config=PLOT_CONFIG)
    st.caption("A real reply means anything past \"viewed\". Small numbers swing a lot.")

with c3, st.container(key="card_weekly"):
    st.markdown('<p class="jr-h">Applications per week</p>', unsafe_allow_html=True)
    weekly = (status.dropna(subset=["applied_date"])
              .assign(week=lambda d: pd.to_datetime(d.applied_date).dt.to_period("W").dt.start_time)
              .groupby("week").size().rename("applications").reset_index())
    fig = px.bar(weekly, x="week", y="applications", color_discrete_sequence=[BLUE])
    fig.update_layout(bargap=.35)
    fig.update_traces(hovertemplate="Week of %{x|%d %b}: %{y}<extra></extra>")
    fig.update_xaxes(title=None, tickformat="%d %b")
    fig.update_yaxes(title=None, rangemode="tozero")
    st.plotly_chart(style(fig, 260), width="stretch", config=PLOT_CONFIG)
