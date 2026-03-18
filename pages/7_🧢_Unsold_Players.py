import streamlit as st
from helpers import read_gsheet
from settings import unsold_spreadsheet_url

st.set_page_config(layout="wide")
st.title("Unsold Players")

unsold_df = read_gsheet(unsold_spreadsheet_url, "Unsold_players")

st.metric("Total Unsold", len(unsold_df))
st.dataframe(unsold_df, use_container_width=True, hide_index=True)
