"""Client for Instagram's internal web API (the one instagram.com itself calls)."""
import random
import time

import requests

API_URL = "https://www.instagram.com/api/v1"
# Public app id of instagram.com; the web API rejects requests without it.
WEB_APP_ID = "936619743392459"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


class InstagramError(Exception):
    pass


class InstagramFollowerScraper:
    def __init__(self, sessionid, csrftoken=None, page_size=25, delay=(2.0, 5.0)):
        self.page_size = page_size
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "X-IG-App-ID": WEB_APP_ID,
            "Referer": "https://www.instagram.com/",
        })
        self.session.cookies.set("sessionid", sessionid, domain=".instagram.com")
        self.csrftoken = csrftoken

    def warm_up(self):
        """Load the homepage like a browser does, to get the cookies and csrftoken the API expects."""
        self.session.get("https://www.instagram.com/", timeout=30)
        if self.csrftoken:
            self.session.cookies.set("csrftoken", self.csrftoken, domain=".instagram.com")
        else:
            self.csrftoken = next((c.value for c in self.session.cookies if c.name == "csrftoken"), "")
        self.session.headers.update({
            "X-CSRFToken": self.csrftoken,
            "X-Requested-With": "XMLHttpRequest",
        })

    def _get(self, path, params=None):
        response = self.session.get(f"{API_URL}{path}", params=params, timeout=30)
        if "/accounts/login" in response.url:
            raise InstagramError("Not logged in: sessionid is missing, invalid or expired.")
        if response.status_code != 200:
            try:
                message = response.json().get("message", "")
            except ValueError:
                message = ""
            raise InstagramError(f"HTTP {response.status_code} on {path} {message}".strip())
        return response.json()

    def get_profile(self, username):
        """Return the target's id and follower count, checking we can see its followers."""
        try:
            user = self._get("/users/web_profile_info/", {"username": username})["data"]["user"]
        except InstagramError as error:
            raise InstagramError(
                f"{error}\nInstagram blocked the profile lookup. Pass the profile id directly "
                f"with --user-id (see README: 'Find the profile ID')."
            ) from error
        if user is None:
            raise InstagramError(f"Profile '{username}' not found.")
        if user["is_private"] and not user.get("followed_by_viewer"):
            raise InstagramError(f"Profile '{username}' is private and you don't follow it.")
        return {"id": user["id"], "follower_count": user["edge_followed_by"]["count"]}

    def iter_relationships(self, user_id, relationship, max_count=None):
        """Yield followers or followed accounts page by page.

        ``max_count=None`` continues until Instagram has no more pages. Pages can
        overlap, so users are de-duplicated before they are yielded.
        """
        if relationship not in {"followers", "following"}:
            raise ValueError("relationship must be 'followers' or 'following'")

        seen = set()  # pages can overlap, so the same follower may come back twice
        max_id = None
        while max_count is None or len(seen) < max_count:
            params = {"count": self.page_size}
            if max_id:
                params["max_id"] = max_id
            data = self._get(f"/friendships/{user_id}/{relationship}/", params)

            for user in data.get("users", []):
                user_key = user.get("pk") or user.get("username")
                if user_key in seen:
                    continue
                seen.add(user_key)
                yield user
                if max_count is not None and len(seen) >= max_count:
                    return

            max_id = data.get("next_max_id")
            if not max_id:
                return
            time.sleep(random.uniform(*self.delay))

    def iter_followers(self, user_id, max_count=None):
        """Yield accounts that follow ``user_id``."""
        yield from self.iter_relationships(user_id, "followers", max_count)

    def iter_following(self, user_id, max_count=None):
        """Yield accounts followed by ``user_id``."""
        yield from self.iter_relationships(user_id, "following", max_count)
