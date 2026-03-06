import streamlit as st
import pandas as pd
from helpers import read_file

st.set_page_config(layout="wide")
st.title("Summer Is Coming 2026")
st.subheader("**:blue[Cric Talk Draft]** :fire:")


bucket_name = "summer-is-coming-2026"
standings_file_path = "Outputs/standings_df.csv"
cumsum_file_path = "Outputs/cumsum_df.csv"

standings_df = read_file(bucket_name, standings_file_path).set_index("Standings")
cumsum_df = read_file(bucket_name, cumsum_file_path).set_index("Owner")
col1, col2 = st.columns([2, 3])

cumsum_df = cumsum_df.rename(
    columns={
        x: int(x.split("Match_")[1]) for x in cumsum_df.columns if x.startswith("Match")
    }
)

num_matches = max([c for c in cumsum_df.columns if str(c).isdigit()])
col1.markdown(
    f"""
<div style="display: flex; align-items: baseline;">
  <span style="font-size: 24px; font-weight: 600;">Standings</span>
  <span style="margin-left: 10px; font-size: 16px; color: gray;">After match {num_matches}</span>
</div>
""",
    unsafe_allow_html=True,
)
col1.dataframe(standings_df, height=420)

col2.subheader("Draft Standings Race")
col2.line_chart(cumsum_df.T)
