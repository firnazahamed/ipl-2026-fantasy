import streamlit as st
from helpers import read_gsheet, list_gsheet_tabs
from settings import squads_spreadsheet_url

st.set_page_config(layout="wide")
st.title("Squads")

squads = sorted(list_gsheet_tabs(squads_spreadsheet_url), reverse=True)

option = st.selectbox("Select week", squads)

squad_df = read_gsheet(squads_spreadsheet_url, option)

st.dataframe(squad_df, use_container_width=True)
