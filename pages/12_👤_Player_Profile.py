import base64
import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO

from helpers import (
    read_file,
    read_gsheet,
    list_gsheet_tabs,
    find_col,
    get_client,
    get_ownership_history,
    load_hist_points_df,
    load_hist_ownership_df,
)
from settings import (
    bucket_name,
    player_id_dict,
    owner_team_dict,
    price_list_spreadsheet_url,
    OWNER_PALETTE,
    hist_squads_by_year,
)

st.set_page_config(layout="wide", page_title="Player Profile", page_icon="👤")

# ── Role helpers ──────────────────────────────────────────────────────────────

_ROLE_SHORT = {
    "BAT": "BAT", "BATSMAN": "BAT", "BATTER": "BAT",
    "BOWL": "BOWL", "BOWLER": "BOWL",
    "AR": "AR", "ALLROUNDER": "AR", "ALL-ROUNDER": "AR", "ALL ROUNDER": "AR",
    "WK": "WK", "WICKETKEEPER": "WK", "WICKET-KEEPER": "WK", "WICKET KEEPER": "WK",
}
_ROLE_STYLE = {
    "BAT":  ("#3b82f6", "#1d4ed8"),
    "BOWL": ("#16a34a", "#166534"),
    "AR":   ("#d97706", "#92400e"),
    "WK":   ("#9333ea", "#581c87"),
}

def short_role(r: str) -> str:
    return _ROLE_SHORT.get(str(r).strip().upper(), str(r).strip().upper())

def role_style(r: str):
    return _ROLE_STYLE.get(short_role(r), ("#6b7280", "#374151"))


# ── Cached loaders ────────────────────────────────────────────────────────────

@st.cache_data(ttl=600)
def _load_price_df():
    return read_gsheet(price_list_spreadsheet_url, "price_list")

@st.cache_data(ttl=600)
def _load_agg_df():
    return read_file(bucket_name, "Outputs/agg_points_df.csv")

@st.cache_data(ttl=600)
def _load_score_df():
    return read_file(bucket_name, "Outputs/score_df.csv")

_IPL_CDN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":  "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.iplt20.com/",
}


@st.cache_data(ttl=86400)
def _player_photo_b64(player_id, player_name):
    """Fetch a player headshot from the IPL official CDN.

    URL pattern: https://scores.iplt20.com/ipl/playerimages/{Player+Name}.png
    Falls back to None (initials avatar) if the image is unavailable.
    """
    if not player_name:
        return None
    encoded = player_name.strip().replace(" ", "+")
    url = f"https://scores.iplt20.com/ipl/playerimages/{encoded}.png"
    try:
        r = requests.get(url, timeout=6, headers=_IPL_CDN_HEADERS)
        ct = r.headers.get("content-type", "")
        if r.status_code == 200 and "image" in ct and "html" not in ct:
            enc = base64.b64encode(r.content).decode()
            return f"data:{ct.split(';')[0].strip()};base64,{enc}"
    except Exception:
        pass
    return None


def _initials_avatar(name, bg="#4b5563"):
    """Generate an inline SVG initials avatar as a base64 data-URI."""
    parts = name.split()
    initials = (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else name[:2].upper()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        f'<circle cx="50" cy="50" r="50" fill="{bg}"/>'
        f'<text x="50" y="50" dominant-baseline="central" text-anchor="middle" '
        f'font-size="38" font-weight="700" font-family="sans-serif" fill="#fff">'
        f'{initials}</text></svg>'
    )
    enc = base64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{enc}"

@st.cache_data(ttl=600)
def _load_all_scorecards() -> pd.DataFrame:
    """Concatenate every match scorecard from GCS into one DataFrame."""
    client = get_client()
    dfs = []
    for blob in client.list_blobs(bucket_name, prefix="Scorecards/"):
        if not blob.name.endswith("_scorecard.csv"):
            continue
        match_id = blob.name.split("/")[-1].replace("_scorecard.csv", "")
        try:
            df = pd.read_csv(BytesIO(blob.download_as_bytes()))
            df["match_id"] = match_id
            dfs.append(df)
        except Exception:
            pass
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


