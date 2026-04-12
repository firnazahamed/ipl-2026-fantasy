import streamlit as st
import pandas as pd
import os
from io import BytesIO

# Create API client.
def get_client():
    from google.oauth2 import service_account
    from google.cloud import storage
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
    from google.cloud import storage
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


@st.cache_data(ttl=600)
def read_gsheet(spreadsheet_url, sheet_name):
    import gspread
    gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
    worksheet = gc.open_by_url(spreadsheet_url).worksheet(sheet_name)
    data = worksheet.get_all_values()
    return pd.DataFrame(data[1:], columns=data[0])


@st.cache_data(ttl=600)
def list_gsheet_tabs(spreadsheet_url):
    import gspread
    gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
    return [ws.title for ws in gc.open_by_url(spreadsheet_url).worksheets()]


def _gspread_client():
    import gspread
    return gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))


def write_trade(spreadsheet_url, owner, transfer_type, player_in, player_out, week_effective):
    """Fill the next empty row in the owner's trade tab."""
    ws = _gspread_client().open_by_url(spreadsheet_url).worksheet(owner)
    rows = ws.get_all_values()
    for i, row in enumerate(rows[1:], start=2):  # skip header row
        if len(row) < 2 or not row[1].strip():
            ws.update(f"B{i}:E{i}", [[transfer_type, player_in, player_out, week_effective]])
            return
    # All pre-filled rows used — append a new one
    ws.append_row([len(rows), transfer_type, player_in, player_out, week_effective])


def remove_player_from_unsold(spreadsheet_url, player_name):
    ws = _gspread_client().open_by_url(spreadsheet_url).worksheet("Unsold_players")
    cell = ws.find(player_name)
    if cell:
        ws.delete_rows(cell.row)


def add_player_to_unsold(spreadsheet_url, player_name, team="", role="", price=""):
    ws = _gspread_client().open_by_url(spreadsheet_url).worksheet("Unsold_players")
    rows = ws.get_all_values()
    headers = rows[0] if rows else []
    next_sno = len(rows)
    lookup = {
        "s.no": str(next_sno),
        "player name": player_name,
        "team": team,
        "role": role,
        "category": role,  # GSheet may use "Category" instead of "Role"
    }
    # Match any header containing "price"
    row = []
    for h in headers:
        key = h.strip().lower()
        if "price" in key:
            row.append(str(price))
        else:
            row.append(lookup.get(key, ""))
    ws.append_row(row)


def write_squad(spreadsheet_url, week_name, owner, squad_rows):
    """Write an owner's squad to the week tab in the squads GSheet.

    squad_rows: list of exactly 15 player names ordered as:
        [0]     = captain  (also in playing XI)
        [1]     = vice-captain  (also in playing XI)
        [2-10]  = remaining 9 playing XI players
        [11-14] = 4 bench/reserve players (use "" for empty slots)

    GSheet layout (data rows, after header row 1):
        Rows  2–12  → Playing XI  (11 players)
        Rows 13–16  → Empty       (4 blank separator rows)
        Rows 17–20  → Bench       (4 players)

    Creates the week worksheet if it doesn't exist.
    Updates only the owner's column, leaving every other column untouched.
    """
    import gspread
    from settings import owner_team_dict

    gc = _gspread_client()
    sh = gc.open_by_url(spreadsheet_url)

    # Get or create the week worksheet
    try:
        ws = sh.worksheet(week_name)
        headers = ws.row_values(1)
    except gspread.exceptions.WorksheetNotFound:
        owners = list(owner_team_dict.keys())
        ws = sh.add_worksheet(title=week_name, rows=20, cols=len(owners))
        ws.update("A1", [owners])
        headers = owners

    if owner not in headers:
        raise ValueError(f"Owner '{owner}' not found in sheet headers: {headers}")

    col_idx = headers.index(owner) + 1  # 1-based

    xi    = squad_rows[:11]   # Playing XI  → rows 2–12
    bench = squad_rows[11:15] # Bench        → rows 17–20

    # Write Playing XI (rows 2–12)
    xi_start = gspread.utils.rowcol_to_a1(2, col_idx)
    xi_end   = gspread.utils.rowcol_to_a1(12, col_idx)
    ws.update(f"{xi_start}:{xi_end}", [[p] for p in xi])

    # Clear separator rows 13–16
    sep_start = gspread.utils.rowcol_to_a1(13, col_idx)
    sep_end   = gspread.utils.rowcol_to_a1(16, col_idx)
    ws.update(f"{sep_start}:{sep_end}", [[""], [""], [""], [""]])

    # Write bench rows 17–20
    bench_start = gspread.utils.rowcol_to_a1(17, col_idx)
    bench_end   = gspread.utils.rowcol_to_a1(20, col_idx)
    ws.update(f"{bench_start}:{bench_end}", [[p] for p in bench])


