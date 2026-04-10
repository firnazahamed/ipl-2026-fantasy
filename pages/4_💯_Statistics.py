import streamlit as st
import pandas as pd
from helpers import read_file, read_gsheet, find_col
from settings import retentions_list, rtm_list, bucket_name, unsold_spreadsheet_url, price_list_spreadsheet_url

st.set_page_config(layout="wide")
st.title("Player Performance Statistics")

unsold_df = read_gsheet(unsold_spreadsheet_url, "Unsold_players")
prices_df = read_gsheet(price_list_spreadsheet_url, "price_list")
agg_points_df = read_file(bucket_name, "Outputs/agg_points_df.csv")

_name_col  = find_col(prices_df, "Player_name", "Player name", "Name")
_team_col  = find_col(prices_df, "Team", "IPL Team", "Franchise")
_cat_col   = find_col(prices_df, "Category", "Role")
_price_col = find_col(prices_df, "Price")

df = prices_df.merge(agg_points_df, left_on=_name_col, right_on="Name_batting")
df = df[
    [
        _name_col,
        _team_col,
        _cat_col,
        _price_col,
        "batting_points",
        "bowling_points",
        "fielding_points",
        "total_points",
    ]
].rename(columns={
    _name_col:  "Player",
    _team_col:  "Team",
    _cat_col:   "Category",
    _price_col: "Price",
    "batting_points":  "Batting",
    "bowling_points":  "Bowling",
    "fielding_points": "Fielding",
    "total_points":    "Total",
})

tab1, tab2, tab3 = st.tabs(["By Price", "By Category", "Retentions & RTM"])

with tab1:
    for price in sorted(df["Price"].unique(), reverse=True):
        price_df = df[df["Price"] == price].sort_values("Total", ascending=False)
        st.subheader(f"{price} Price Category")
        col1, col2 = st.columns(2)
        with col1:
            st.caption("Best Performers")
            st.dataframe(price_df.head(10), use_container_width=True, hide_index=True)
        if len(price_df) > 10:
            with col2:
                st.caption("Worst Performers")
                st.dataframe(price_df.tail(5).sort_values("Total"), use_container_width=True, hide_index=True)
        st.divider()

with tab2:
    for category in sorted(df["Category"].unique()):
        category_df = df[df["Category"] == category].sort_values("Total", ascending=False)
        st.subheader(f"Best {category}")
        st.dataframe(category_df.head(10), use_container_width=True, hide_index=True)
        st.divider()

with tab3:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Retentions")
        retention_df = df[df["Player"].isin(retentions_list)].sort_values("Total", ascending=False)
        st.dataframe(retention_df, use_container_width=True, hide_index=True)
    with col2:
        st.subheader("RTM")
        rtm_df = df[df["Player"].isin(rtm_list)].sort_values("Total", ascending=False)
        st.dataframe(rtm_df, use_container_width=True, hide_index=True)
