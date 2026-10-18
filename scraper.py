"""Export the followers or following list of an Instagram profile.

Usage:
    python3 scraper.py <username> --user-id <profile_id> --list followers --max 100

Your login is read from config/settings.json, or from the IG_SESSIONID
environment variable. See README.md for setup.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

from instagram.client import InstagramError, InstagramFollowerScraper
from instagram.exporter import export_to_csv, export_to_json
from instagram.parser import parse_followers

CONFIG_PATH = Path(__file__).parent / "config" / "settings.json"


def load_settings():
    settings = {}
    if CONFIG_PATH.exists():
        settings = json.loads(CONFIG_PATH.read_text())
    if os.environ.get("IG_SESSIONID"):
        settings["sessionid"] = os.environ["IG_SESSIONID"]
    if not settings.get("sessionid") or settings["sessionid"] == "YOUR_SESSION_ID":
        sys.exit("No sessionid: set IG_SESSIONID or fill in config/settings.json")
    return settings


def main():
    parser = argparse.ArgumentParser(
        description="Export an Instagram profile's followers or following list."
    )
    parser.add_argument("username", help="target profile, without the @")
    parser.add_argument("--user-id", help="numeric id of the profile; skips the profile lookup")
    parser.add_argument(
        "--list",
        dest="relationship",
        choices=("followers", "following"),
        default="followers",
        help="list to export (default: followers)",
    )
    parser.add_argument("--max", type=int, default=100, help="max accounts to fetch (default 100)")
    parser.add_argument("--out", default="output", help="output folder (default output/)")
    args = parser.parse_args()

    settings = load_settings()
    scraper = InstagramFollowerScraper(
        settings["sessionid"],
        csrftoken=settings.get("csrftoken"),
        delay=tuple(settings.get("delay_seconds", (2.0, 5.0))),
    )
    scraper.warm_up()

    if args.user_id:
        user_id = args.user_id
        print(
            f"@{args.username} (id {user_id}): fetching up to "
            f"{args.max} {args.relationship}"
        )
    else:
        profile = scraper.get_profile(args.username)
        user_id = profile["id"]
        print(f"@{args.username}: fetching up to {args.max} {args.relationship}")

    raw = []
    try:
        for user in scraper.iter_relationships(user_id, args.relationship, args.max):
            raw.append(user)
            if len(raw) % 100 == 0:
                print(f"  {len(raw)} fetched...")
    except (InstagramError, requests.RequestException, KeyboardInterrupt) as error:
        # Keep whatever we got so far instead of losing it.
        print(f"Stopped early: {str(error) or 'interrupted'}")

    accounts = parse_followers(raw, args.username)
    out_dir = Path(args.out)
    stem = f"{args.username}_{args.relationship}"
    json_path = export_to_json(accounts, out_dir / f"{stem}.json")
    csv_path = export_to_csv(accounts, out_dir / f"{stem}.csv")
    print(f"Saved {len(accounts)} {args.relationship} to {json_path} and {csv_path}")


if __name__ == "__main__":
    try:
        main()
    except InstagramError as error:
        sys.exit(f"Error: {error}")
