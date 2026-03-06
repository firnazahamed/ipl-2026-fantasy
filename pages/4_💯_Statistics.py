import streamlit as st
import pandas as pd
from helpers import read_file
from settings import retentions_list, rtm_list, bucket_name

st.set_page_config(layout="wide")
st.title("Player performance statistics")

unsold_df = read_file(bucket_name, "Unsold_players.csv")
prices_df = read_file(bucket_name, "price_list.csv")
agg_points_df = read_file(bucket_name, "Outputs/agg_points_df.csv")

df = prices_df.merge(agg_points_df, left_on="Player_name", right_on="Name_batting")
df = df[
    [
        "Player_name",
        "Team",
        "Category",
        "Price",
        "batting_points",
        "bowling_points",
        "fielding_points",
        "total_points",
    ]
]

for price in sorted(df["Price"].unique(), reverse=True):
    price_category_df = df[df["Price"] == price].sort_values(
        "total_points", ascending=False
    )
    st.header(f"{price} Price Category")
    st.subheader("Best Performers")
    st.dataframe(price_category_df.head(10))
    if len(price_category_df) > 10:
        st.subheader("Worst Performers")
        st.dataframe(price_category_df.tail(5).sort_values("total_points"))

for category in sorted(df["Category"].unique()):
    category_df = df[df["Category"] == category].sort_values(
        "total_points", ascending=False
    )
    st.header(f"Best {category}")
    # st.subheader("Best Performers")
    st.dataframe(category_df.head(10))

retention_df = df[df["Player_name"].isin(retentions_list)].sort_values(
    "total_points", ascending=False
)
st.header(f"Retention Performers")
st.dataframe(retention_df.head(11))

rtm_df = df[df["Player_name"].isin(rtm_list)].sort_values(
    "total_points", ascending=False
)
st.header(f"RTM Performers")
st.dataframe(rtm_df.head(11))
