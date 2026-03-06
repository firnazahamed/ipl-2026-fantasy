import streamlit as st
import pandas as pd
from helpers import get_client, read_file
from settings import bucket_name

client = get_client()

squads = sorted(
    [
        blob.name.strip("Squads/").strip(".csv")
        for blob in client.list_blobs(bucket_name, prefix="Squads")
    ],
    reverse=True,
)

option = st.selectbox("Select week", squads)

squad_df = read_file(bucket_name, f"Squads/{option}.csv")
st.subheader("Squad")
st.dataframe(squad_df)
