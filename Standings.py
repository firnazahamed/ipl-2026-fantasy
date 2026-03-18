import streamlit as st
import pandas as pd
from helpers import read_file

st.set_page_config(layout="wide")

bucket_name = "summer-is-coming-2026"

standings_df = read_file(bucket_name, "Outputs/standings_df.csv").set_index("Standings")
cumsum_df    = read_file(bucket_name, "Outputs/cumsum_df.csv").set_index("Owner")
sum_df       = read_file(bucket_name, "Outputs/sum_df.csv").set_index("Owner")

cumsum_df = cumsum_df.rename(
    columns={
        x: int(x.split("Match_")[1]) for x in cumsum_df.columns if x.startswith("Match")
    }
)

num_matches   = max([c for c in cumsum_df.columns if str(c).isdigit()])
last_match_col = sum_df.columns[-1]
last_match_pts = sum_df[last_match_col].astype(int)
leader_points  = int(standings_df["Points"].max())

# ── Hero header ───────────────────────────────────────────────────────────────
st.markdown(
    f"""
<div style="display:flex; align-items:center; gap:14px; margin-bottom:6px;">
    <div style="font-size:30px; font-weight:800; letter-spacing:-0.5px;">🏏 Summer Is Coming 2026</div>
    <span style="
        background:#f59e0b;
        color:#000;
        font-size:12px;
        font-weight:700;
        border-radius:6px;
        padding:3px 10px;
        letter-spacing:0.5px;
        white-space:nowrap;
        align-self:center;
    ">Match {num_matches}</span>
</div>
<div style="font-size:14px; color:#888; margin-bottom:16px;">Cric Talk Fantasy Draft &nbsp;·&nbsp; IPL 2026</div>
""",
    unsafe_allow_html=True,
)

st.divider()

# ── Main layout ───────────────────────────────────────────────────────────────
col1, col2 = st.columns([2, 4])

col1.markdown(
    f"""
<div style="display: flex; align-items: baseline;">
  <span style="font-size: 24px; font-weight: 600;">Leaderboard</span>
  <span style="margin-left: 10px; font-size: 16px; color: gray;">After match {num_matches}</span>
</div>
""",
    unsafe_allow_html=True,
)

rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}

rank_styles = {
    1: {"card_bg": "rgba(245,158,11,0.12)", "border": "#f59e0b"},
    2: {"card_bg": "rgba(148,163,184,0.10)", "border": "#94a3b8"},
    3: {"card_bg": "rgba(180,83,9,0.10)",   "border": "#b45309"},
}
default_style = {"card_bg": "rgba(59,130,246,0.07)", "border": "#3b82f6", "badge_bg": "#3b82f6", "badge_fg": "#fff"}

for rank, row in standings_df.iterrows():
    rank = int(rank)
    s = rank_styles.get(rank, default_style)
    badge = rank_emoji.get(rank, f"#{rank}")
    pct = round(int(row["Points"]) / leader_points * 100, 1)
    last_pts = last_match_pts.get(row["Owner"], 0)
    if last_pts > 0:
        last_badge = f'<span style="color:#6b7280;font-size:12px;">↑{last_pts}</span>'
    elif last_pts < 0:
        last_badge = f'<span style="color:#6b7280;font-size:12px;">↓{abs(last_pts)}</span>'
    else:
        last_badge = f'<span style="color:#6b7280;font-size:12px;">—</span>'
    col1.markdown(
        f"""
<div style="
    background: {s['card_bg']};
    border: 1px solid {s['border']}40;
    border-left: 3px solid {s['border']};
    border-radius: 8px;
    padding: 7px 12px 5px 12px;
    margin-bottom: 5px;
">
    <div style="display:flex; align-items:center; gap:10px;">
        {f'<span style="font-size:20px; flex-shrink:0;">{badge}</span>' if rank <= 3 else f'<span style="background:{s["badge_bg"]};color:{s["badge_fg"]};font-weight:700;font-size:11px;border-radius:4px;padding:2px 6px;min-width:26px;text-align:center;flex-shrink:0;">#{rank}</span>'}
        <div style="flex:1; min-width:0; overflow:hidden;">
            <span style="font-weight:600; font-size:14px;">{row['Owner']}</span>
            <span style="color:#888; font-size:12px; margin-left:6px;">{row['Team']}</span>
        </div>
        <div style="display:flex; align-items:center; gap:10px; flex-shrink:0;">
            <span style="font-size:20px; font-weight:700; color:#f97316; min-width:44px; text-align:right;">{int(row['Points'])}</span>
            <span style="min-width:34px; text-align:left;">{last_badge}</span>
        </div>
    </div>
    <div style="margin-top:5px; background:rgba(255,255,255,0.08); border-radius:3px; height:3px;">
        <div style="width:{pct}%; background:{s['border']}; height:3px; border-radius:3px;"></div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

col2.subheader("Draft Standings Race")
col2.line_chart(cumsum_df.T, height=500)