# ── Tiny UI helpers ───────────────────────────────────────────────────────────

def _badge(text: str, bg: str, fg: str = "#fff", radius: int = 20) -> str:
    return (
        f'<span style="background:{bg};color:{fg};padding:4px 13px;'
        f'border-radius:{radius}px;font-size:13px;font-weight:600;">{text}</span>'
    )

def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

def _col_val(row: pd.Series, df: pd.DataFrame, *candidates) -> float:
    col = find_col(df, *candidates)
    return _safe_float(row[col]) if col and col in row.index else 0.0


# ── Load always-needed data ───────────────────────────────────────────────────

price_df = _load_price_df()
agg_df   = _load_agg_df()

_name_col  = find_col(price_df, "Player_name", "Player name", "Name")
_team_col  = find_col(price_df, "Team", "IPL Team", "Franchise")
_cat_col   = find_col(price_df, "Category", "Role")
_price_col = find_col(price_df, "Price")
_nat_col   = find_col(price_df, "Nationality")
_agg_name  = find_col(agg_df,   "Name_batting", "Name", "Player")
_agg_tot   = find_col(agg_df,   "total_points", "Total_points", "Total")


# ── Build full player list (current season + all historical owners) ────────────

def _all_players():
    names = set(player_id_dict.keys())
    try:
        hist_own = load_hist_ownership_df()
        p_col = find_col(hist_own, "Player")
        if p_col:
            names.update(hist_own[p_col].astype(str).str.strip().tolist())
    except Exception:
        pass
    names.discard("")
    names.discard("nan")
    return sorted(names)


# ── Page title + selector ─────────────────────────────────────────────────────

st.title("Player Profile")

sel_col, _ = st.columns([3, 5])
with sel_col:
    selected = st.selectbox(
        "Select player",
        _all_players(),
        index=None,
        placeholder="Type to search...",
    )


if not selected:
    st.info("Select a player above to view their profile.")
    st.stop()


# ── Gather player metadata ────────────────────────────────────────────────────

player_id = player_id_dict.get(selected, "")

p_row = (
    price_df[price_df[_name_col].str.strip() == selected]
    if _name_col else pd.DataFrame()
)

def _pval(col):
    return p_row[col].iloc[0].strip() if not p_row.empty and col else "—"

player_team  = _pval(_team_col)
player_role  = _pval(_cat_col)
player_price = _pval(_price_col)
player_nat   = _pval(_nat_col)
role_bg, _   = role_style(player_role)

# Current 2026 owner from score_df
current_owner = None
try:
    sdf      = _load_score_df()
    pid_col  = find_col(sdf, "Player_id", "player_id")
    own_col  = find_col(sdf, "Owner", "owner")
    if pid_col and own_col and player_id:
        last = sdf.drop_duplicates(subset=pid_col, keep="last")
        pid_int = int(player_id)
        row_match = last[
            last[pid_col].astype(str).str.replace(r"\.0$", "", regex=True) == str(pid_int)
        ]
        if not row_match.empty:
            current_owner = row_match[own_col].iloc[0]
except Exception:
    pass


# ── 1. Hero Card ──────────────────────────────────────────────────────────────

# Photo: try real Cricinfo headshot first, fall back to styled initials avatar
avatar_bg  = OWNER_PALETTE.get(current_owner, role_bg) if current_owner else role_bg
photo_src  = _player_photo_b64(player_id, selected) or _initials_avatar(selected, avatar_bg)

owned_html = ""
if current_owner:
    oc = OWNER_PALETTE.get(current_owner, "#6b7280")
    team_name = owner_team_dict.get(current_owner, "")
    owned_html = (
        f'<div style="margin-top:14px;font-size:14px;color:rgba(255,255,255,0.6);">'
        f'2026 owner&nbsp;&nbsp;'
        f'<span style="background:{oc};color:#1a1a1a;padding:3px 13px;'
        f'border-radius:12px;font-weight:700;font-size:14px;">{current_owner}</span>'
        f'&nbsp;<span style="font-size:13px;color:rgba(255,255,255,0.4);">{team_name}</span>'
        f'</div>'
    )

