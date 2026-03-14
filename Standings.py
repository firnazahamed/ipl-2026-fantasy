import streamlit as st
import pandas as pd
from helpers import read_file

st.set_page_config(layout="wide")
st.title("Summer Is Coming 2026")
st.subheader("**:blue[Cric Talk Draft]** :fire:")


bucket_name = "summer-is-coming-2026"
standings_file_path = "Outputs/standings_df.csv"
cumsum_file_path = "Outputs/cumsum_df.csv"

standings_df = read_file(bucket_name, standings_file_path).set_index("Standings")
cumsum_df = read_file(bucket_name, cumsum_file_path).set_index("Owner")
sum_df = read_file(bucket_name, "Outputs/sum_df.csv").set_index("Owner")
col1, col2 = st.columns([2, 4])

cumsum_df = cumsum_df.rename(
    columns={
        x: int(x.split("Match_")[1]) for x in cumsum_df.columns if x.startswith("Match")
    }
)

num_matches = max([c for c in cumsum_df.columns if str(c).isdigit()])
col1.markdown(
    f"""
<div style="display: flex; align-items: baseline;">
  <span style="font-size: 24px; font-weight: 600;">Standings</span>
  <span style="margin-left: 10px; font-size: 16px; color: gray;">After match {num_matches}</span>
</div>
""",
    unsafe_allow_html=True,
)

rank_styles = {
    1: {"badge_bg": "#f59e0b", "badge_fg": "#000", "card_bg": "rgba(245,158,11,0.12)", "border": "#f59e0b"},
    2: {"badge_bg": "#94a3b8", "badge_fg": "#000", "card_bg": "rgba(148,163,184,0.10)", "border": "#94a3b8"},
    3: {"badge_bg": "#b45309", "badge_fg": "#fff", "card_bg": "rgba(180,83,9,0.10)",   "border": "#b45309"},
}
default_style = {"badge_bg": "#3b82f6", "badge_fg": "#fff", "card_bg": "rgba(59,130,246,0.07)", "border": "#3b82f6"}

leader_points = standings_df["Points"].max()
last_match_col = sum_df.columns[-1]
last_match_pts = sum_df[last_match_col].astype(int)

for rank, row in standings_df.iterrows():
    rank = int(rank)
    s = rank_styles.get(rank, default_style)
    pct = round(int(row["Points"]) / leader_points * 100, 1)
    last_pts = last_match_pts.get(row["Owner"], 0)
    last_badge = (
        f'<span style="background:#22c55e22;color:#22c55e;font-size:11px;font-weight:600;'
        f'border:1px solid #22c55e55;border-radius:4px;padding:1px 7px;">Leader</span>'
        f'&nbsp;<span style="color:#6b7280;font-size:12px;">↑{last_pts}</span>'
        if rank == 1
        else f'<span style="color:#6b7280;font-size:12px;">↑{last_pts}</span>'
    )
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
        <span style="
            background: {s['badge_bg']};
            color: {s['badge_fg']};
            font-weight: 700;
            font-size: 11px;
            border-radius: 4px;
            padding: 2px 6px;
            min-width: 26px;
            text-align: center;
            flex-shrink: 0;
        ">#{rank}</span>
        <div style="flex:1; min-width:0; overflow:hidden;">
            <span style="font-weight:600; font-size:14px;">{row['Owner']}</span>
            <span style="color:#888; font-size:12px; margin-left:6px;">{row['Team']}</span>
        </div>
        <div style="text-align:right; flex-shrink:0;">
            <span style="font-size:20px; font-weight:700; color:#f97316;">{int(row['Points'])}</span>
            &nbsp;{last_badge}
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
