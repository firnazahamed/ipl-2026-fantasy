import streamlit as st
from helpers import read_gsheet, list_gsheet_tabs, write_squad
from settings import (
    squads_spreadsheet_url,
    trades_spreadsheet_url,
    price_list_spreadsheet_url,
    unsold_spreadsheet_url,
    owner_team_dict,
    weeks,
    team_fixtures,
)

st.set_page_config(layout="wide")

# ── Role classification ────────────────────────────────────────────────────────
_BAT_ROLES  = {"BAT", "BATSMAN", "BATTER", "WK", "WICKETKEEPER", "WICKET-KEEPER",
               "WICKET KEEPER", "AR", "ALL-ROUNDER", "ALL ROUNDER", "ALLROUNDER"}
_BOWL_ROLES = {"BOWL", "BOWLER", "AR", "ALL-ROUNDER", "ALL ROUNDER", "ALLROUNDER"}
_WK_ROLES   = {"WK", "WICKETKEEPER", "WICKET-KEEPER", "WICKET KEEPER"}

def _norm(cat):         return str(cat).strip().upper()
def can_bat(cat):       return _norm(cat) in _BAT_ROLES
def can_bowl(cat):      return _norm(cat) in _BOWL_ROLES
def is_wk(cat):         return _norm(cat) in _WK_ROLES

# ── HTML badge helpers ─────────────────────────────────────────────────────────
_ROLE_STYLE = {
    "BAT":          ("#dbeafe", "#1e40af"),
    "BATSMAN":      ("#dbeafe", "#1e40af"),
    "BATTER":       ("#dbeafe", "#1e40af"),
    "BOWL":         ("#dcfce7", "#166534"),
    "BOWLER":       ("#dcfce7", "#166534"),
    "AR":           ("#f3e8ff", "#6b21a8"),
    "ALL-ROUNDER":  ("#f3e8ff", "#6b21a8"),
    "ALL ROUNDER":  ("#f3e8ff", "#6b21a8"),
    "ALLROUNDER":   ("#f3e8ff", "#6b21a8"),
    "WK":           ("#fef9c3", "#854d0e"),
    "WICKETKEEPER": ("#fef9c3", "#854d0e"),
    "WICKET-KEEPER":("#fef9c3", "#854d0e"),
    "WICKET KEEPER":("#fef9c3", "#854d0e"),
}
_ROLE_ICON = {
    "BAT": "🏏", "BATSMAN": "🏏", "BATTER": "🏏",
    "BOWL": "🎳", "BOWLER": "🎳",
    "AR": "⚡", "ALL-ROUNDER": "⚡", "ALL ROUNDER": "⚡", "ALLROUNDER": "⚡",
    "WK": "🧤", "WICKETKEEPER": "🧤", "WICKET-KEEPER": "🧤", "WICKET KEEPER": "🧤",
}

def _badge(label, bg, fg):
    return (
        f'<span style="background:{bg};color:{fg};padding:3px 10px;'
        f'border-radius:999px;font-size:13px;font-weight:700;'
        f'white-space:nowrap;display:inline-block">{label}</span>'
    )

def _role_badge_html(player):
    raw  = role_map.get(player, "")
    key  = _norm(raw)
    if not raw:
        return ""
    bg, fg = _ROLE_STYLE.get(key, ("#f3f4f6", "#374151"))
    icon   = _ROLE_ICON.get(key, "")
    return _badge(f"{icon} {raw}", bg, fg)

def _games_badge_html(player):
    team  = team_map.get(player, "")
    if not team:
        return ""
    games = games_for_team(team)
    team_html = _badge(team.upper(), "#e2e8f0", "#1e293b")
    if games is None:
        return team_html
    if games == 0:   bg, fg = "#fee2e2", "#991b1b"
    elif games == 1: bg, fg = "#fef3c7", "#92400e"
    elif games == 2: bg, fg = "#f3f4f6", "#374151"
    else:            bg, fg = "#d1fae5", "#065f46"
    games_html = _badge(f"{games} game{'s' if games != 1 else ''}", bg, fg)
    return f"{team_html}&nbsp;{games_html}"

