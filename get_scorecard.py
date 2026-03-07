#!/usr/bin/env python3

import os
import re
import argparse
from typing import Optional
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from helpers import upload_df_to_gcs


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _clean_name(raw: str) -> str:
    """Strip captain marker and non-word runs; return normalised name."""
    return re.sub(r"\W+", " ", raw.split("(c)")[0]).strip()


def _parse_batting_table(table, team_idx: int) -> list:
    """Return rows as plain lists [Name, Desc, Runs, Balls, 4s, 6s, SR, Team, Player_id]."""
    rows = []
    for row in table.find_all("tr"):
        cols_td = row.find_all("td")
        if not cols_td:
            continue
        cols = [c.text.strip() for c in cols_td]

        if cols[0].lower() in ("extras", "total"):
            continue

        player_id_anchors = row.find_all("a", href=True)
        player_id = (
            player_id_anchors[0]["href"].split("-")[-1]
            if player_id_anchors
            else None
        )

        if len(cols) > 1 and cols[1] == "absent hurt":
            rows.append([_clean_name(cols[0]), cols[1], 0, 0, 0, 0, 0, team_idx, player_id])
            continue

        if "Did not bat" in cols[0]:
            for anchor in cols_td[0].find_all("a", href=True):
                pid = anchor["href"].split("-")[-1]
                name = re.sub(
                    r"\W+", " ", anchor.get_text(strip=True).rstrip(",").split("(c)")[0]
                ).strip()
                if name:
                    rows.append([name, "DNB", 0, 0, 0, 0, 0, team_idx, pid])
            continue

        if len(cols) > 2:
            # cols[4] is "minutes" — skip it; 4s=cols[5], 6s=cols[6], SR=cols[7]
            rows.append([
                _clean_name(cols[0]),
                cols[1],
                cols[2],
                cols[3],
                cols[5],
                cols[6],
                cols[7],
                team_idx,
                player_id,
            ])

    return rows


def _parse_bowling_table(table, team_idx: int) -> list:
    """Return rows as plain lists [Name, Overs, Maidens, Runs, Wickets, Econ, Dots, Wd, Nb, Team, Player_id]."""
    rows = []
    for row in table.find_all("tr"):
        player_id_col = row.find_all("a", href=True)
        if not player_id_col or "cricketers" not in player_id_col[0]["href"]:
            continue
        player_id = player_id_col[0]["href"].split("-")[-1]
        cols = [c.text.strip() for c in row.find_all("td")]
        if len(cols) > 8:
            rows.append([
                re.sub(r"\W+", " ", cols[0]).strip(),
                cols[1], cols[2], cols[3], cols[4],
                cols[5], cols[6], cols[7], cols[8],
                team_idx, player_id,
            ])
    return rows


def _calc_batting_points(batsmen_df: pd.DataFrame) -> pd.DataFrame:
    df = batsmen_df.copy()
    df["Runs"] = df["Runs"].astype(int)
    df["Balls"] = df["Balls"].astype(int)
    df["4s"] = df["4s"].astype(int)
    df["6s"] = df["6s"].astype(int)
    df["base_points"] = df["Runs"]
    df["pace_points"] = df["Runs"] - df["Balls"]
    df["milestone_points"] = (np.floor(df["Runs"] / 25)).replace(
        {0.0: 0, 1.0: 10, 2.0: 20, 3.0: 30, 4.0: 50, 5.0: 50, 6.0: 50, 7.0: 50, 8.0: 50}
    ).clip(upper=50)
    df["impact_points"] = (
        df["4s"]
        + 2 * df["6s"]
        + (df["Runs"] == 0)
        * (df["Desc"] != "not out")
        * (df["Desc"] != "DNB")
        * (df["Desc"] != "absent hurt")
        * (-5)
    )
    df["batting_points"] = (
        df["base_points"] + df["pace_points"] + df["milestone_points"] + df["impact_points"]
    )
    return df


