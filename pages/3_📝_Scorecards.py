import streamlit as st
import pandas as pd
from helpers import get_client, read_file
from settings import bucket_name

client = get_client()

scorecards = sorted(
    [
        blob.name.strip("Scorecards/").strip("_scorecard.csv")
        for blob in client.list_blobs(bucket_name, prefix="Scorecards")
    ],
    reverse=True,
)

OWNER_PALETTE = {
    "Mabbu":  "#fecaca",  # red
    "Siddhu": "#fed7aa",  # orange
    "Bhar":   "#fef08a",  # yellow
    "Srini":  "#bbf7d0",  # green
    "Saju":   "#99f6e4",  # teal
    "Abhi":   "#bae6fd",  # sky blue
    "Jilla":  "#bfdbfe",  # blue
    "Ash":    "#ddd6fe",  # violet
    "Firi":   "#f5d0fe",  # purple
    "Shar":   "#fbcfe8",  # pink
    "Vaithy": "#d9f99d",  # lime
}

option = st.selectbox("Select match id", scorecards)

scorecard_df = read_file(bucket_name, f"Scorecards/{option}_scorecard.csv")
score_df = read_file(bucket_name, "Outputs/score_df.csv")
player_owner = score_df[["Player_id", "Owner"]].drop_duplicates(subset="Player_id").set_index("Player_id")["Owner"]
scorecard_df["Owner"] = scorecard_df["Player_id"].map(player_owner)

st.subheader("Scorecard")

# Colour legend
owner_cols = st.columns(len(OWNER_PALETTE))
for col, (owner, color) in zip(owner_cols, OWNER_PALETTE.items()):
    col.markdown(
        f'<div style="background:{color};border-radius:4px;padding:2px 6px;text-align:center;'
        f'font-size:11px;color:#333;">{owner}</div>',
        unsafe_allow_html=True,
    )
st.markdown("")

display_cols = {
    "Owner": "Owner",
    "Name_batting": "Player",
    "Desc": "Dismissal",
    "Runs_batting": "Runs",
    "Balls_batting": "Balls",
    "4s": "4s",
    "6s": "6s",
    "SR": "SR",
    "batting_points": "Bat Pts",
    "Overs": "Overs",
    "Wickets": "Wkts",
    "Runs_bowling": "Runs Cvd",
    "Econ": "Econ",
    "bowling_points": "Bowl Pts",
    "fielding_points": "Field Pts",
    "bonus_points": "Bonus",
    "total_points": "Total Pts",
}

display_df = scorecard_df[list(display_cols.keys())].rename(columns=display_cols)

def _highlight_owner(row):
    color = OWNER_PALETTE.get(row["Owner"], "")
    return [f"background-color: {color}" if color else ""] * len(row)

styled = (
    display_df.style
    .apply(_highlight_owner, axis=1)
    .background_gradient(subset=["Total Pts"], cmap="Greens")
    .background_gradient(subset=["Bat Pts"], cmap="Blues")
    .background_gradient(subset=["Bowl Pts"], cmap="Purples")
    .format(
        {
            "Runs": "{:.0f}", "Balls": "{:.0f}", "4s": "{:.0f}", "6s": "{:.0f}",
            "SR": "{:.1f}", "Bat Pts": "{:.0f}", "Overs": "{:.1f}",
            "Wkts": "{:.0f}", "Runs Cvd": "{:.0f}", "Econ": "{:.2f}",
            "Bowl Pts": "{:.0f}", "Field Pts": "{:.0f}", "Bonus": "{:.0f}",
            "Total Pts": "{:.0f}",
        },
        na_rep="-",
    )
)

st.dataframe(
    styled,
    use_container_width=True,
    column_config={
        "Owner": st.column_config.TextColumn("Owner", pinned=True),
        "Player": st.column_config.TextColumn("Player", pinned=True),
    },
)
