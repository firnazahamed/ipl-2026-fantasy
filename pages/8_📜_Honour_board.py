import streamlit as st
import pandas as pd
from collections import Counter
from helpers import read_file

st.set_page_config(layout="wide")

seasons = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
winners        = ["Ashkay", "Mabbu", "Saju",   "Saju",  "Firi",  "Firi",   "Vaithy", "Srini"]
runners_up     = ["Mabbu",  "Bhar",  "Siddhu", "Srini", "Bhar",  "Srini",  "Ashkay", "Mabbu"]
second_runners = ["Bhar",   "Shar",  "Srini",  "Firi",  "Saju",  "Ashkay", "Abhi",   "Firi"]

honour_board = pd.DataFrame({
    "Season": seasons,
    "Winner": winners,
    "Runner-up": runners_up,
    "Second runner-up": second_runners,
}).set_index("Season")

# ── Season history cards ──────────────────────────────────────────────────────
st.markdown("## 🏆 Honour Board")

for season, row in honour_board.sort_index(ascending=False).iterrows():
    st.markdown(
        f"""
<div style="
    border: 1px solid #f59e0b30;
    border-left: 4px solid #f59e0b;
    border-radius: 8px;
    padding: 10px 18px;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 32px;
">
    <span style="font-size:20px; font-weight:800; color:#f59e0b; min-width:46px;">{season}</span>
    <span style="font-size:15px;">🥇&nbsp;<strong>{row['Winner']}</strong></span>
    <span style="font-size:15px; color:#aaa;">🥈&nbsp;{row['Runner-up']}</span>
    <span style="font-size:15px; color:#aaa;">🥉&nbsp;{row['Second runner-up']}</span>
</div>
""",
        unsafe_allow_html=True,
    )

# ── Trophy tally ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Trophy Tally")

win_count    = Counter(winners)
runner_count = Counter(runners_up)
second_count = Counter(second_runners)
all_owners   = sorted(set(winners) | set(runners_up) | set(second_runners))

tally = (
    pd.DataFrame({
        "Owner": all_owners,
        "🥇": [win_count.get(o, 0)    for o in all_owners],
        "🥈": [runner_count.get(o, 0) for o in all_owners],
        "🥉": [second_count.get(o, 0) for o in all_owners],
    })
    .sort_values(["🥇", "🥈", "🥉"], ascending=False)
    .set_index("Owner")
)

def _gold(v):
    return "background-color: #fcd34d; color: #000; font-weight: 700;" if v > 0 else "color: #555;"

def _silver(v):
    return "background-color: #cbd5e1; color: #000; font-weight: 700;" if v > 0 else "color: #555;"

def _bronze(v):
    return "background-color: #fdba74; color: #000; font-weight: 700;" if v > 0 else "color: #555;"

st.dataframe(
    tally.style
        .applymap(_gold,   subset=["🥇"])
        .applymap(_silver, subset=["🥈"])
        .applymap(_bronze, subset=["🥉"]),
    use_container_width=True,
)

# ── Past seasons detail ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Past Seasons")
bucket_name = "ipl-seasons"

for year in sorted(seasons, reverse=True):
    st.markdown(
        f"""
<div style="
    border-left: 4px solid #3b82f6;
    padding: 4px 12px;
    margin: 24px 0 12px 0;
">
    <span style="font-size:22px; font-weight:700;">{year}</span>
    <span style="color:#888; font-size:14px; margin-left:8px;">Season</span>
</div>
""",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([2, 4])

    standings_df = read_file(bucket_name, f"{year}_standings.csv").set_index("Standings")
    col1.dataframe(standings_df, use_container_width=True)

    cumsum_df = read_file(bucket_name, f"{year}_cumsum.csv").set_index("Owner")
    cumsum_df = cumsum_df.rename(columns={x: int(x) for x in cumsum_df.columns})
    col2.line_chart(cumsum_df.T, height=280)
