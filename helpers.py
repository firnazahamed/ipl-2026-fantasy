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
    for cur_cnt, new_cnt, threshold in zip(curr, new, (6, 5, 1)):
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


@st.cache_data(ttl=3600)
def load_hist_ownership_df() -> pd.DataFrame:
    """Read the pre-built historical ownership GSheet (2022-2025).

    Expected format: rows=players, columns=['Player', '2022', '2023', '2024', '2025'].
    Values in year columns are comma-separated owner names (or empty if unowned).
    Populated once via the run.ipynb 'Build historical ownership GSheet' cell.
    """
    from settings import hist_ownership_spreadsheet_url
    try:
        tabs = list_gsheet_tabs(hist_ownership_spreadsheet_url)
        if tabs:
            return read_gsheet(hist_ownership_spreadsheet_url, tabs[0])
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=3600)
def build_current_year_ownership() -> tuple:
    """Scan only the current year squad GSheets → ({player_lower: [owners]}, current_year).

    Only reads ~10 weekly tabs for one year — much faster than scanning all years.
    """
    import time
    from settings import hist_squads_by_year, owner_team_dict

    current_year = max(hist_squads_by_year.keys())
    url = hist_squads_by_year[current_year]

    _known_owners = set(owner_team_dict.keys())
    _STATS_HEADERS = {
        "name", "player", "player name", "player_name", "name_batting",
        "name_bowling", "team", "role", "category", "cat", "runs", "wickets",
        "matches", "points", "total", "total_points", "batting_points",
        "bowling_points", "fielding_points", "price", "nationality", "s.no",
        "sno", "sr", "economy", "econ", "balls", "overs", "catches",
        "stumpings", "owner", "unsold",
    }

    def _is_owner_col(col_s):
        if col_s in _known_owners:
            return True
        if "_" in col_s:
            return False
        try:
            int(col_s)
            return False
        except ValueError:
            pass
        return col_s.lower() not in _STATS_HEADERS

    result = {}  # player_lower → set(owners)
    try:
        tabs = list_gsheet_tabs(url)
        for tab in tabs:
            df = None
            for attempt in range(2):
                try:
                    df = read_gsheet(url, tab)
                    break
                except Exception:
                    if attempt == 0:
                        time.sleep(2)
            if df is None or df.empty:
                continue
            for col in df.columns:
                col_s = str(col).strip()
                if not col_s or not _is_owner_col(col_s):
                    continue
                for val in df[col].astype(str):
                    player = val.strip()
                    if not player or player.lower() in ("nan", "", "0"):
                        continue
                    p_lower = player.lower()
                    if p_lower not in result:
                        result[p_lower] = set()
                    result[p_lower].add(col_s)
    except Exception:
        pass

    return {k: list(v) for k, v in result.items()}, current_year


@st.cache_data(ttl=3600)
def get_ownership_history(player_name: str) -> dict:
    """Return {year: [owner, ...]} for every year the player appeared in any squad tab.

    Reads pre-built historical GSheet (2022-2025) in one API call, then live-scans
    only the current year (~10 tab reads). Much faster than scanning all years.
    """
    result = {}
    name_lower  = player_name.strip().lower()
    name_tokens = frozenset(name_lower.split())

    # ── 1. Historical years from pre-built GSheet ─────────────────────────────
    hist_df = load_hist_ownership_df()
    if not hist_df.empty:
        player_col = find_col(hist_df, 'Player')
        if player_col:
            year_cols = [c for c in hist_df.columns if c != player_col]

            # Exact match
            mask = hist_df[player_col].str.strip().str.lower() == name_lower
            match_row = hist_df[mask]

            # Token-based fallback: handles name variants
            if match_row.empty:
                for idx, row in hist_df.iterrows():
                    cell_tokens = frozenset(str(row[player_col]).strip().lower().split())
                    if name_tokens and name_tokens.issubset(cell_tokens):
                        match_row = hist_df.iloc[[idx]]
                        break

            if not match_row.empty:
                row = match_row.iloc[0]
                for yc in year_cols:
                    try:
                        year_int = int(yc)
                    except ValueError:
                        continue
                    val = str(row[yc]).strip()
                    if val and val.lower() not in ("", "nan"):
                        owners = [o.strip() for o in val.split(",") if o.strip()]
                        if owners:
                            result[year_int] = owners

    # ── 2. Current year (live scan, cached separately) ────────────────────────
    current_index, current_year = build_current_year_ownership()
    current_owners = current_index.get(name_lower)
    if not current_owners:
        for p_lower, owners in current_index.items():
            cell_tokens = frozenset(p_lower.split())
            if name_tokens and name_tokens.issubset(cell_tokens):
                current_owners = owners
                break
    if current_owners:
        result[current_year] = list(current_owners)

    return result


@st.cache_data(ttl=600)
def load_hist_points_df() -> pd.DataFrame:
    """Load the 7-year historical fantasy points GSheet (first tab).

    Expected format: rows = players, columns include a player-name column and
    year columns (e.g. 2019, 2020, ...).
    """
    from settings import hist_points_spreadsheet_url
    try:
        tabs = list_gsheet_tabs(hist_points_spreadsheet_url)
        if tabs:
            return read_gsheet(hist_points_spreadsheet_url, tabs[0])
    except Exception:
        pass
    return pd.DataFrame()


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
