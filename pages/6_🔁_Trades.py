import streamlit as st
import pandas as pd
from settings import owner_team_dict, trades_spreadsheet_url
from helpers import read_gsheet


st.set_page_config(layout="wide")
for owner in sorted(owner_team_dict.keys()):
    st.header(owner)
    trade_df = read_gsheet(trades_spreadsheet_url, owner).set_index("S.no")

    st.dataframe(trade_df)
