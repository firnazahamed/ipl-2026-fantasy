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

option = st.selectbox("Select match id", scorecards)

scorecard_df = read_file(bucket_name, f"Scorecards/{option}_scorecard.csv")
st.subheader("Scorecard")

display_cols = {
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

styled = (
    display_df.style
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

st.dataframe(styled, use_container_width=True)
