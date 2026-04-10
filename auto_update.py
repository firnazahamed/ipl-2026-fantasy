#!/usr/bin/env python3
"""Cloud Run entry point: sync data, detect completed matches, update standings."""

import os
import sys
import re
import time
import logging
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).parent.resolve()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],  # Cloud Run captures stdout
)
log = logging.getLogger(__name__)

SERIES_ID = 8048
MATCH_ID_MIN = 1527674
MATCH_ID_MAX = 1527743    # update if playoffs extend further
MAX_NEW_PER_DAY = 2
HTTP_TIMEOUT = 30


# ── Step 1: Sync existing scorecards from GCS ─────────────────────────────────

def sync_scorecards_from_gcs():
    from google.cloud import storage
    from settings import bucket_name
    os.makedirs("Scorecards", exist_ok=True)
    client = storage.Client.from_service_account_json(
        "credentials/cricinfo-273202-a7420ddc1abd.json"
    )
    bucket = client.bucket(bucket_name)
    count = 0
    for blob in bucket.list_blobs(prefix="Scorecards/"):
        fname = os.path.basename(blob.name)
        if fname.endswith("_scorecard.csv"):
            blob.download_to_filename(f"Scorecards/{fname}")
            count += 1
    log.info(f"Synced {count} scorecard(s) from GCS.")


# ── Step 2: Sync squads from Google Sheets ────────────────────────────────────

def sync_squads_from_gsheets():
    from helpers import download_gsheet_as_csv
    from settings import squads_spreadsheet_url, weeks
    os.makedirs("Squads", exist_ok=True)
    for week in weeks.keys():
        download_gsheet_as_csv(squads_spreadsheet_url, sheet_name=week, download_folder="Squads")
    log.info("Squads synced from Google Sheets.")


# ── Match ID helpers ───────────────────────────────────────────────────────────

def get_max_processed_id() -> int:
    ids = []
    for f in Path("Scorecards").glob("*_scorecard.csv"):
        m = re.match(r"^(\d+)_scorecard\.csv$", f.name)
        if m:
            ids.append(int(m.group(1)))
    return max(ids) if ids else MATCH_ID_MIN - 1


# ── Match completion check ─────────────────────────────────────────────────────

def is_match_complete(match_id: int):
    """Returns True if complete, False if in-progress, None if not found/error."""
    ESPN_URL = f"https://www.espncricinfo.com/series/{SERIES_ID}/scorecard/{match_id}"
    scraper_url = (
        f"http://api.scraperapi.com/?api_key={os.environ['SCRAPER_API_KEY']}&url={ESPN_URL}"
    )

    resp = None
    for attempt in range(1, 3):
        try:
            resp = requests.get(scraper_url, timeout=HTTP_TIMEOUT)
            break
        except requests.RequestException as e:
            log.warning(f"Match {match_id}: network error (attempt {attempt}): {e}")
            if attempt < 2:
                time.sleep(30)

    if resp is None:
        return None

    if resp.status_code == 404:
        log.info(f"Match {match_id}: 404 — does not exist yet.")
        return None
    if resp.status_code != 200:
        log.warning(f"Match {match_id}: HTTP {resp.status_code}.")
        return None

    bs = BeautifulSoup(resp.content, "html.parser")
    result_tag = bs.find(
        lambda tag: tag.name in ("p", "span", "div")
        and tag.string
        and any(kw in tag.string.lower() for kw in ("won by", "match tied", "no result"))
    )
    tbodies = bs.find_all("tbody")

    if result_tag is None:
        log.info(f"Match {match_id}: no result string — in progress.")
        return False
    if len(tbodies) < 2:
        log.info(f"Match {match_id}: only {len(tbodies)} innings table(s) — incomplete.")
        return False

    log.info(f"Match {match_id}: complete ({len(tbodies)} innings tables).")
    return True


# ── Scorecard fetch ────────────────────────────────────────────────────────────

def run_get_scorecard(match_id: int) -> bool:
    try:
        from get_scorecard import get_scorecard
        from helpers import upload_df_to_gcs
        from settings import bucket_name
        log.info(f"Fetching scorecard for match {match_id} …")
        df = get_scorecard(SERIES_ID, match_id)
        upload_df_to_gcs(df, f"Scorecards/{match_id}_scorecard.csv", bucket_name)
        log.info(f"Match {match_id}: scorecard saved and uploaded to GCS.")
        return True
    except Exception as e:
        log.error(f"Match {match_id}: get_scorecard failed — {e}", exc_info=True)
        return False


# ── Standings update ───────────────────────────────────────────────────────────

def run_get_standings() -> bool:
    try:
        from get_standings import retrieve_scorecards, retrieve_team_info, create_score_df, save_outputs
        from settings import weeks, owner_team_dict, player_id_dict
        log.info("Updating standings …")
        scorecards = retrieve_scorecards()
        weekly_dicts, squad_dict = retrieve_team_info()
        outputs = create_score_df(
            scorecards, weekly_dicts, squad_dict, weeks, owner_team_dict, player_id_dict
        )
        save_outputs(*outputs)
        log.info("Standings updated and uploaded to GCS.")
        return True
    except Exception as e:
        log.error(f"get_standings failed — {e}", exc_info=True)
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info(f"auto_update.py started at {datetime.now().isoformat()}")
    os.chdir(SCRIPT_DIR)

    if not os.environ.get("SCRAPER_API_KEY"):
        log.error("SCRAPER_API_KEY not set. Aborting.")
        sys.exit(1)

    sync_scorecards_from_gcs()
    sync_squads_from_gsheets()

    max_processed = get_max_processed_id()
    log.info(f"Highest processed match_id: {max_processed}")

    if max_processed >= MATCH_ID_MAX:
        log.info("All known match IDs processed. Nothing to do.")
        return

    candidates = [
        max_processed + i
        for i in range(1, MAX_NEW_PER_DAY + 1)
        if max_processed + i <= MATCH_ID_MAX
    ]
    log.info(f"Candidates to check: {candidates}")

    new_matches = []
    for match_id in candidates:
        complete = is_match_complete(match_id)
        if complete is None:
            log.info(f"Match {match_id}: not found. Stopping probe.")
            break
        if complete is False:
            log.info(f"Match {match_id}: not yet complete. Stopping.")
            break
        if not run_get_scorecard(match_id):
            log.error(f"Match {match_id}: fetch failed. Stopping.")
            break
        new_matches.append(match_id)

    if new_matches:
        log.info(f"New matches processed: {new_matches}")
        run_get_standings()
    else:
        log.info("No new matches processed today.")

    log.info(f"auto_update.py finished at {datetime.now().isoformat()}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