def _player_html(player):
    role_b  = _role_badge_html(player)
    games_b = _games_badge_html(player)
    badges  = "&nbsp;&nbsp;".join(x for x in [games_b, role_b] if x)
    return (
        f'<div style="padding:4px 0">'
        f'<div style="font-size:15px;font-weight:600;margin-bottom:4px">{player}</div>'
        f'<div>{badges}</div>'
        f'</div>'
    )

def _section_label(text):
    return (
        f'<div style="font-size:11px;font-weight:700;letter-spacing:0.08em;'
        f'opacity:0.45;padding:6px 0 4px">{text}</div>'
    )

# ── Load reference data ────────────────────────────────────────────────────────
squad_tabs    = sorted(list_gsheet_tabs(squads_spreadsheet_url),
                       key=lambda x: int(x.replace("Week", "")))
price_list_df = read_gsheet(price_list_spreadsheet_url, "price_list")
unsold_df     = read_gsheet(unsold_spreadsheet_url, "Unsold_players")
week_options  = sorted(weeks.keys(), key=lambda x: int(x.replace("Week", "")))

role_map = {}
team_map = {}

if {"Player_name", "Category"}.issubset(price_list_df.columns):
    role_map.update(dict(zip(
        price_list_df["Player_name"].str.strip(),
        price_list_df["Category"].str.strip(),
    )))
if {"Player_name", "Team"}.issubset(price_list_df.columns):
    team_map.update(dict(zip(
        price_list_df["Player_name"].str.strip(),
        price_list_df["Team"].str.strip(),
    )))

_u_name = next((c for c in unsold_df.columns if c.strip().lower() == "player name"), None)
_u_role = next((c for c in unsold_df.columns if c.strip().lower() in {"role", "category"}), None)
_u_team = next((c for c in unsold_df.columns if c.strip().lower() == "team"), None)
if _u_name:
    for _, urow in unsold_df.iterrows():
        nm = str(urow[_u_name]).strip()
        if not nm:
            continue
        if _u_role and nm not in role_map:
            role_map[nm] = str(urow[_u_role]).strip()
        if _u_team and nm not in team_map:
            team_map[nm] = str(urow[_u_team]).strip()

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("## 📋 Submit Weekly Team")

col_owner, col_week = st.columns(2)
with col_owner:
    owner = st.selectbox(
        "Owner",
        sorted(owner_team_dict.keys()),
        format_func=lambda o: f"{o} — {owner_team_dict[o]}",
        label_visibility="collapsed",
    )
with col_week:
    submitted_weeks = set(squad_tabs)
    default_idx = next(
        (i for i, w in enumerate(week_options) if w not in submitted_weeks),
        len(week_options) - 1,
    )
    submit_week = st.selectbox(
        "Week", week_options, index=default_idx, label_visibility="collapsed"
    )

submit_week_num    = int(submit_week.replace("Week", ""))
_fixture_week_idx  = submit_week_num - 1

# ── Fixture helpers ────────────────────────────────────────────────────────────
def games_for_team(team):
    abbr     = str(team).strip().upper()
    fixtures = team_fixtures.get(abbr)
    if fixtures is None or _fixture_week_idx >= len(fixtures):
        return None
    return fixtures[_fixture_week_idx]

# ── Fixture cards ──────────────────────────────────────────────────────────────
st.markdown(f"**Fixtures — {submit_week}**")

if _fixture_week_idx < 8:
    _cards = []
    for team, counts in team_fixtures.items():
        g = counts[_fixture_week_idx]
        if g == 0:   bg, fg, label = "#fee2e2", "#991b1b", "No games"
        elif g == 1: bg, fg, label = "#fef3c7", "#92400e", "1 game"
        elif g == 2: bg, fg, label = "#f9fafb", "#374151", "2 games"
        else:        bg, fg, label = "#d1fae5", "#065f46", f"{g} games"
        _cards.append(
            f'<div style="background:{bg};color:{fg};border-radius:10px;padding:14px 10px;'
            f'text-align:center;flex:1;min-width:70px">'
            f'<div style="font-weight:800;font-size:14px">{team}</div>'
            f'<div style="font-size:28px;font-weight:800;margin:4px 0;line-height:1">{g}</div>'
            f'<div style="font-size:11px;opacity:0.85">{label}</div>'
            f'</div>'
        )
    st.markdown(
        '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:4px">'
        + "".join(_cards) + "</div>",
        unsafe_allow_html=True,
    )
else:
    st.caption("Fixture data not yet available for this week.")

