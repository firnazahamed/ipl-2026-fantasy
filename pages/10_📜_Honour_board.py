import streamlit as st
import pandas as pd
from collections import Counter
from helpers import read_file

st.set_page_config(layout="wide")

ipl_data = pd.DataFrame({
    "Season": [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],
    "Winner":          ["Ashkay", "Mabbu", "Saju",   "Saju",  "Firi",  "Firi",   "Vaithy", "Srini"],
    "Runner-up":       ["Mabbu",  "Bhar",  "Siddhu", "Srini", "Bhar",  "Srini",  "Ashkay", "Mabbu"],
    "Second runner-up":["Bhar",   "Shar",  "Srini",  "Firi",  "Saju",  "Ashkay", "Abhi",   "Firi"],
    "Type": "IPL",
})

wc_data = pd.DataFrame({
    "Season": [2019, 2023],
    "Winner":          ["Ashkay", "Bhar"],
    "Runner-up":       ["Srini",  "Firi"],
    "Second runner-up":["Shar",   "Ashkay"],
    "Type": "WC",
})

seasons = ipl_data["Season"].tolist()

honour_board = (
    pd.concat([ipl_data, wc_data], ignore_index=True)
    .assign(TypeOrder=lambda d: d["Type"].map({"IPL": 2, "WC": 1}))
    .sort_values("TypeOrder", ascending=True)
    .sort_values("Season", ascending=False, kind="stable")
    .drop(columns="TypeOrder")
)

STYLE = {
    "IPL": {"border": "#f59e0b", "badge_bg": "#f59e0b", "badge_fg": "#000", "label": "IPL"},
    "WC":  {"border": "#10b981", "badge_bg": "#10b981", "badge_fg": "#fff", "label": "WC"},
}

# ── Season history cards ──────────────────────────────────────────────────────
st.markdown("## 🏆 Honour Board")

for _, row in honour_board.iterrows():
    s = STYLE[row["Type"]]
    st.markdown(
        f"""
<div style="
    border: 1px solid {s['border']}30;
    border-left: 4px solid {s['border']};
    border-radius: 8px;
    padding: 10px 18px;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 32px;
">
    <span style="font-size:20px; font-weight:800; color:{s['border']}; min-width:46px;">{int(row['Season'])}</span>
    <span style="background:{s['badge_bg']}; color:{s['badge_fg']}; font-size:11px; font-weight:700; border-radius:4px; padding:2px 7px;">{s['label']}</span>
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

all_winners        = honour_board["Winner"].tolist()
all_runners_up     = honour_board["Runner-up"].tolist()
all_second_runners = honour_board["Second runner-up"].tolist()

win_count    = Counter(all_winners)
runner_count = Counter(all_runners_up)
second_count = Counter(all_second_runners)
all_owners   = sorted(set(all_winners) | set(all_runners_up) | set(all_second_runners))

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

st.caption("Includes IPL and World Cup results")

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
    height=(len(tally) + 1) * 35 + 3,
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
    col1.dataframe(standings_df, use_container_width=True, height=(len(standings_df) + 1) * 35 + 3)

    cumsum_df = read_file(bucket_name, f"{year}_cumsum.csv").set_index("Owner")
    cumsum_df = cumsum_df.rename(columns={x: int(x) for x in cumsum_df.columns})
    col2.line_chart(cumsum_df.T, height=280)
