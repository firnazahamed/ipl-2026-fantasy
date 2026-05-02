#!/usr/bin/env python3
"""
Run after a match finishes:
  1. Finds the next unprocessed match ID from settings.weeks
  2. Fetches the scorecard and uploads it to GCS
  3. Rebuilds standings and uploads all outputs to GCS

Usage:
  python update_match.py                  # auto-detect next match
  python update_match.py --match 1529270  # force a specific match ID
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).parent.resolve()
os.chdir(SCRIPT_DIR)

os.environ.setdefault("SCRAPER_API_KEY", "67dd6af4b4c692a37a2a419b944aaef0")

SERIES_ID = 8048


def get_all_match_ids() -> list[str]:
    """Return every match ID defined in settings.weeks, in order."""
    from settings import weeks
    ids = []
    for week_cfg in weeks.values():
        ids.extend(week_cfg.get("matches", []))
    return ids


def get_processed_ids() -> set[str]:
    """Return match IDs that already have a local scorecard CSV."""
    path = SCRIPT_DIR / "Scorecards"
    if not path.exists():
        return set()
    return {f.name.replace("_scorecard.csv", "") for f in path.glob("*_scorecard.csv")}


def find_next_match_id() -> Optional[str]:
    """Return the first match ID in schedule order that hasn't been processed yet."""
    processed = get_processed_ids()
    for mid in get_all_match_ids():
        if mid not in processed:
            return mid
    return None


def fetch_scorecard(match_id: str) -> bool:
    from get_scorecard import get_scorecard
    from helpers import upload_df_to_gcs
    from settings import bucket_name

    print(f"Fetching scorecard for match {match_id} …")
    try:
        df = get_scorecard(SERIES_ID, int(match_id))
        upload_df_to_gcs(df, f"Scorecards/{match_id}_scorecard.csv", bucket_name)
        print(f"  Scorecard saved locally and uploaded to GCS.")
        return True
    except Exception as e:
        print(f"  ERROR fetching scorecard: {e}", file=sys.stderr)
        return False


def update_standings() -> bool:
    from get_standings import retrieve_scorecards, retrieve_team_info, create_score_df, save_outputs
    from settings import weeks, owner_team_dict, player_id_dict

    print("Rebuilding standings …")
    try:
        scorecards = retrieve_scorecards()
        weekly_dicts, squad_dict = retrieve_team_info()
        outputs = create_score_df(
            scorecards, weekly_dicts, squad_dict, weeks, owner_team_dict, player_id_dict
        )
        save_outputs(*outputs)
        print("  Standings updated and uploaded to GCS.")
        return True
    except Exception as e:
        print(f"  ERROR updating standings: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Fetch scorecard and update standings.")
    parser.add_argument("--match", type=str, default=None, help="Force a specific match ID")
    args = parser.parse_args()

    match_id = args.match or find_next_match_id()

    if match_id is None:
        print("All matches in the schedule have already been processed.")
        sys.exit(0)

    processed = get_processed_ids()
    if match_id in processed and not args.match:
        print(f"Match {match_id} is already processed. Nothing to do.")
        sys.exit(0)

    print(f"Next match to process: {match_id}")

    if not fetch_scorecard(match_id):
        sys.exit(1)

    if not update_standings():
        sys.exit(1)

    print(f"\nDone. Match {match_id} processed successfully.")


if __name__ == "__main__":
    main()
