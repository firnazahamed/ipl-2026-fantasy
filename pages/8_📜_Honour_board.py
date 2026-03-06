import streamlit as st
import pandas as pd
from helpers import read_file

st.set_page_config(layout="wide")

seasons = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
honour_board = pd.DataFrame(
    {
        "Season": seasons,
        "Winner": ["Ashkay", "Mabbu", "Saju", "Saju", "Firi", "Firi", "Vaithy", "TBD"],
        "Runner-up": ["Mabbu", "Bhar", "Siddhu", "Srini", "Bhar", "Srini", "Ashkay", "TBD"],
        "Second runner-up": ["Bhar", "Shar", "Srini", "Firi", "Saju", "Ashkay", "Abhi", "TBD"],
    }
).set_index("Season")

st.header("Honour Board")
st.table(honour_board)

st.header("Past Seasons")
bucket_name = "ipl-seasons"

for year in sorted(seasons, reverse=True):

    col1, col2 = st.columns([2, 3])

    standings_df = read_file(bucket_name, f"{year}_standings.csv").set_index(
        "Standings"
    )
    col1.subheader(f"{year} Final Standings")
    col1.dataframe(standings_df)

    cumsum_df = read_file(bucket_name, f"{year}_cumsum.csv").set_index("Owner")
    cumsum_df = cumsum_df.rename(columns={x: int(x) for x in cumsum_df.columns})
    col2.subheader(f"{year} Standings Race")
    col2.line_chart(cumsum_df.T)

    st.markdown("#")
