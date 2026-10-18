"""Offline tests: Instagram's responses are faked, no network or account needed.

Run from the project folder with: python3 -m unittest
"""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from instagram.client import InstagramError, InstagramFollowerScraper
from instagram.exporter import export_to_csv, export_to_json
from instagram.parser import parse_followers


def fake_response(payload, status=200, url="https://www.instagram.com/api/v1/x"):
    response = MagicMock(status_code=status, url=url)
    response.json.return_value = payload
    return response


def make_user(n):
    return {"pk": n, "username": f"user{n}", "full_name": f"User {n} 🙂",
            "is_private": n % 2 == 0, "is_verified": False, "profile_pic_url": f"https://pic/{n}"}


def make_scraper(responses):
    scraper = InstagramFollowerScraper("fake-session", delay=(0, 0))
    scraper.session.get = MagicMock(side_effect=responses)
    return scraper


class ScraperTests(unittest.TestCase):
    def test_paginates_until_no_next_max_id(self):
        scraper = make_scraper([
            fake_response({"users": [make_user(1), make_user(2)], "next_max_id": "abc"}),
            fake_response({"users": [make_user(3)]}),
        ])
        users = list(scraper.iter_followers("42", max_count=100))

        self.assertEqual([u["username"] for u in users], ["user1", "user2", "user3"])
        second_call_params = scraper.session.get.call_args_list[1].kwargs["params"]
        self.assertEqual(second_call_params["max_id"], "abc")

    def test_skips_followers_repeated_across_pages(self):
        scraper = make_scraper([
            fake_response({"users": [make_user(1), make_user(2)], "next_max_id": "abc"}),
            fake_response({"users": [make_user(2), make_user(3)]}),
        ])
        users = list(scraper.iter_followers("42", max_count=100))

        self.assertEqual([u["username"] for u in users], ["user1", "user2", "user3"])

    def test_stops_at_max_count(self):
        scraper = make_scraper([
            fake_response({"users": [make_user(i) for i in range(25)], "next_max_id": "abc"}),
        ])
        users = list(scraper.iter_followers("42", max_count=10))

        self.assertEqual(len(users), 10)
        self.assertEqual(scraper.session.get.call_count, 1)

    def test_following_uses_following_endpoint(self):
        scraper = make_scraper([fake_response({"users": [make_user(1)]})])

        users = list(scraper.iter_following("42", max_count=10))

        self.assertEqual([u["username"] for u in users], ["user1"])
        requested_url = scraper.session.get.call_args.args[0]
        self.assertTrue(requested_url.endswith("/friendships/42/following/"))

    def test_no_max_fetches_until_last_page(self):
        scraper = make_scraper([
            fake_response({"users": [make_user(1)], "next_max_id": "next"}),
            fake_response({"users": [make_user(2)]}),
        ])

        users = list(scraper.iter_followers("42", max_count=None))

        self.assertEqual([u["username"] for u in users], ["user1", "user2"])

    def test_get_profile(self):
        scraper = make_scraper([fake_response({"data": {"user": {
            "id": "42", "is_private": False, "edge_followed_by": {"count": 1234}}}})])

        self.assertEqual(scraper.get_profile("someone"), {"id": "42", "follower_count": 1234})

    def test_private_profile_not_followed_is_rejected(self):
        scraper = make_scraper([fake_response({"data": {"user": {
            "id": "42", "is_private": True, "followed_by_viewer": False,
            "edge_followed_by": {"count": 5}}}})])

        with self.assertRaisesRegex(InstagramError, "private"):
            scraper.get_profile("someone")

    def test_expired_session_redirects_to_login(self):
        scraper = make_scraper([fake_response({}, url="https://www.instagram.com/accounts/login/")])

        with self.assertRaisesRegex(InstagramError, "sessionid"):
            scraper.get_profile("someone")

    def test_blocked_profile_lookup_suggests_user_id(self):
        scraper = make_scraper([fake_response({}, status=429)])

        with self.assertRaisesRegex(InstagramError, "--user-id"):
            scraper.get_profile("someone")

    def test_warm_up_prefers_configured_csrftoken(self):
        scraper = InstagramFollowerScraper("fake-session", csrftoken="mine")

        def homepage(*args, **kwargs):
            scraper.session.cookies.set("csrftoken", "from-instagram", domain="www.instagram.com")
            return fake_response({})

        scraper.session.get = MagicMock(side_effect=homepage)
        scraper.warm_up()

        self.assertEqual(scraper.session.headers["X-CSRFToken"], "mine")

    def test_rate_limit_error_includes_instagram_message(self):
        scraper = make_scraper([fake_response({"message": "Please wait a few minutes"}, status=429)])

        with self.assertRaisesRegex(InstagramError, "429.*Please wait"):
            list(scraper.iter_followers("42", max_count=10))


class OutputTests(unittest.TestCase):
    def test_parse_and_export(self):
        rows = parse_followers([make_user(1), make_user(2)], "target")
        self.assertEqual(rows[0]["id"], "1")
        self.assertEqual(rows[0]["profile_url"], "https://www.instagram.com/user1/")
        self.assertEqual(rows[1]["source_username"], "target")

        with tempfile.TemporaryDirectory() as tmp:
            json_path = export_to_json(rows, Path(tmp) / "out" / "f.json")
            csv_path = export_to_csv(rows, Path(tmp) / "out" / "f.csv")

            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), rows)
            with csv_path.open(encoding="utf-8-sig") as f:
                csv_rows = list(csv.DictReader(f))
            self.assertEqual(csv_rows[0]["full_name"], "User 1 🙂")
            self.assertEqual(len(csv_rows), 2)


if __name__ == "__main__":
    unittest.main()
