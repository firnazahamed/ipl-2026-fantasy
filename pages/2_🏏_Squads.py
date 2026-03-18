import streamlit as st
from helpers import read_gsheet, list_gsheet_tabs
from settings import squads_spreadsheet_url

squads = sorted(list_gsheet_tabs(squads_spreadsheet_url), reverse=True)

option = st.selectbox("Select week", squads)

squad_df = read_gsheet(squads_spreadsheet_url, option)
st.subheader("Squad")
st.dataframe(squad_df)