nat_icon = "🇮🇳" if player_nat.lower() in ("indian", "india") else "🌍"

st.html(f"""
<div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 55%,#0f3460 100%);
            border-radius:16px;padding:20px 24px;display:flex;align-items:center;
            flex-wrap:wrap;gap:20px;border:1px solid rgba(255,255,255,0.1);margin-bottom:4px;">
  <img src="{photo_src}"
       style="width:90px;height:90px;border-radius:50%;object-fit:cover;
              border:3px solid rgba(255,255,255,0.2);background:#444;flex-shrink:0;">
  <div style="flex:1;min-width:180px;">
    <div style="font-size:26px;font-weight:800;color:#fff;
                letter-spacing:-0.5px;line-height:1.1;">{selected}</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;">
      {_badge(short_role(player_role), role_bg)}
      {_badge(player_team, "rgba(255,255,255,0.15)")}
      {_badge(f"{nat_icon} {player_nat}", "rgba(255,255,255,0.08)", "rgba(255,255,255,0.8)")}
      {_badge(f"{player_price} Price", "#b8860b", "#fff")}
    </div>
    {owned_html}
  </div>
</div>
""")

st.divider()


# ── 2. Ownership History ──────────────────────────────────────────────────────

st.subheader("🏠 Ownership History")

with st.spinner("Loading squad history across all seasons…"):
    ownership = get_ownership_history(selected)

# score_df is the source of truth for the current season — use it to fill any
# gap where the squad GSheet lookup didn't find a 2026 owner.
current_year = max(hist_squads_by_year.keys())
if current_owner and current_year not in ownership:
    ownership[current_year] = [current_owner]

all_years     = sorted(hist_squads_by_year.keys())
unique_owners = sorted({o for owners in ownership.values() for o in owners})

if not ownership:
    st.caption("No squad data found for this player in any tracked season.")
else:
    st.caption(
        f"Owned in **{len(ownership)}** of {len(all_years)} seasons"
        f" · **{len(unique_owners)}** unique owner{'s' if len(unique_owners) != 1 else ''}"
    )
    for year in reversed(all_years):
        yr_owners = ownership.get(year, [])
        c_yr, c_chips = st.columns([1, 8])
        with c_yr:
            st.markdown(f"**{year}**")
        with c_chips:
            if yr_owners:
                chips = "".join(
                    f'<span style="background:{OWNER_PALETTE.get(o,"#6b7280")};'
                    f'color:#1a1a1a;padding:3px 14px;border-radius:14px;'
                    f'font-weight:700;font-size:13px;margin-right:6px;">{o}</span>'
                    for o in yr_owners
                )
                st.html(f'<div style="padding:3px 0">{chips}</div>')
            else:
                st.html(
                    '<div style="color:rgba(150,150,150,0.55);'
                    'font-size:13px;padding:4px 0;">— unowned</div>'
                )

st.divider()


# ── 3. Multi-Year Points Chart ────────────────────────────────────────────────

st.subheader("📈 Fantasy Points by Season")

hist_df  = load_hist_points_df()
year_pts = {}