def _calc_bowling_points(bowler_df: pd.DataFrame) -> pd.DataFrame:
    df = bowler_df.copy()
    df["Wickets"] = df["Wickets"].astype(int)
    df["Runs"] = df["Runs"].astype(int)
    df["Dots"] = df["Dots"].astype(int)
    df["Maidens"] = df["Maidens"].astype(int)
    df["Balls"] = (
        df["Overs"]
        .apply(lambda x: x.split("."))
        .apply(lambda x: int(x[0]) * 6 + int(x[1]) if len(x) > 1 else int(x[0]) * 6)
    )
    df["base_points"] = 25 * df["Wickets"]
    df["pace_points"] = 1.5 * df["Balls"] - df["Runs"]
    df["pace_points"] = df["pace_points"].apply(
        lambda x: np.round(x * 2.5) if x > 0 else np.round(x)
    )
    df["milestone_points"] = df["Wickets"].replace(
        {0: 0, 1: 0, 2: 10, 3: 20, 4: 30, 5: 50, 6: 50, 7: 50, 8: 50}
    ).clip(upper=50)
    df["impact_points"] = np.round(1.5 * df["Dots"] + df["Maidens"] * 30)
    df["bowling_points"] = (
        df["base_points"] + df["pace_points"] + df["milestone_points"] + df["impact_points"]
    )
    return df


def _resolve_fielder(fielder_df: pd.DataFrame, fielder: str, fielding_team: int):
    """Return the DataFrame index for fielder on fielding_team, or None if not found.

    Falls back through four matching strategies:
    1. Entire name appears in team's names
    2. Second name matches exactly one player (any team)
    3. Second name + first letter of first name
    4. First name matches exactly one player
    """
    parts = fielder.split()
    if not parts:
        return None

    team_mask = fielder_df["Team"] == fielding_team

    # 1. Entire name appears in the team's names
    s = fielder_df.loc[team_mask, "Name"].str.contains(fielder, regex=False)
    if s.any():
        return s[s].index[0]

    if len(parts) < 2:
        return None

    last = parts[1]

    # 2. Second name matches exactly one player (any team)
    s = fielder_df["Name"].str.contains(last, regex=False)
    if s.sum() == 1:
        return s[s].index[0]

    # 3. Second name + first letter of first name
    s = fielder_df["Name"].str.contains(last, regex=False) & (
        fielder_df["Name"].str[0] == parts[0][0]
    )
    if s.sum() == 1:
        return s[s].index[0]

    # 4. First name matches exactly one player
    s = fielder_df["Name"].str.contains(parts[0], regex=False)
    if s.sum() == 1:
        return s[s].index[0]

    return None


def _get_mom_id(bs) -> Optional[str]:
    """Return the player-id string for the Man of the Match, or None.

    Searches by text content rather than a specific CSS class so it stays
    robust when ESPN updates their layout.
    """
    for text_node in bs.find_all(string=lambda t: t and "Player Of The Match" in t):
        container = text_node.parent
        for _ in range(6):  # walk up at most 6 ancestor levels
            if container is None or container.name == "body":
                break
            anchor = container.find("a", href=lambda h: h and "/cricketers/" in h)
            if anchor:
                return anchor["href"].split("-")[-1]
            container = container.parent
    return None


