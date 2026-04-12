import streamlit as st
from settings import owner_team_dict, trades_spreadsheet_url
from helpers import read_gsheet, find_col

st.set_page_config(layout="wide")
st.title("Trades")

owners = sorted(owner_team_dict.keys())
tabs = st.tabs(owners)

for tab, owner in zip(tabs, owners):
    with tab:
        st.caption(owner_team_dict[owner])
        trade_df = read_gsheet(trades_spreadsheet_url, owner)
        sno_col = find_col(trade_df, "S.no", "S no", "S_no", "Sno", "Serial")
        if sno_col:
            trade_df = trade_df.set_index(sno_col)
        st.dataframe(trade_df, use_container_width=True)