if not hist_df.empty:
    h_name = find_col(hist_df, "Player", "Player Name", "Player name", "Name")
    if h_name:
        # Exact match first; fall back to token-based matching (handles name variants
        # like "MS Dhoni" vs "M S Dhoni" vs "Mahendra Singh Dhoni").
        name_lower  = selected.strip().lower()
        name_tokens = frozenset(name_lower.split())

        p_hist = hist_df[hist_df[h_name].astype(str).str.strip() == selected]
        if p_hist.empty:
            def _name_matches(cell):
                c = str(cell).strip().lower()
                if c == name_lower:
                    return True
                cell_tokens = frozenset(c.split())
                return bool(name_tokens) and name_tokens.issubset(cell_tokens)
            p_hist = hist_df[hist_df[h_name].apply(_name_matches)]

        if not p_hist.empty:
            hist_row = p_hist.iloc[0]
            for col in hist_df.columns:
                try:
                    # Use float() first to handle columns stored as "2025.0"
                    yr = int(float(str(col).strip()))
                    if 2010 <= yr <= 2030:
                        raw = hist_row[col]
                        if pd.notna(raw) and str(raw).strip() not in ("", "-", "N/A", "nan"):
                            year_pts[yr] = float(str(raw).replace(",", ""))
                except (ValueError, TypeError):
                    pass

# Append current 2026 points from agg_df
if _agg_name and _agg_tot:
    cur = agg_df[agg_df[_agg_name].astype(str).str.strip() == selected]
    if not cur.empty:
        v = _safe_float(cur[_agg_tot].iloc[0])
        if v > 0:
            year_pts[2026] = v

if year_pts:
    sorted_yrs = sorted(year_pts.keys())

    bar_colors, hover_texts = [], []
    for yr in sorted_yrs:
        yr_owners = ownership.get(yr, [])
        if yr_owners:
            color = OWNER_PALETTE.get(yr_owners[0], "#6366f1")
            owner_label = " & ".join(yr_owners)
        else:
            color = "#4b5563"
            owner_label = "Unowned"
        bar_colors.append(color)
        hover_texts.append(f"<b>{yr}</b><br>{year_pts[yr]:.0f} pts<br>Owner: {owner_label}")

    fig = go.Figure(go.Bar(
        x=[str(y) for y in sorted_yrs],
        y=[year_pts[y] for y in sorted_yrs],
        marker_color=bar_colors,
        marker_line_width=0,
        text=[f"{year_pts[y]:.0f}" for y in sorted_yrs],
        textposition="outside",
        textfont=dict(size=12, color="rgba(255,255,255,0.75)"),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts,
    ))
    fig.update_layout(
        xaxis_title="Season",
        yaxis_title="Fantasy Points",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="rgba(200,200,200,0.85)"),
        margin=dict(t=24, b=8, l=0, r=8),
        height=300,
        showlegend=False,
        xaxis=dict(type="category", gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.07)"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Owner colour legend
    seen = set()
    legend_parts = []
    for yr in sorted_yrs:
        for o in ownership.get(yr, []):
            if o not in seen:
                seen.add(o)
                c = OWNER_PALETTE.get(o, "#6b7280")
                legend_parts.append(
                    f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:14px;">'
                    f'<span style="width:11px;height:11px;border-radius:3px;background:{c};"></span>'
                    f'<span style="font-size:12px;color:rgba(200,200,200,0.6);">{o}</span></span>'
                )
    if legend_parts:
        st.html(f'<div style="margin-top:-6px;">{"".join(legend_parts)}</div>')
else:
    st.caption("No historical points data found for this player.")

st.divider()


# ── 4. 2026 Season Stats ──────────────────────────────────────────────────────

st.subheader("📊 2026 Season Stats")

p_agg = (
    agg_df[agg_df[_agg_name].astype(str).str.strip() == selected]
    if _agg_name else pd.DataFrame()
)

if p_agg.empty:
    st.caption("No stats yet for this player in the 2026 season.")
