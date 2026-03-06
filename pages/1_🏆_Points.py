import streamlit as st
import pandas as pd
from helpers import read_file
from settings import bucket_name

score_df = read_file(bucket_name, "Outputs/score_df.csv").set_index("Owner")
st.header("Match wise player points for our draft")
st.subheader("Points for players in our draft including captaincy mutlipliers")
st.dataframe(
    score_df,
    column_config={
        "Owner": st.column_config.TextColumn("Owner", pinned=True),
        "Player": st.column_config.TextColumn("Player", pinned=True),
    },
)

sum_df = read_file(bucket_name, "Outputs/sum_df.csv").set_index("Owner").astype(int)
st.header("Match aggregate points")
st.dataframe(sum_df.style.highlight_max(axis=0).format("{:d}"))

cumsum_df = read_file(bucket_name, "Outputs/cumsum_df.csv").set_index("Owner")
st.header("Cumulative points")
st.dataframe(cumsum_df)

cumrank_df = read_file(bucket_name, "Outputs/cumrank_df.csv").set_index("Owner")
st.header("Cumulative ranking")
st.dataframe(cumrank_df)

weekly_df = read_file(bucket_name, "Outputs/weekly_points_df.csv").set_index("Owner")
st.header("Weekly points in our draft")
st.dataframe(weekly_df)

points_df = read_file(bucket_name, "Outputs/season_points_df.csv").set_index("Player")
st.header("Match wise player points for all players")
st.subheader("Points for all players without captaincy multipliers or bench exclusions")
st.dataframe(points_df)

player_weekly_df = read_file(
    bucket_name, "Outputs/weekly_player_points_df.csv"
).set_index("Player")
st.header("Weekly points for all players")
st.dataframe(player_weekly_df)