def _get_winner_index(bs) -> Optional[int]:
    """Return 1 or 2 for the winning team's innings index, or None."""
    innings_teams = []
    for span in bs.find_all("span"):
        txt = span.get_text(strip=True)
        if txt.endswith(" Innings"):
            abbr = txt.replace(" Innings", "").strip()
            if abbr not in innings_teams:
                innings_teams.append(abbr)
    result_tag = bs.find("p", string=lambda t: t and "won by" in t)
    if result_tag and len(innings_teams) >= 2:
        winner_abbr = result_tag.get_text(strip=True).split(" won by")[0].strip()
        return {innings_teams[0]: 1, innings_teams[1]: 2}.get(winner_abbr)
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_scorecard(series_id, match_id):
    URL = f"https://www.espncricinfo.com/series/{series_id}/scorecard/{match_id}"
    url = f"http://api.scraperapi.com/?api_key={os.environ['SCRAPER_API_KEY']}&url={URL}"
    page = requests.get(url)
    page.raise_for_status()
    bs = BeautifulSoup(page.content, "html.parser")

    table_body = bs.find_all("tbody")

    # Bowling tables are at indices 1 and 3 (between the batting tables)
    # i=0 → team 2 bowls (bats second), i=1 → team 1 bowls (bats first)
    bowling_rows = []
    for i, table in enumerate(table_body[1:4:2]):
        team_idx = 2 if i == 0 else 1
        bowling_rows.extend(_parse_bowling_table(table, team_idx))

    bowler_df = pd.DataFrame(
        bowling_rows,
        columns=["Name", "Overs", "Maidens", "Runs", "Wickets", "Econ", "Dots", "Wd", "Nb", "Team", "Player_id"],
    )

    # Batting tables are at indices 0 and 2
    batting_rows = []
    for i, table in enumerate(table_body[0:4:2]):
        batting_rows.extend(_parse_batting_table(table, i + 1))

    batsmen_df = pd.DataFrame(
        batting_rows,
        columns=["Name", "Desc", "Runs", "Balls", "4s", "6s", "SR", "Team", "Player_id"],
    )

    # --- Point calculation ---
    bowler_df = _calc_bowling_points(bowler_df)
    batsmen_df = _calc_batting_points(batsmen_df)

    teams_df = (
        pd.concat([
            batsmen_df[["Name", "Team", "Player_id"]],
            bowler_df[["Name", "Team", "Player_id"]],
        ])
        .drop_duplicates()
        .reset_index(drop=True)
    )

    # --- Fielding ---
    fielder_df = teams_df.copy()
    fielder_df["fielding_points"] = 0
    for team in [1, 2]:
        fielders = []
        for wicket in batsmen_df[batsmen_df["Team"] == team]["Desc"]:
            if wicket.startswith("c & b"):
                fielders.append(wicket.split("c & b")[1].strip())
            elif wicket.startswith("c "):
                fielders.append(wicket.split("c ")[1].split(" b ")[0].strip())
            if wicket.startswith("st "):
                fielders.append(wicket.split("st ")[1].split(" b ")[0].strip())
            if wicket.startswith("run out"):
                fielders.extend(
                    x.strip()
                    for x in wicket.split("run out")[1]
                    .replace("(", "")
                    .replace(")", "")
                    .split("/")
                )

        fielders = [f for f in fielders if "sub (" not in f and "sub [" not in f]
        fielders = [re.sub(r"\W+", " ", f).strip() for f in fielders]
        fielding_team = 2 if team == 1 else 1
        for fielder in fielders:
            idx = _resolve_fielder(fielder_df, fielder, fielding_team)
            if idx is not None:
                fielder_df.loc[idx, "fielding_points"] += 10
            else:
                print(f"Fielder not found: {fielder}")

    # --- MoM bonus ---
    fielder_df["bonus_points"] = 0
    mom_id = _get_mom_id(bs)
    if mom_id:
        fielder_df.loc[fielder_df["Player_id"] == mom_id, "bonus_points"] += 25

    # --- Winning-team bonus ---
    winner_index = _get_winner_index(bs)
    if winner_index:
        fielder_df.loc[fielder_df["Team"] == winner_index, "bonus_points"] += 5

    # --- Merge ---
    total_df = (
        teams_df.merge(batsmen_df, how="left", on=["Name", "Player_id", "Team"])
        .merge(bowler_df, how="left", on=["Player_id"], suffixes=("_batting", "_bowling"))
        .merge(fielder_df, how="left", on=["Player_id"])
        .fillna(0)
    )

    total_df["total_points"] = (
        total_df["batting_points"]
        + total_df["bowling_points"]
        + total_df["fielding_points"]
        + total_df["bonus_points"]
    )

    total_df = total_df.reset_index()
    total_df.to_csv(f"./Scorecards/{match_id}_scorecard.csv", header=True, index=False)

    return total_df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--match_id", type=int, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()
    df = get_scorecard(8048, args.match_id)
    upload_df_to_gcs(df, f"Scorecards/{args.match_id}_scorecard.csv")