st.divider()

# ── Load base squad ────────────────────────────────────────────────────────────
prev_week = next(
    (t for t in sorted(squad_tabs, key=lambda x: int(x.replace("Week", "")), reverse=True)
     if int(t.replace("Week", "")) < submit_week_num),
    None,
)

if prev_week:
    prev_df = read_gsheet(squads_spreadsheet_url, prev_week)
    if owner in prev_df.columns:
        owner_col  = prev_df[owner]
        prev_xi    = [p.strip() for p in owner_col[:11].tolist()   if p and str(p).strip()]
        prev_bench = [p.strip() for p in owner_col[15:19].tolist() if p and str(p).strip()]
        base_pool  = prev_xi + prev_bench
    else:
        base_pool, prev_xi = [], []
    st.caption(f"Base squad from **{prev_week}**")
else:
    base_pool, prev_xi = [], []
    st.caption("No previous week found — starting from scratch.")

# ── Apply trades ───────────────────────────────────────────────────────────────
applied_trades = []
squad_pool     = list(base_pool)

try:
    trades_df = read_gsheet(trades_spreadsheet_url, owner)
    for _, trow in trades_df.iterrows():
        eff   = str(trow.get("Trade effective", "")).strip().replace(" ", "")
        p_in  = str(trow.get("Player in",  "")).strip()
        p_out = str(trow.get("Player out", "")).strip()
        if eff != submit_week or not p_in or not p_out or p_in == "nan" or p_out == "nan":
            continue
        if p_out in squad_pool:
            squad_pool[squad_pool.index(p_out)] = p_in
        elif p_in not in squad_pool:
            squad_pool.append(p_in)
        applied_trades.append((p_out, p_in))
except Exception:
    pass

seen       = set()
squad_pool = [p for p in squad_pool if not (p in seen or seen.add(p))]

if applied_trades:
    msgs = " · ".join(f"~~{o}~~ → **{i}**" for o, i in applied_trades)
    st.info(f"Trades applied for {submit_week}: {msgs}")

# ── Default checkbox state (set once per owner+week) ──────────────────────────
default_xi = [p for p in prev_xi if p in squad_pool]
for p in squad_pool:
    if len(default_xi) >= 11:
        break
    if p not in default_xi:
        default_xi.append(p)

state_key = f"xi_{owner}_{submit_week}"
for p in squad_pool:
    cb_key = f"cb_{p}_{state_key}"
    if cb_key not in st.session_state:
        st.session_state[cb_key] = p in default_xi

# Current XI derived from checkbox state
xi_list    = [p for p in squad_pool if st.session_state.get(f"cb_{p}_{state_key}", False)]
bench_list = [p for p in squad_pool if p not in xi_list]
xi_full    = len(xi_list) >= 11
xi_count   = len(xi_list)

# ── Squad picker ───────────────────────────────────────────────────────────────
# Keep checkbox + player-info on the same line on mobile
st.markdown("""
<style>
div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stHorizontalBlock"] {
    flex-direction: row !important;
    align-items: center !important;
    flex-wrap: nowrap !important;
}
</style>
""", unsafe_allow_html=True)

ok_color = "#16a34a" if xi_count == 11 else "#dc2626" if xi_count > 11 else "#d97706"
st.markdown(
    f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">'
    f'<span style="font-size:16px;font-weight:700">Select Playing XI</span>'
    f'<span style="background:{ok_color};color:white;padding:2px 12px;'
    f'border-radius:999px;font-size:13px;font-weight:700">{xi_count} / 11</span>'
    f'</div>',
    unsafe_allow_html=True,
)

