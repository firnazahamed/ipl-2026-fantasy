import streamlit as st
import pandas as pd
from helpers import read_gsheet, list_gsheet_tabs
from settings import squads_spreadsheet_url, owner_team_dict

st.set_page_config(layout="wide")
st.title("Squads")

# ── Week selector ─────────────────────────────────────────────────────────────
squads = sorted(list_gsheet_tabs(squads_spreadsheet_url), reverse=True)
col_sel, _ = st.columns([2, 6])
with col_sel:
    option = st.selectbox("Select week", squads)

# ── Load & parse ──────────────────────────────────────────────────────────────
# GSheet layout (0-indexed after header):
#   0–10  → Playing XI  (0 = captain, 1 = vice-captain)
#   11–14 → Empty separator rows
#   15–18 → Bench (up to 4 players)
squad_df = read_gsheet(squads_spreadsheet_url, option)
xi_df    = squad_df.iloc[0:11].reset_index(drop=True)
bench_df = squad_df.iloc[15:19].reset_index(drop=True)

owners = [col for col in squad_df.columns if col.strip()]

# Slot labels used as the index in the Compare view
XI_SLOTS    = ["C", "VC"] + [str(i) for i in range(3, 12)]
BENCH_SLOTS = ["B1", "B2", "B3", "B4"]

# ── Shared helpers ────────────────────────────────────────────────────────────
def badge(text, bg, fg="#fff"):
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 7px;'
        f'border-radius:4px;font-size:11px;font-weight:700;'
        f'margin-left:6px;vertical-align:middle;">{text}</span>'
    )

def player_row(name, slot, border=True):
    """Render one player as an HTML row with optional C/VC badge."""
    b = ""
    if slot == "C":
        b = badge("C", "#c9a227", "#000")
    elif slot == "VC":
        b = badge("VC", "#6c757d")
    border_style = "border-bottom:1px solid rgba(128,128,128,0.2);" if border else ""
    return (
        f'<div style="display:flex;align-items:center;padding:7px 4px;{border_style}">'
        f'<span style="color:rgba(128,128,128,0.7);font-size:12px;width:28px;">{slot}</span>'
        f'<span style="flex:1;">{name}</span>{b}'
        f'</div>'
    )

def squad_card(owner):
    xi_players    = xi_df[owner].tolist()
    bench_players = [p for p in bench_df[owner].tolist() if p.strip()]

    xi_html = "".join(
        player_row(p, XI_SLOTS[i], border=(i < 10))
        for i, p in enumerate(xi_players)
        if p.strip()
    )
    bench_html = "".join(
        player_row(p, f"B{i+1}", border=(i < len(bench_players) - 1))
        for i, p in enumerate(bench_players)
    ) or '<div style="color:rgba(128,128,128,0.5);padding:6px 4px;font-size:13px;">—</div>'

    return f"""
<div style="border:1px solid rgba(128,128,128,0.25);border-radius:10px;
            padding:14px 16px;height:100%;box-sizing:border-box;">
  <div style="font-size:13px;font-weight:600;letter-spacing:.4px;
              text-transform:uppercase;margin-bottom:10px;
              color:rgba(128,128,128,0.8);">Playing XI</div>
  {xi_html}
  <div style="font-size:13px;font-weight:600;letter-spacing:.4px;
              text-transform:uppercase;margin:14px 0 8px;
              color:rgba(128,128,128,0.8);">Bench</div>
  {bench_html}
</div>
"""

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_compare, tab_individual = st.tabs(["Compare All", "Individual Squads"])

# ── Compare All ───────────────────────────────────────────────────────────────
with tab_compare:
    def section_df(raw_df, slots):
        rows = []
        for i, slot in enumerate(slots):
            row = {"": slot}
            for owner in owners:
                row[owner] = raw_df[owner].iloc[i] if i < len(raw_df) else ""
            rows.append(row)
        return pd.DataFrame(rows).set_index("")

    st.caption("Playing XI")
    st.dataframe(section_df(xi_df, XI_SLOTS), use_container_width=True)

    st.caption("Bench")
    st.dataframe(section_df(bench_df, BENCH_SLOTS), use_container_width=True)

# ── Individual Squads ─────────────────────────────────────────────────────────
with tab_individual:
    # Two rows of owner buttons; clicking shows their squad card below
    if "squad_owner" not in st.session_state:
        st.session_state.squad_owner = owners[0]

    # Pill-style owner selector
    cols = st.columns(len(owners))
    for col, owner in zip(cols, owners):
        with col:
            if st.button(owner, use_container_width=True,
                         type="primary" if st.session_state.squad_owner == owner else "secondary"):
                st.session_state.squad_owner = owner

    st.markdown(
        f"### {owner_team_dict.get(st.session_state.squad_owner, st.session_state.squad_owner)}",
    )
    st.html(squad_card(st.session_state.squad_owner))