# ── Shared role helpers ────────────────────────────────────────────────────────
BAT_ROLES  = {"BAT", "BATSMAN", "BATTER", "WK", "WICKETKEEPER", "WICKET-KEEPER",
               "WICKET KEEPER", "AR", "ALL-ROUNDER", "ALL ROUNDER", "ALLROUNDER"}
BOWL_ROLES = {"BOWL", "BOWLER", "AR", "ALL-ROUNDER", "ALL ROUNDER", "ALLROUNDER"}
WK_ROLES   = {"WK", "WICKETKEEPER", "WICKET-KEEPER", "WICKET KEEPER"}

def norm_role(s):        return str(s).strip().upper()
def can_bat(cat):        return norm_role(cat) in BAT_ROLES
def can_bowl(cat):       return norm_role(cat) in BOWL_ROLES
def is_wk(cat):          return norm_role(cat) in WK_ROLES
def is_overseas(nat):    return bool(nat) and norm_role(nat) not in ("INDIAN", "INDIA", "", "NAN")

def find_col(df, *candidates):
    """Return the first df column matching any candidate (case-insensitive, normalised)."""
    norm = lambda s: s.strip().lower().replace("_", " ").replace("-", " ")
    targets = {norm(c) for c in candidates}
    for col in df.columns:
        if norm(col) in targets:
            return col
    return None


# ── Squad validity helpers ─────────────────────────────────────────────────────

def role_counts(xi, role_map):
    """Return (batters, bowlers, wks) counts for an XI list."""
    cats = [role_map.get(p, '') for p in xi]
    return (
        sum(1 for c in cats if can_bat(c)),
        sum(1 for c in cats if can_bowl(c)),
        sum(1 for c in cats if is_wk(c)),
    )


def overseas_count(xi, nationality_map):
    """Return number of overseas players in an XI list."""
    return sum(1 for p in xi if is_overseas(nationality_map.get(p, '')))


def is_valid_swap(current_xi, candidate_xi, role_map, nationality_map):
    """Return True if swapping to candidate_xi respects role minimums and overseas cap.

    Role minimums: 7 batters, 5 bowlers, 1 WK — enforced only down to current count
    (handles squads already below threshold due to missing data).
    Overseas cap: max 4.
    """
    curr = role_counts(current_xi, role_map)
    new  = role_counts(candidate_xi, role_map)
    for cur_cnt, new_cnt, threshold in zip(curr, new, (7, 5, 1)):
        if new_cnt < min(cur_cnt, threshold):
            return False
    if overseas_count(candidate_xi, nationality_map) > 4:
        return False
    return True


def build_role_nat_maps(price_df, unsold_df):
    """Build role_map and nationality_map from pre-loaded price_list and unsold DataFrames.

    price_list takes priority; unsold fills any gaps.
    """
    role_map = {}
    nationality_map = {}

    _p_name = find_col(price_df, 'Player name', 'Player_name', 'Name')
    _p_role = find_col(price_df, 'Category', 'Role', 'Cat')
    _p_nat  = find_col(price_df, 'Nationality')
    if _p_name and _p_role:
        role_map.update(dict(zip(price_df[_p_name].str.strip(), price_df[_p_role].str.strip())))
    if _p_name and _p_nat:
        nationality_map.update(dict(zip(price_df[_p_name].str.strip(), price_df[_p_nat].str.strip())))

    _u_name = find_col(unsold_df, 'Player name', 'Player_name', 'Name')
    _u_role = find_col(unsold_df, 'Role', 'Category', 'Cat')
    _u_nat  = find_col(unsold_df, 'Nationality')
    if _u_name:
        for _, row in unsold_df.iterrows():
            nm = str(row[_u_name]).strip()
            if not nm:
                continue
            if _u_role and nm not in role_map:
                role_map[nm] = str(row[_u_role]).strip()
            if _u_nat and nm not in nationality_map:
                nationality_map[nm] = str(row[_u_nat]).strip()

    return role_map, nationality_map


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
