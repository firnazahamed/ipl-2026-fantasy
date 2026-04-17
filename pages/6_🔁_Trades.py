import re
import streamlit as st
import pandas as pd
from settings import owner_team_dict, trades_spreadsheet_url, bucket_name
from helpers import read_gsheet, find_col, read_file

st.set_page_config(layout="wide")
st.title("Trades")

# Load player weekly points once
player_weekly_df = read_file(bucket_name, "Outputs/weekly_player_points_df.csv")
week_cols = [c for c in player_weekly_df.columns if c.startswith("Week") and c.endswith("_points")]
available_weeks = {int(c.replace("Week", "").replace("_points", "")) for c in week_cols}

# Build normalised name → {week_num: points} lookup
def norm(s):
    return str(s).strip().lower()

points_lookup = {
    norm(row["Player"]): {
        int(c.replace("Week", "").replace("_points", "")): float(row[c])
        for c in week_cols
    }
    for _, row in player_weekly_df.iterrows()
}

owners = sorted(owner_team_dict.keys())
tabs = st.tabs(owners)

for tab, owner in zip(tabs, owners):
    with tab:
        st.caption(owner_team_dict[owner])
        trade_df = read_gsheet(trades_spreadsheet_url, owner)
        sno_col = find_col(trade_df, "S.no", "S no", "S_no", "Sno", "Serial")
        if sno_col:
            trade_df = trade_df.set_index(sno_col)
        st.dataframe(trade_df, use_container_width=True, height=(len(trade_df) + 1) * 35 + 3)

        # ── Trade Impact Analysis ────────────────────────────────────────────
        st.subheader("Trade Impact")

        player_in_col  = find_col(trade_df, "Player in",  "Player_in")
        player_out_col = find_col(trade_df, "Player out", "Player_out")
        effective_col  = find_col(trade_df, "Trade effective", "Trade_effective", "Effective")

        if not (player_in_col and player_out_col and effective_col):
            st.caption("Trade columns not found.")
            continue

        valid = trade_df[
            trade_df[player_in_col].str.strip().astype(bool) &
            trade_df[player_out_col].str.strip().astype(bool) &
            trade_df[effective_col].str.strip().astype(bool)
        ]

        if valid.empty:
            st.caption("No trades to analyse yet.")
            continue

        rows = []
        for _, row in valid.iterrows():
            p_in  = row[player_in_col].strip()
            p_out = row[player_out_col].strip()
            eff   = row[effective_col].strip()

            m = re.search(r'\d+', eff)
            if not m:
                continue
            eff_week = int(m.group())

            future = sorted(w for w in available_weeks if w >= eff_week)

            pts_in  = sum(points_lookup.get(norm(p_in),  {}).get(w, 0) for w in future)
            pts_out = sum(points_lookup.get(norm(p_out), {}).get(w, 0) for w in future)
            net     = pts_in - pts_out

            rows.append({
                "Player In":      p_in,
                "Player Out":     p_out,
                "From":           eff,
                "Gained (In)":    round(pts_in,  1),
                "Given Up (Out)": round(pts_out, 1),
                "Net":            round(net,     1),
            })

        if not rows:
            st.caption("No complete trade data to analyse.")
            continue

        impact_df = pd.DataFrame(rows)

        def _color_net(val):
            if val > 0:
                return "color: green; font-weight: bold"
            if val < 0:
                return "color: red; font-weight: bold"
            return "color: gray"

        num_cols = ["Gained (In)", "Given Up (Out)", "Net"]
        styler = impact_df.style.format("{:.0f}", subset=num_cols)
        _color_method = "map" if hasattr(styler, "map") else "applymap"
        styled = getattr(styler, _color_method)(_color_net, subset=["Net"])
        st.dataframe(styled, use_container_width=True, hide_index=True,
                     height=(len(impact_df) + 1) * 35 + 3)

        total_net = round(impact_df["Net"].sum(), 1)
        sign      = "+" if total_net > 0 else ""
        colour    = "green" if total_net > 0 else ("red" if total_net < 0 else "gray")
        st.markdown(
            f"**Overall trade impact:** "
            f"<span style='color:{colour}; font-weight:bold'>{sign}{total_net} pts</span>",
            unsafe_allow_html=True,
        )
        st.caption("Points counted from effective week onwards. Net = Gained − Given Up. Raw player points — no captaincy or bench multipliers.")
