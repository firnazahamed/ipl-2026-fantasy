import streamlit as st
import pandas as pd
from helpers import read_gsheet, list_gsheet_tabs, read_file, build_role_nat_maps, find_col
from get_bench_subs import compute_subs_core
from settings import (
    squads_spreadsheet_url,
    owner_team_dict,
    bucket_name,
    weeks as WEEKS,
    player_id_dict,
    price_list_spreadsheet_url,
    unsold_spreadsheet_url,
)

# IPL franchise brand colours — (background, text)
# Chosen for maximum visual distinction, not raw brand accuracy
TEAM_COLORS = {
    "CSK":  ("rgba(246,196,22,0.5)",   "#000"),   # yellow
    "DC":   ("rgba(0,90,200,0.5)",     "#fff"),   # royal blue
    "GT":   ("rgba(180,138,36,0.5)",   "#000"),   # gold (more distinctive than their navy)
    "KKR":  ("rgba(110,30,150,0.5)",   "#fff"),   # vibrant purple
    "LSG":  ("rgba(0,188,212,0.5)",    "#000"),   # cyan/teal
    "MI":   ("rgba(0,40,110,0.5)",     "#fff"),   # deep navy
    "PBKS": ("rgba(237,27,36,0.5)",    "#fff"),   # red
    "RCB":  ("rgba(180,10,30,0.5)",    "#fff"),   # dark crimson
    "RR":   ("rgba(220,30,120,0.5)",   "#fff"),   # hot pink/magenta
    "SRH":  ("rgba(239,95,0,0.5)",     "#000"),   # orange
}

@st.cache_data(ttl=600)
def _load_player_team_map():
    try:
        df = read_gsheet(price_list_spreadsheet_url, "price_list")
        name_col = find_col(df, "Player_name", "Player name", "Name")
        team_col = find_col(df, "Team", "IPL Team", "Franchise")
        if name_col and team_col:
            return dict(zip(df[name_col].str.strip(), df[team_col].str.strip()))
    except Exception:
        pass
    return {}

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
#   11–14 → Substitutions made this week (bench player subbed in, 0–4 per owner)
#   15–18 → Bench (up to 4 players)
squad_df = read_gsheet(squads_spreadsheet_url, option)
xi_df    = squad_df.iloc[0:11].reset_index(drop=True)
subs_df  = squad_df.iloc[11:15].reset_index(drop=True)
bench_df = squad_df.iloc[15:19].reset_index(drop=True)

player_team_map = _load_player_team_map()

owners = [col for col in squad_df.columns if col.strip()]

# Slot labels used as the index in the Compare view
XI_SLOTS    = ["C", "VC"] + [str(i) for i in range(3, 12)]
SUBS_SLOTS  = ["S1", "S2", "S3", "S4"]
BENCH_SLOTS = ["B1", "B2", "B3", "B4"]

# ── Shared helpers ────────────────────────────────────────────────────────────
def badge(text, bg, fg="#fff"):
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 7px;'
        f'border-radius:4px;font-size:11px;font-weight:700;'
        f'margin-left:6px;vertical-align:middle;">{text}</span>'
    )

def player_row(name, slot, border=True, team=None):
    """Render one player as an HTML row with optional C/VC badge and team chip."""
    b = ""
    if slot == "C":
        b = badge("C", "#c9a227", "#000")
    elif slot == "VC":
        b = badge("VC", "#6c757d")
    team_chip = ""
    if team and team in TEAM_COLORS:
        bg, _ = TEAM_COLORS[team]
        solid = bg.replace("0.5)", "1)")
        tint  = bg.replace("0.5)", "0.18)")
        team_chip = (
            f'<span style="background:{tint};color:{solid};border:1px solid {solid};'
            f'padding:1px 5px;border-radius:3px;font-size:10px;font-weight:700;margin-left:5px;">'
            f'{team}</span>'
        )
    border_style = "border-bottom:1px solid rgba(128,128,128,0.2);" if border else ""
    return (
        f'<div style="display:flex;align-items:center;padding:7px 4px;{border_style}">'
        f'<span style="color:rgba(128,128,128,0.7);font-size:12px;width:28px;">{slot}</span>'
        f'<span style="flex:1;">{name}</span>{team_chip}{b}'
        f'</div>'
    )