with st.container(border=True):
    # ── Playing XI section ─────────────────────────────────────────────────
    st.markdown(_section_label("PLAYING XI"), unsafe_allow_html=True)
    if xi_list:
        for p in xi_list:
            c_cb, c_info = st.columns([1, 9])
            with c_cb:
                st.checkbox("", key=f"cb_{p}_{state_key}", label_visibility="collapsed")
            c_info.markdown(_player_html(p), unsafe_allow_html=True)
    else:
        st.caption("No players selected yet — tick from the bench below.")

    # ── Bench section ──────────────────────────────────────────────────────
    st.markdown(
        f'<hr style="margin:10px 0;opacity:0.15">'
        + _section_label("BENCH"),
        unsafe_allow_html=True,
    )
    if bench_list:
        for p in bench_list:
            c_cb, c_info = st.columns([1, 9])
            with c_cb:
                st.checkbox("", key=f"cb_{p}_{state_key}", label_visibility="collapsed")
            alpha = "0.45" if xi_full else "1"
            c_info.markdown(
                f'<div style="opacity:{alpha}">{_player_html(p)}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("All 15 players are in the Playing XI.")

# Derive XI from checkbox state after all widgets have rendered
xi_list     = [p for p in squad_pool if st.session_state.get(f"cb_{p}_{state_key}", False)]
bench_list  = [p for p in squad_pool if p not in xi_list]
selected_xi = xi_list

# ── Captain & Vice-Captain ─────────────────────────────────────────────────────
st.divider()
captain      = None
vice_captain = None

if selected_xi:
    st.markdown("**Captain & Vice-Captain**")
    captain = st.selectbox("🟡 Captain (1.5×)", options=selected_xi)
    vc_opts      = [p for p in selected_xi if p != captain]
    vice_captain = st.selectbox("🟠 Vice-Captain (1.2×)", options=vc_opts) if vc_opts else None

# ── Combination check ──────────────────────────────────────────────────────────
st.divider()
batters    = sum(1 for p in selected_xi if can_bat(role_map.get(p, "")))
bowlers    = sum(1 for p in selected_xi if can_bowl(role_map.get(p, "")))
wk_count   = sum(1 for p in selected_xi if is_wk(role_map.get(p, "")))
combo_valid = batters >= 7 and bowlers >= 5 and wk_count >= 1

def _check_html(label, value, target):
    ok   = value >= target
    bg   = "#d1fae5" if ok else "#fee2e2"
    fg   = "#065f46" if ok else "#991b1b"
    icon = "✓" if ok else "✗"
    note = f"min {target} required" if ok else f"need {target - value} more"
    return (
        f'<div style="background:{bg};color:{fg};border-radius:10px;'
        f'padding:16px;text-align:center">'
        f'<div style="font-size:32px;font-weight:800;line-height:1">{icon} {value}</div>'
        f'<div style="font-weight:700;font-size:15px;margin:6px 0 2px">{label}</div>'
        f'<div style="font-size:12px;opacity:0.85">{note}</div>'
        f'</div>'
    )

st.markdown(
    f'<div style="display:flex;gap:10px;flex-wrap:wrap">'
    f'<div style="flex:1;min-width:110px">{_check_html("Can Bat",        batters,  7)}</div>'
    f'<div style="flex:1;min-width:110px">{_check_html("Can Bowl",       bowlers,  5)}</div>'
    f'<div style="flex:1;min-width:110px">{_check_html("Wicket-Keepers", wk_count, 1)}</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Submit ─────────────────────────────────────────────────────────────────────
st.divider()

all_valid = (
    len(selected_xi) == 11
    and captain is not None
    and vice_captain is not None
    and combo_valid
)

errors = []
if len(selected_xi) != 11:
    errors.append(f"Playing XI must be exactly 11 — currently {len(selected_xi)}.")
if not captain:
    errors.append("Captain not selected.")
if not vice_captain:
    errors.append("Vice-Captain not selected.")
if selected_xi and not combo_valid:
    if batters  < 7:  errors.append(f"Need at least 7 who can bat ({batters} now).")
    if bowlers  < 5:  errors.append(f"Need at least 5 who can bowl ({bowlers} now).")
    if wk_count < 1:  errors.append("Need at least 1 wicket-keeper in the XI.")
for e in errors:
    st.error(e)

if st.button("Submit Squad", type="primary", disabled=not all_valid, use_container_width=True):
    xi_rest    = [p for p in selected_xi if p not in (captain, vice_captain)]
    bench_pad  = (bench_list + [""] * 4)[:4]
    squad_rows = [captain, vice_captain] + xi_rest + bench_pad  # 15 rows

    with st.spinner(f"Saving {owner}'s squad for {submit_week}…"):
        write_squad(squads_spreadsheet_url, submit_week, owner, squad_rows)

    st.cache_data.clear()
    st.success(
        f"**{owner}** ({owner_team_dict[owner]}) — {submit_week} submitted!  \n"
        f"Captain: **{captain}** · Vice-Captain: **{vice_captain}**"
    )
