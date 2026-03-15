import streamlit as st
import pandas as pd
from helpers import read_file
from settings import bucket_name

st.set_page_config(layout="wide")
st.title("Points")

score_df         = read_file(bucket_name, "Outputs/score_df.csv")
sum_df           = read_file(bucket_name, "Outputs/sum_df.csv").set_index("Owner").astype(int)
cumsum_df        = read_file(bucket_name, "Outputs/cumsum_df.csv").set_index("Owner")
cumrank_df       = read_file(bucket_name, "Outputs/cumrank_df.csv").set_index("Owner")
weekly_df        = read_file(bucket_name, "Outputs/weekly_points_df.csv").set_index("Owner")
points_df        = read_file(bucket_name, "Outputs/season_points_df.csv")
player_weekly_df = read_file(bucket_name, "Outputs/weekly_player_points_df.csv")

tab1, tab2, tab3, tab4 = st.tabs(["📋 Draft Points", "📊 Match Summary", "📈 Cumulative", "👤 All Players"])

with tab1:
    st.subheader("Match-wise player points")
    st.caption("Includes captaincy (1.5×) and bench (0.5×) multipliers")
    st.dataframe(score_df, use_container_width=True)

with tab2:
    st.subheader("Match aggregate points")
    st.caption("Total points per owner per match")
    st.dataframe(sum_df, use_container_width=True)

    st.divider()
    st.subheader("Weekly points")
    st.dataframe(weekly_df, use_container_width=True)

with tab3:
    st.subheader("Cumulative points")
    st.dataframe(cumsum_df, use_container_width=True)

    st.divider()
    st.subheader("Cumulative ranking")
    st.caption("Rank 1 = leading")
    st.dataframe(cumrank_df, use_container_width=True)

with tab4:
    st.subheader("Match-wise points — all players")
    st.caption("No captaincy multipliers or bench exclusions")
    st.dataframe(points_df, use_container_width=True)

    st.divider()
    st.subheader("Weekly points — all players")
    st.dataframe(player_weekly_df, use_container_width=True)