def squad_card(owner):
    xi_players    = xi_df[owner].tolist()
    subs_players  = [p for p in subs_df[owner].tolist() if str(p).strip()]
    bench_players = [p for p in bench_df[owner].tolist() if str(p).strip()]

    xi_html = "".join(
        player_row(p, XI_SLOTS[i], border=(i < 10), team=player_team_map.get(p))
        for i, p in enumerate(xi_players)
        if str(p).strip()
    )
    bench_html = "".join(
        player_row(p, f"B{i+1}", border=(i < len(bench_players) - 1), team=player_team_map.get(p))
        for i, p in enumerate(bench_players)
    ) or '<div style="color:rgba(128,128,128,0.5);padding:6px 4px;font-size:13px;">—</div>'

    subs_section_html = ""
    if subs_players:
        subs_html = "".join(
            player_row(p, f"S{i+1}", border=(i < len(subs_players) - 1), team=player_team_map.get(p))
            for i, p in enumerate(subs_players)
        )
        subs_section_html = f"""
  <div style="font-size:13px;font-weight:600;letter-spacing:.4px;
              text-transform:uppercase;margin:14px 0 8px;
              color:rgba(128,128,128,0.8);">Substitutions</div>
  {subs_html}"""

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
  {bench_html}{subs_section_html}
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
                name = raw_df[owner].iloc[i] if i < len(raw_df) else ""
                team = player_team_map.get(str(name).strip(), "")
                row[owner] = f"{name} · {team}" if name and team else name
            rows.append(row)
        return pd.DataFrame(rows).set_index("")

    def _team_cell_style(val):
        parts = str(val).rsplit(" · ", 1)
        team = parts[-1].strip() if len(parts) == 2 else player_team_map.get(str(val).strip(), "")
        if team and team in TEAM_COLORS:
            bg, _ = TEAM_COLORS[team]
            tint = bg.replace("0.5)", "0.12)")
            return f"background-color:{tint};border-left:3px solid {bg};"
        return ""

    xi_section    = section_df(xi_df, XI_SLOTS)
    bench_section = section_df(bench_df, BENCH_SLOTS)

    def separator(label):
        df = pd.DataFrame([{o: "" for o in owners}], index=[label])
        df.index.name = ""
        return df

    any_subs = subs_df[owners].apply(lambda c: c.str.strip().ne("")).any().any()
    parts = [xi_section, separator("── BENCH ──"), bench_section]
    total_rows = len(XI_SLOTS) + 1 + len(BENCH_SLOTS)
    if any_subs:
        subs_section = section_df(subs_df, SUBS_SLOTS)
        parts += [separator("── SUBS ──"), subs_section]
        total_rows += 1 + len(SUBS_SLOTS)
    combined = pd.concat(parts)
    st.dataframe(
        combined.style.applymap(_team_cell_style),
        use_container_width=True,
        height=(total_rows + 1) * 35 + 3,
    )

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


# ── Bench Substitution Suggestions ───────────────────────────────────────────

def _load_role_nat_maps():
    """Load price_list and unsold from GSheets and return role/nationality maps."""
    try:
        price_df  = read_gsheet(price_list_spreadsheet_url, 'price_list')
        unsold_df = read_gsheet(unsold_spreadsheet_url, 'Unsold_players')
        return build_role_nat_maps(price_df, unsold_df)
    except Exception:
        return {}, {}


