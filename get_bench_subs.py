import pandas as pd
import gspread

from settings import (
    service_account_credentials,
    price_list_spreadsheet_url,
    unsold_spreadsheet_url,
    weeks,
    owner_team_dict,
    player_id_dict,
)
from helpers import can_bat, can_bowl, is_wk, is_overseas, find_col


def _read_gsheet(spreadsheet_url, sheet_name):
    """Read a Google Sheet tab directly into a DataFrame."""
    gc = gspread.service_account(filename=service_account_credentials)
    ws = gc.open_by_url(spreadsheet_url).worksheet(sheet_name)
    data = ws.get_all_values()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data[1:], columns=data[0])


def _build_maps():
    """Read price_list and unsold directly from GSheets and merge to build
    role_map and nationality_map.  price_list takes priority; unsold
    fills any gaps."""
    price_df  = _read_gsheet(price_list_spreadsheet_url, 'price_list')
    unsold_df = _read_gsheet(unsold_spreadsheet_url, 'Unsold_players')

    role_map        = {}
    nationality_map = {}

    # price_list first — header may be 'Player Name' or 'Player_name'
    _p_name = find_col(price_df, 'Player name', 'Player_name', 'Name')
    _p_role = find_col(price_df, 'Category', 'Role', 'Cat')
    _p_nat  = find_col(price_df, 'Nationality')
    if _p_name and _p_role:
        role_map.update(dict(zip(
            price_df[_p_name].str.strip(),
            price_df[_p_role].str.strip(),
        )))
    if _p_name and _p_nat:
        nationality_map.update(dict(zip(
            price_df[_p_name].str.strip(),
            price_df[_p_nat].str.strip(),
        )))

    # unsold fills gaps
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


def _role_counts(xi, role_map):
    cats = [role_map.get(p, '') for p in xi]
    return (
        sum(1 for c in cats if can_bat(c)),
        sum(1 for c in cats if can_bowl(c)),
        sum(1 for c in cats if is_wk(c)),
    )


def _overseas_count(xi, nationality_map):
    return sum(1 for p in xi if is_overseas(nationality_map.get(p, '')))


def _is_valid_swap(current_xi, candidate_xi, role_map, nationality_map):
    """A swap is valid if:
    - No role count drops below min(current_count, threshold).
      (Handles squads already below threshold due to missing data — a
       like-for-like swap is never blocked.)
    - Overseas count in the candidate XI does not exceed 4.
    """
    curr = _role_counts(current_xi, role_map)
    new  = _role_counts(candidate_xi, role_map)
    for cur_cnt, new_cnt, threshold in zip(curr, new, (7, 5, 1)):
        if new_cnt < min(cur_cnt, threshold):
            return False
    if _overseas_count(candidate_xi, nationality_map) > 4:
        return False
    return True


def suggest_bench_subs(week, scorecards, weekly_player_points_df):
    """Print bench substitution suggestions for every owner for *week*.

    Parameters
    ----------
    week : str
        e.g. 'Week2'
    scorecards : dict
        Keyed by '{match_id}_scorecard', as returned by retrieve_scorecards().
    weekly_player_points_df : pd.DataFrame
        As returned by create_score_df(); columns Player, Week1_points, ...
    """
    week_col = f'{week}_points'
    if week_col not in weekly_player_points_df.columns:
        print(f"No data available for {week} yet.")
        return

    role_map, nationality_map = _build_maps()

    # Players who appeared in any scorecard for this week
    players_who_played = set()
    for match_id in weeks.get(week, {}).get('matches', []):
        key = f"{match_id}_scorecard"
        if key in scorecards:
            players_who_played.update(
                scorecards[key]['Player_id'].dropna().astype(int).tolist()
            )

    def player_played(name):
        pid = player_id_dict.get(name.strip())
        return pid is not None and int(pid) in players_who_played

    player_pts = (
        weekly_player_points_df
        .set_index('Player')[week_col]
        .fillna(0)
        .to_dict()
    )

    squad_df = pd.read_csv(f"Squads/{week}.csv")

    print(f"=== Bench Substitution Suggestions for {week} ===\n")
    any_suggestion = False

    for owner in sorted(owner_team_dict.keys()):
        if owner not in squad_df.columns:
            continue

        col = squad_df[owner]
        xi    = [str(p).strip() for p in col.iloc[:11]   if str(p).strip() not in ('', 'nan')]
        bench = [str(p).strip() for p in col.iloc[15:19] if str(p).strip() not in ('', 'nan')]

        no_play = [p for p in xi if not player_played(p)]
        bench_played = sorted(
            [(p, player_pts.get(p, 0)) for p in bench if player_played(p)],
            key=lambda x: x[1], reverse=True,
        )

        if not no_play or not bench_played:
            continue

        current_xi   = list(xi)
        subs_made    = []
        used_bench   = set()
        used_no_play = set()

        for bench_player, pts in bench_played:
            if bench_player in used_bench:
                continue
            for player_out in no_play:
                if player_out in used_no_play:
                    continue
                candidate_xi = [bench_player if p == player_out else p for p in current_xi]
                if _is_valid_swap(current_xi, candidate_xi, role_map, nationality_map):
                    subs_made.append((player_out, bench_player, pts))
                    current_xi = candidate_xi
                    used_bench.add(bench_player)
                    used_no_play.add(player_out)
                    break

        if subs_made:
            any_suggestion = True
            print(f"{owner} — {owner_team_dict[owner]}:")
            for out_p, in_p, pts in subs_made:
                print(f"  OUT: {out_p:<28s}  IN: {in_p:<28s}  ({pts:+.0f} pts)")
            bat_n, bowl_n, wk_n = _role_counts(current_xi, role_map)
            overseas_n = _overseas_count(current_xi, nationality_map)
            print(f"  XI check — can bat: {bat_n}  can bowl: {bowl_n}  WK: {wk_n}  overseas: {overseas_n}/4")
            print(f"  Suggested XI: {', '.join(current_xi)}")
            print()

    if not any_suggestion:
        print("No bench substitutions suggested for this week.")
