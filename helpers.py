import streamlit as st
import pandas as pd
import os
from google.oauth2 import service_account
from google.cloud import storage
from io import BytesIO

# Create API client.
def get_client():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"]
    )
    client = storage.Client(credentials=credentials)

    return client


@st.cache_data(ttl=600)
def read_file(bucket_name, file_path, format="csv", sheet_name=None):
    client = get_client()
    bucket = client.bucket(bucket_name)
    content = bucket.blob(file_path).download_as_bytes()
    if format == "csv":
        df = pd.read_csv(BytesIO(content))
    elif format == "excel":
        df = pd.read_excel(BytesIO(content), sheet_name=sheet_name)

    return df


def upload_df_to_gcs(df, file_path, bucket_name):

    # Setting credentials using the downloaded JSON file
    client = storage.Client.from_service_account_json(
        json_credentials_path="credentials/cricinfo-273202-a7420ddc1abd.json"
    )
    bucket = client.get_bucket(bucket_name)
    bucket.blob(file_path).upload_from_string(
        df.to_csv(header=True, index=False), "text/csv"
    )
    # object_name_in_gcs_bucket = bucket.blob(file_path)
    # object_name_in_gcs_bucket.upload_from_filename(df)


def retrieve_scorecards():

    scorcard_sheets = sorted(os.listdir("./Scorecards/"))
    scorecards = {}
    for scorecard_sheet in scorcard_sheets:
        if not scorecard_sheet.startswith("."):  # Ignore hidden files like .DS_Store
            scorecard = pd.read_csv(f"./Scorecards/{scorecard_sheet}")
            scorecard_name = scorecard_sheet.split(".csv")[0]
            scorecards[scorecard_name] = scorecard
    return scorecards


def download_gsheet_as_csv(spreadsheet_url, sheet_name, download_folder="Squads"):

    import gspread
    from settings import service_account_credentials

    # Authenticate with Google Sheets using your service account credentials
    gc = gspread.service_account(filename=service_account_credentials)

    # Open the Google Sheets document
    sh = gc.open_by_url(spreadsheet_url)

    try:
        # Select the specified sheet by name
        worksheet = sh.worksheet(sheet_name)

        # Get all values from the sheet
        data = worksheet.get_all_values()

        # Create a DataFrame from the data
        df = pd.DataFrame(data[1:], columns=data[0])

        # Save the DataFrame as a CSV file
        df.to_csv(f"{download_folder}/{sheet_name}.csv", index=False)

        print(f"Sheet '{sheet_name}' has been downloaded'")
    except gspread.exceptions.WorksheetNotFound:
        print(f"Sheet '{sheet_name}' not found in the Google Sheets document.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