def compute_bench_subs(week, raw_squad_df, player_weekly_pts_df):
    """Return bench sub suggestions for all owners for *week*.

    Loads scorecards from GCS and role/nationality maps from GSheets,
    then delegates to compute_subs_core.

    Returns [] if no games have been scored this week yet.
    """
    week_col = f'{week}_points'
    if week_col not in player_weekly_pts_df.columns:
        return []

    players_who_played = set()
    for match_id in WEEKS.get(week, {}).get('matches', []):
        try:
            sc = read_file(bucket_name, f"Scorecards/{match_id}_scorecard.csv")
            players_who_played.update(sc['Player_id'].dropna().astype(int).tolist())
        except Exception:
            pass

    if not players_who_played:
        return []

    player_pts = (
        player_weekly_pts_df
        .set_index('Player')[week_col]
        .fillna(0)
        .apply(float)
        .to_dict()
    )

    role_map, nationality_map = _load_role_nat_maps()
    return compute_subs_core(raw_squad_df, players_who_played, role_map, nationality_map, player_pts)


# ── Team colour legend ────────────────────────────────────────────────────────
chips = " ".join(
    f'<span style="background:{bg.replace("0.5)","0.18)")};color:{bg.replace("0.5)","1)")};'
    f'border:1px solid {bg.replace("0.5)","1)")};'
    f'padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;margin:2px 3px;'
    f'display:inline-block;">{team}</span>'
    for team, (bg, _) in TEAM_COLORS.items()
)
st.html(f'<div style="margin-top:8px;margin-bottom:4px;">{chips}</div>')

st.divider()
st.subheader(f"Bench Substitution Suggestions — {option}")
st.caption("Based on scorecards loaded so far this week. Points shown are bench rate (½ × raw).")

try:
    player_weekly_pts_df = read_file(bucket_name, "Outputs/weekly_player_points_df.csv")
    subs_data = compute_bench_subs(option, squad_df, player_weekly_pts_df)

    if not subs_data:
        st.info("No bench substitutions available yet — either no games have been scored this week, or no swaps are needed.")
    else:
        COLS = 3
        for row_start in range(0, len(subs_data), COLS):
            cols = st.columns(COLS)
            for j, entry in enumerate(subs_data[row_start:row_start + COLS]):
                with cols[j]:
                    total_half_pts = sum(pts / 2 for _, _, pts in entry['subs'])
                    st.markdown(
                        f"**{entry['owner']}** &nbsp;·&nbsp; "
                        f"<span style='color:rgba(128,128,128,0.8);font-size:13px;'>{entry['team']}</span>",
                        unsafe_allow_html=True,
                    )
                    rows_html = ""
                    for out_p, in_p, pts in entry['subs']:
                        half = pts / 2
                        rows_html += (
                            f'<div style="display:flex;align-items:center;gap:6px;'
                            f'padding:6px 0;border-bottom:1px solid rgba(128,128,128,0.15);">'
                            f'<span style="color:#e05c5c;font-size:12px;font-weight:600;'
                            f'min-width:30px;">OUT</span>'
                            f'<span style="flex:1;font-size:13px;">{out_p}</span>'
                            f'</div>'
                            f'<div style="display:flex;align-items:center;gap:6px;'
                            f'padding:6px 0;border-bottom:1px solid rgba(128,128,128,0.2);">'
                            f'<span style="color:#4caf87;font-size:12px;font-weight:600;'
                            f'min-width:30px;">IN</span>'
                            f'<span style="flex:1;font-size:13px;">{in_p}</span>'
                            f'<span style="font-size:12px;font-weight:700;color:#4caf87;'
                            f'white-space:nowrap;">+{half:.0f} pts</span>'
                            f'</div>'
                        )
                    rows_html += (
                        f'<div style="margin-top:8px;font-size:11px;'
                        f'color:rgba(128,128,128,0.7);">'
                        f'XI check · bat {entry["bat"]} · bowl {entry["bowl"]} · '
                        f'WK {entry["wk"]} · overseas {entry["overseas"]}/4'
                        f'</div>'
                        f'<div style="margin-top:4px;font-size:12px;font-weight:600;">'
                        f'Total on offer: +{total_half_pts:.0f} pts</div>'
                    )
                    st.html(
                        f'<div style="border:1px solid rgba(128,128,128,0.25);'
                        f'border-radius:8px;padding:12px 14px;">{rows_html}</div>'
                    )

except Exception as e:
    st.warning(f"Could not load bench sub data: {e}")
