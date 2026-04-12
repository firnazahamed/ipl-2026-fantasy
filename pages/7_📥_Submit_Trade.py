import streamlit as st
from helpers import (
    read_gsheet, list_gsheet_tabs,
    write_trade, remove_player_from_unsold, add_player_to_unsold,
    find_col,
)
from settings import (
    squads_spreadsheet_url, unsold_spreadsheet_url,
    trades_spreadsheet_url, price_list_spreadsheet_url,
    owner_team_dict, weeks,
)

st.set_page_config(layout="wide")
st.title("Submit Trade")

# ── Load data ─────────────────────────────────────────────────────────────────
squad_tabs    = sorted(list_gsheet_tabs(squads_spreadsheet_url), key=lambda x: int(x.replace("Week", "")))
latest_week   = squad_tabs[-1]
squad_df      = read_gsheet(squads_spreadsheet_url, latest_week)
unsold_df     = read_gsheet(unsold_spreadsheet_url, "Unsold_players")
price_list_df = read_gsheet(price_list_spreadsheet_url, "price_list")
player_name_col = next(c for c in unsold_df.columns if c.strip().lower() == "player name")
unsold_names = sorted(unsold_df[player_name_col].dropna().tolist())
week_options = sorted(weeks.keys(), key=lambda x: int(x.replace("Week", "")))

st.caption(f"Squad based on {latest_week}")
st.divider()

# ── Form ──────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2, gap="large")

with col_left:
    st.subheader("Trade Details")

    owner = st.selectbox("Owner", sorted(owner_team_dict.keys()),
                         format_func=lambda o: f"{o} — {owner_team_dict[o]}")

    owner_squad = sorted([p for p in squad_df[owner].tolist() if p and p.strip()])
    player_out  = st.selectbox("Player Out", owner_squad)

    transfer_type = st.radio("Transfer Type", ["Unsold Trade", "Injury Replacement"],
                             help="Unsold Trade: swap with someone from the unsold pool. "
                                  "Injury Replacement: replace an injured player with anyone.")

    week_effective = st.selectbox("Week Effective", week_options)

with col_right:
    st.subheader("Player In")

    input_method = st.radio("Select player from", ["Unsold pool", "Enter name manually"],
                            horizontal=True)

    if input_method == "Unsold pool":
        player_in = st.selectbox("Player In", unsold_names)
    else:
        player_in = st.text_input("Player In", placeholder="Enter player name")

    from_unsold_pool = input_method == "Unsold pool"

    if transfer_type == "Unsold Trade":
        st.info("The outgoing player will be added back to the unsold pool.")
    else:
        st.info("The outgoing player will NOT be returned to the unsold pool.")

# ── Validation & submit ───────────────────────────────────────────────────────
st.divider()

col_summary, col_btn = st.columns([3, 1])

with col_summary:
    if player_in and str(player_in).strip():
        st.markdown(
            f"**{owner}** ({owner_team_dict[owner]}) — "
            f"**{player_out}** out / **{player_in}** in &nbsp;·&nbsp; "
            f"{transfer_type} &nbsp;·&nbsp; Effective {week_effective}"
        )

with col_btn:
    submit = st.button("✅ Submit Trade", type="primary", use_container_width=True)

if submit:
    errors = []
    if not player_out:
        errors.append("No player selected to trade out.")
    if not player_in or not str(player_in).strip():
        errors.append("Player In cannot be empty.")
    if transfer_type == "Unsold Trade" and player_in == player_out:
        errors.append("Player In and Player Out cannot be the same player.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        with st.spinner("Submitting trade..."):
            write_trade(
                trades_spreadsheet_url, owner,
                transfer_type, str(player_in).strip(), player_out, week_effective,
            )
            if from_unsold_pool:
                remove_player_from_unsold(unsold_spreadsheet_url, player_in)
            if transfer_type == "Unsold Trade":
                _pl_name_col  = find_col(price_list_df, "Player_name", "Player name", "Player Name", "Name")
                _pl_team_col  = find_col(price_list_df, "Team", "IPL Team", "Franchise")
                _pl_cat_col   = find_col(price_list_df, "Category", "Role", "Cat")
                _pl_price_col = find_col(price_list_df, "Price", "Auction Price", "Cost")
                match = (
                    price_list_df[price_list_df[_pl_name_col] == player_out]
                    if _pl_name_col else price_list_df.iloc[0:0]
                )
                if not match.empty:
                    row = match.iloc[0]
                    add_player_to_unsold(
                        unsold_spreadsheet_url, player_out,
                        team=row[_pl_team_col] if _pl_team_col else None,
                        role=row[_pl_cat_col]  if _pl_cat_col  else None,
                        price=row[_pl_price_col] if _pl_price_col else None,
                    )
                else:
                    add_player_to_unsold(unsold_spreadsheet_url, player_out)

        st.cache_data.clear()
        st.success(
            f"Trade submitted! **{player_out}** → **{player_in}** "
            f"({transfer_type}, effective {week_effective})"
        )
