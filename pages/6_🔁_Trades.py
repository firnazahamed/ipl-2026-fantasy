import streamlit as st
from settings import owner_team_dict, trades_spreadsheet_url
from helpers import read_gsheet

st.set_page_config(layout="wide")
st.title("Trades")

owners = sorted(owner_team_dict.keys())
tabs = st.tabs(owners)

for tab, owner in zip(tabs, owners):
    with tab:
        st.caption(owner_team_dict[owner])
        trade_df = read_gsheet(trades_spreadsheet_url, owner).set_index("S.no")
        st.dataframe(trade_df, use_container_width=True)