else:
    agg_row = p_agg.iloc[0]
    bat_pts  = _col_val(agg_row, agg_df, "batting_points",  "Batting_points",  "batting")
    bowl_pts = _col_val(agg_row, agg_df, "bowling_points",  "Bowling_points",  "bowling")
    fld_pts  = _col_val(agg_row, agg_df, "fielding_points", "Fielding_points", "fielding")
    tot_pts  = _col_val(agg_row, agg_df, "total_points",    "Total_points",    "total")

    c1, c2, c3, c4 = st.columns(4)
    for col_obj, label, val, colour in [
        (c1, "Total Points",  tot_pts,  "#818cf8"),
        (c2, "Batting Pts",   bat_pts,  "#60a5fa"),
        (c3, "Bowling Pts",   bowl_pts, "#4ade80"),
        (c4, "Fielding Pts",  fld_pts,  "#fbbf24"),
    ]:
        with col_obj:
            st.metric(label=label, value=f"{val:.0f}")

    if tot_pts > 0:
        pct_bat  = bat_pts  / tot_pts * 100
        pct_bowl = bowl_pts / tot_pts * 100
        pct_fld  = fld_pts  / tot_pts * 100
        st.html(f"""
        <div style="margin-top:4px;">
          <div style="font-size:13px;font-weight:600;margin-bottom:8px;">Points breakdown</div>
          <div style="display:flex;height:12px;border-radius:6px;overflow:hidden;gap:2px;">
            <div style="width:{pct_bat:.1f}%;background:#3b82f6;"></div>
            <div style="width:{pct_bowl:.1f}%;background:#22c55e;"></div>
            <div style="width:{pct_fld:.1f}%;background:#f59e0b;"></div>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:12px 24px;margin-top:10px;font-size:13px;">
            <div style="display:flex;align-items:center;gap:6px;">
              <div style="width:12px;height:12px;border-radius:3px;background:#3b82f6;flex-shrink:0;"></div>
              <span>Batting</span><span style="font-weight:700;margin-left:4px;">{pct_bat:.0f}%</span>
            </div>
            <div style="display:flex;align-items:center;gap:6px;">
              <div style="width:12px;height:12px;border-radius:3px;background:#22c55e;flex-shrink:0;"></div>
              <span>Bowling</span><span style="font-weight:700;margin-left:4px;">{pct_bowl:.0f}%</span>
            </div>
            <div style="display:flex;align-items:center;gap:6px;">
              <div style="width:12px;height:12px;border-radius:3px;background:#f59e0b;flex-shrink:0;"></div>
              <span>Fielding</span><span style="font-weight:700;margin-left:4px;">{pct_fld:.0f}%</span>
            </div>
          </div>
        </div>
        """)

st.divider()


# ── 5. Match-by-Match Table ───────────────────────────────────────────────────

st.subheader("🎯 Match-by-Match Performance")

with st.spinner("Loading scorecards…"):
    all_sc = _load_all_scorecards()

if all_sc.empty:
    st.caption("No scorecard data available.")
