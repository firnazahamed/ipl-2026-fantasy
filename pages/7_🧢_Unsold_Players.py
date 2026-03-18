import streamlit as st
from helpers import read_gsheet
from settings import unsold_spreadsheet_url

unsold_df = read_gsheet(unsold_spreadsheet_url, "Unsold_players")
st.header("Unsold Players")
st.table(unsold_df)
