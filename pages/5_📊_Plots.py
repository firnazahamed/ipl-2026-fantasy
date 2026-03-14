import streamlit as st
import pandas as pd
import altair as alt
import plotly.graph_objects as go
import plotly.express as px
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

matches = sorted(cumsum_df.columns.tolist())
owners = sorted(cumsum_df.index.tolist())
color_seq = px.colors.qualitative.D3
owner_colors = {o: color_seq[i % len(color_seq)] for i, o in enumerate(owners)}

def _race_frame(match):
    return cumsum_df[match].fillna(0).sort_values(ascending=True)

init = _race_frame(matches[0])
max_pts = int(cumsum_df.max().max() * 1.18)

race_fig = go.Figure(
    data=[go.Bar(
        x=init.values.astype(int),
        y=init.index,
        orientation="h",
        marker_color=[owner_colors[o] for o in init.index],
        text=init.values.astype(int),
        textposition="outside",
        cliponaxis=False,
    )],
    frames=[
        go.Frame(
            data=[go.Bar(
                x=_race_frame(m).values.astype(int),
                y=_race_frame(m).index,
                orientation="h",
                marker_color=[owner_colors[o] for o in _race_frame(m).index],
                text=_race_frame(m).values.astype(int),
                textposition="outside",
                cliponaxis=False,
            )],
            layout=go.Layout(
                yaxis={"categoryorder": "array", "categoryarray": _race_frame(m).index.tolist()},
                title_text=f"After Match {m}",
            ),
            name=str(m),
        )
        for m in matches
    ],
    layout=go.Layout(
        height=430,
        margin=dict(l=80, r=80, t=50, b=60),
        xaxis=dict(range=[0, max_pts], showgrid=True),
        yaxis=dict(categoryorder="array", categoryarray=init.index.tolist()),
        title=dict(text=f"After Match {matches[0]}", x=0.5),
        showlegend=False,
        updatemenus=[{
            "type": "buttons",
            "showactive": False,
            "y": -0.18,
            "x": 0.5,
            "xanchor": "center",
            "yanchor": "top",
            "buttons": [
                {
                    "label": "▶ Play",
                    "method": "animate",
                    "args": [None, {
                        "frame": {"duration": 800, "redraw": True},
                        "fromcurrent": True,
                        "transition": {"duration": 600, "easing": "cubic-in-out"},
                    }],
                },
                {
                    "label": "⏸ Pause",
                    "method": "animate",
                    "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}],
                },
            ],
        }],
        sliders=[{
            "active": 0,
            "currentvalue": {"prefix": "Match ", "font": {"size": 13}, "xanchor": "center"},
            "transition": {"duration": 600, "easing": "cubic-in-out"},
            "pad": {"t": 40},
            "len": 0.9,
            "x": 0.05,
            "steps": [
                {
                    "args": [[str(m)], {
                        "frame": {"duration": 800, "redraw": True},
                        "mode": "immediate",
                        "transition": {"duration": 600, "easing": "cubic-in-out"},
                    }],
                    "label": str(m),
                    "method": "animate",
                }
                for m in matches
            ],
        }],
    ),
)

st.plotly_chart(race_fig, use_container_width=True)

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