else:
    sc_pid      = find_col(all_sc, "Player_id", "player_id")
    sc_name     = find_col(all_sc, "Name_batting", "Name", "Player")
    sc_name_bowl= find_col(all_sc, "Name_bowling")
    sc_team     = find_col(all_sc, "Team_batting", "Team")
    sc_runs     = find_col(all_sc, "Runs_batting", "Runs")
    sc_balls    = find_col(all_sc, "Balls_batting", "Balls")
    sc_wkts     = find_col(all_sc, "Wickets", "wickets")
    sc_econ     = find_col(all_sc, "Econ", "Economy", "econ")
    sc_fld      = find_col(all_sc, "fielding_points", "Fielding_points")
    sc_tot      = find_col(all_sc, "total_points", "Total_points")

    # Build a name→IPL-team lookup from price_df for opponent resolution
    _price_name_col = find_col(price_df, "Player_name", "Player name", "Name")
    _price_team_col = find_col(price_df, "Team", "IPL Team", "Franchise")
    _name_to_team = {}
    if _price_name_col and _price_team_col:
        _name_to_team = dict(zip(
            price_df[_price_name_col].astype(str).str.strip(),
            price_df[_price_team_col].astype(str).str.strip(),
        ))

    def _opponent_team(mid, player_team_id):
        """Return the IPL team abbreviation for the opponent in match mid."""
        match_sc = all_sc[all_sc["match_id"] == mid]
        if sc_team:
            opp_rows = match_sc[
                match_sc[sc_team].astype(str).str.strip() != str(player_team_id)
            ]
        else:
            opp_rows = pd.DataFrame()
        if not opp_rows.empty and sc_name:
            for opp_name in opp_rows[sc_name].astype(str):
                team = _name_to_team.get(opp_name.strip())
                if team and team not in ("", "nan", "—"):
                    return team
        return "?"

    # Filter to this player (by player_id first, name fallback)
    player_sc = pd.DataFrame()
    if sc_pid and player_id:
        try:
            player_sc = all_sc[
                all_sc[sc_pid].astype(str).str.replace(r"\.0$", "", regex=True) == str(int(player_id))
            ]
        except Exception:
            pass
    if player_sc.empty and sc_name:
        player_sc = all_sc[all_sc[sc_name].astype(str).str.strip() == selected]

    if player_sc.empty:
        st.caption("No match data found for this player this season.")
    else:
        player_sc = player_sc.sort_values("match_id").reset_index(drop=True)

        # Build display rows
        rows = []
        for idx, (_, r) in enumerate(player_sc.iterrows(), 1):
            mid = r["match_id"]
            p_team_id = str(r[sc_team]).strip() if sc_team else ""
            opponent  = _opponent_team(mid, p_team_id)

            runs  = int(_safe_float(r[sc_runs],  0)) if sc_runs  else 0
            balls = int(_safe_float(r[sc_balls], 0)) if sc_balls else 0
            wkts  = int(_safe_float(r[sc_wkts],  0)) if sc_wkts  else 0
            econ  = round(_safe_float(r[sc_econ], 0.0), 2) if sc_econ else 0.0
            fld   = round(_safe_float(r[sc_fld]),  1) if sc_fld else 0.0
            tot   = round(_safe_float(r[sc_tot]),  1) if sc_tot else 0.0

            # Show "—" when the player genuinely didn't bat or bowl
            did_bat  = balls > 0
            did_bowl = (
                sc_name_bowl and
                str(r[sc_name_bowl]).strip() not in ("0", "", "nan") and
                econ > 0
            )
            bat_str  = f"{runs} ({balls}b)" if did_bat  else "—"
            bowl_str = f"{wkts}W ({econ})"  if did_bowl else "—"

            rows.append({
                "#":         idx,
                "Match":     f"vs {opponent}",
                "Batting":   bat_str,
                "Bowling":   bowl_str,
                "Total Pts": tot,
            })

        matches_df = pd.DataFrame(rows)
        n = len(matches_df)

        # Best-game callout
        best_idx = int(matches_df["Total Pts"].idxmax())
        best     = matches_df.loc[best_idx]
        st.html(f"""
        <div style="background:linear-gradient(90deg,#3730a3,#4338ca);
                    border-radius:8px;padding:14px 20px;margin-bottom:16px;
                    display:flex;align-items:center;flex-wrap:wrap;gap:10px 14px;">
          <span style="font-size:24px;flex-shrink:0;">⭐</span>
          <div style="min-width:0;">
            <div style="font-size:11px;color:rgba(255,255,255,0.65);
                        text-transform:uppercase;letter-spacing:.8px;
                        font-weight:700;">Best Game</div>
            <div style="font-size:16px;font-weight:800;color:#fff;margin-top:3px;
                        word-break:break-word;">
              {best['Total Pts']:.0f} pts — Match #{best['#']} ({best['Match']})
            </div>
            <div style="font-size:13px;color:rgba(255,255,255,0.75);margin-top:3px;">
              {best['Batting']} bat &nbsp;·&nbsp; {best['Bowling']} bowl
            </div>
          </div>
        </div>
        """)

        # Row highlighting: top-3 green, bottom-3 red (only if enough matches)
        sorted_desc = matches_df["Total Pts"].sort_values(ascending=False)
        top3_thresh = sorted_desc.iloc[min(2, n - 1)]
        bot3_thresh = sorted_desc.iloc[max(n - 3, 0)] if n > 3 else None

        def _highlight(row):
            v = row["Total Pts"]
            if v >= top3_thresh and v > 0:
                return ["background-color:rgba(34,197,94,0.35)"] * len(row)
            if bot3_thresh is not None and v <= bot3_thresh:
                return ["background-color:rgba(239,68,68,0.25)"] * len(row)
            return [""] * len(row)

        styled = (
            matches_df.style
            .apply(_highlight, axis=1)
            .format({"Total Pts": "{:.1f}"})
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()


# ── 6. Role Rank ──────────────────────────────────────────────────────────────

st.subheader("📐 Role Ranking — 2026")

if not p_agg.empty and _cat_col and _agg_name and _agg_tot:
    try:
        merged = agg_df.merge(
            price_df[[_name_col, _cat_col]].rename(columns={_name_col: _agg_name}),
            on=_agg_name,
            how="left",
        )
        merged["_role"] = merged[_cat_col].apply(lambda x: short_role(str(x)))
        merged[_agg_tot] = pd.to_numeric(merged[_agg_tot], errors="coerce").fillna(0)

        this_role   = short_role(player_role)
        peers       = merged[merged["_role"] == this_role].sort_values(_agg_tot, ascending=False).reset_index(drop=True)
        player_tot  = _safe_float(p_agg[_agg_tot].iloc[0])
        rank        = int((peers[_agg_tot] > player_tot).sum()) + 1
        total_peers = len(peers)
        percentile  = 100.0 * (total_peers - rank) / max(total_peers - 1, 1)
        rank_colour = "#22c55e" if percentile >= 66 else ("#f59e0b" if percentile >= 33 else "#ef4444")

        c_badge, c_chart = st.columns([2, 5])

        with c_badge:
            st.html(f"""
            <div style="border:2px solid {rank_colour};
                        border-radius:12px;padding:22px 24px;text-align:center;">
              <div style="font-size:44px;font-weight:800;color:{rank_colour};">#{rank}</div>
              <div style="font-size:14px;font-weight:600;margin-top:6px;">
                of {total_peers} {this_role}s
              </div>
              <div style="margin-top:12px;background:#e5e7eb;
                          border-radius:4px;height:8px;overflow:hidden;">
                <div style="width:{max(3,round(percentile))}%;
                             height:100%;background:{rank_colour};"></div>
              </div>
              <div style="font-size:13px;font-weight:700;color:{rank_colour};margin-top:6px;">
                Top {100 - int(percentile):.0f}%
              </div>
            </div>
            """)

        with c_chart:
            # Show top-5 + player if not already in top-5
            top5 = peers.head(5)
            if selected not in top5[_agg_name].values:
                extra = peers[peers[_agg_name] == selected]
                bar_df = pd.concat([top5, extra]).drop_duplicates(subset=_agg_name)
            else:
                bar_df = top5
            bar_df = bar_df.sort_values(_agg_tot, ascending=True)

            bar_colours = [
                rank_colour if name == selected else "#4b5563"
                for name in bar_df[_agg_name]
            ]

            rank_fig = go.Figure(go.Bar(
                x=bar_df[_agg_tot].tolist(),
                y=bar_df[_agg_name].tolist(),
                orientation="h",
                marker_color=bar_colours,
                marker_line_width=0,
                text=bar_df[_agg_tot].apply(lambda v: f"{v:.0f}").tolist(),
                textposition="outside",
                textfont=dict(size=11, color="rgba(200,200,200,0.7)"),
            ))
            rank_fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="rgba(200,200,200,0.75)", size=12),
                margin=dict(t=8, b=8, l=0, r=40),
                height=230,
                showlegend=False,
                xaxis=dict(
                    gridcolor="rgba(255,255,255,0.05)",
                    title="Points",
                ),
                yaxis=dict(gridcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(rank_fig, use_container_width=True)

    except Exception as e:
        st.caption(f"Could not compute role ranking: {e}")
else:
    st.caption("Role ranking not available — no stats for this player yet.")
