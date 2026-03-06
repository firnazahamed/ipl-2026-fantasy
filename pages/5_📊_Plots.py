import streamlit as st
import pandas as pd
import altair as alt
from altair import datum
from helpers import read_file
from get_standings import retrieve_scorecards
from settings import bucket_name

st.set_page_config(page_title="Plots", page_icon="📊")

cumsum_df = read_file(bucket_name, "Outputs/cumsum_df.csv").set_index("Owner")
sum_df = read_file(bucket_name, "Outputs/sum_df.csv").set_index("Owner")
cumrank_df = read_file(bucket_name, "Outputs/cumrank_df.csv")

sum_df = sum_df.rename(
    columns={
        x: int(x.split("Match_")[1]) for x in sum_df.columns if x.startswith("Match")
    }
)
cumsum_df = cumsum_df.rename(
    columns={
        x: int(x.split("Match_")[1]) for x in cumsum_df.columns if x.startswith("Match")
    }
)
st.header("Draft Standings Race")
st.line_chart(cumsum_df.T)

# Draft Standings Evolution Plot
# Melt into long format
df_long = cumrank_df.melt(id_vars="Owner", var_name="Match", value_name="Rank")
df_long["Match"] = df_long["Match"].str.extract(r"(\d+)").astype(int)

# Determine max rank for dynamic scaling
max_rank = df_long["Rank"].max()

# Create chart with a fixed y-axis domain (1 to max_rank)
chart = (
    alt.Chart(df_long)
    .mark_line(point=True)
    .encode(
        x=alt.X("Match:O", title="Match Number"),
        y=alt.Y(
            "Rank:Q",
            title="Draft Standing",
            scale=alt.Scale(domain=[1, max_rank], reverse=True),
        ),
        color="Owner:N",
    )
    .properties(width=800, height=500, title="Standings Progression Over Matches")
)

st.altair_chart(chart, use_container_width=True)

st.header("Player performance")
st.markdown(
    "Plot shows the points scored by the players excluding the multipliers for captains"
)

agg_points_df = read_file(bucket_name, "Outputs/agg_points_df.csv")
c = (
    alt.Chart(agg_points_df)
    .mark_circle()
    .encode(
        x="batting_points",
        y="bowling_points",
        color="total_points",
        tooltip=["Name_batting", "batting_points", "bowling_points", "fielding_points"],
    )
    .interactive()
)

annotation_points_cutoff = agg_points_df[:5].total_points.min()
annotation = (
    alt.Chart(agg_points_df)
    .mark_text(align="left", baseline="middle", fontSize=10, dx=7)
    .encode(x="batting_points", y="bowling_points", text="Name_batting")
    .transform_filter((datum.total_points >= annotation_points_cutoff))
)

st.altair_chart((c + annotation), use_container_width=True)

st.markdown("#")
st.header("Comparison plots")

players = st.multiselect("Choose team owners", cumsum_df.index)
if not players:
    st.error("Please select at least one team owner")
else:

    st.header("Match wise points chart")
    chart_data = sum_df.loc[players].T
    st.area_chart(chart_data)

    cumsum_data = cumsum_df.loc[players]
    cumsum_data = cumsum_data.T.reset_index()
    cumsum_data = pd.melt(cumsum_data, id_vars=["index"]).rename(
        columns={"index": "Match", "value": "Cumulative Points"}
    )

    chart = (
        alt.Chart(cumsum_data)
        .mark_line()
        .encode(x="Match", y="Cumulative Points", color="Owner")
    )

    st.header("Cumulative points")
    st.altair_chart(chart, use_container_width=True)
