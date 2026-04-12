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
from helpers import role_counts, overseas_count, is_valid_swap, build_role_nat_maps, find_col


def _read_gsheet(spreadsheet_url, sheet_name):
    """Read a Google Sheet tab directly into a DataFrame (CLI / non-Streamlit use)."""
    gc = gspread.service_account(filename=service_account_credentials)
    ws = gc.open_by_url(spreadsheet_url).worksheet(sheet_name)
    data = ws.get_all_values()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data[1:], columns=data[0])


def _build_maps():
    """Read price_list and unsold directly from GSheets and return role/nationality maps."""
    price_df  = _read_gsheet(price_list_spreadsheet_url, 'price_list')
    unsold_df = _read_gsheet(unsold_spreadsheet_url, 'Unsold_players')
    return build_role_nat_maps(price_df, unsold_df)


def compute_subs_core(squad_df, players_who_played, role_map, nationality_map, player_pts):
    """Pure bench-sub algorithm. Returns a list of per-owner result dicts.

    Parameters
    ----------
    squad_df : pd.DataFrame
        One column per owner; rows 0–10 = XI, rows 15–18 = bench.
    players_who_played : set of int
        Player IDs that appeared in any completed scorecard.
    role_map : dict  {player_name: role_str}
    nationality_map : dict  {player_name: nationality_str}
    player_pts : dict  {player_name: float}
        Raw (no multiplier) weekly points so far.

    Each result dict has keys:
        owner, team, subs [(out, in, raw_pts)], final_xi, bat, bowl, wk, overseas
    """
    def player_played(name):
        pid = player_id_dict.get(name.strip())
        return pid is not None and int(pid) in players_who_played

    results = []
    for owner in sorted(owner_team_dict.keys()):
        if owner not in squad_df.columns:
            continue

        col = squad_df[owner]
        xi    = [str(p).strip() for p in col.iloc[:11]   if str(p).strip() not in ('', 'nan')]
        bench = [str(p).strip() for p in col.iloc[15:19] if str(p).strip() not in ('', 'nan')]

        no_play = [p for p in xi if not player_played(p)]
        bench_played = sorted(
            [(p, float(player_pts.get(p, 0))) for p in bench if player_played(p)],
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
                if is_valid_swap(current_xi, candidate_xi, role_map, nationality_map):
                    subs_made.append((player_out, bench_player, pts))
                    current_xi = candidate_xi
                    used_bench.add(bench_player)
                    used_no_play.add(player_out)
                    break

        if subs_made:
            bat_n, bowl_n, wk_n = role_counts(current_xi, role_map)
            overseas_n = overseas_count(current_xi, nationality_map)
            results.append({
                'owner':    owner,
                'team':     owner_team_dict.get(owner, owner),
                'subs':     subs_made,
                'final_xi': current_xi,
                'bat':      bat_n,
                'bowl':     bowl_n,
                'wk':       wk_n,
                'overseas': overseas_n,
            })

    return results


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

    players_who_played = set()
    for match_id in weeks.get(week, {}).get('matches', []):
        key = f"{match_id}_scorecard"
        if key in scorecards:
            players_who_played.update(
                scorecards[key]['Player_id'].dropna().astype(int).tolist()
            )

    player_pts = (
        weekly_player_points_df
        .set_index('Player')[week_col]
        .fillna(0)
        .to_dict()
    )

    role_map, nationality_map = _build_maps()
    squad_df = pd.read_csv(f"Squads/{week}.csv")
    results = compute_subs_core(squad_df, players_who_played, role_map, nationality_map, player_pts)

    print(f"=== Bench Substitution Suggestions for {week} ===\n")
    if not results:
        print("No bench substitutions suggested for this week.")
        return

    for entry in results:
        print(f"{entry['owner']} — {entry['team']}:")
        for out_p, in_p, pts in entry['subs']:
            print(f"  OUT: {out_p:<28s}  IN: {in_p:<28s}  ({pts:+.0f} pts)")
        print(
            f"  XI check — can bat: {entry['bat']}  can bowl: {entry['bowl']}"
            f"  WK: {entry['wk']}  overseas: {entry['overseas']}/4"
        )
        print(f"  Suggested XI: {', '.join(entry['final_xi'])}")
        print()
