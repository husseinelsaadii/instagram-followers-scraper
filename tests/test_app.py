"""Validation tests for the localhost app. No network access is used."""

import unittest
from unittest.mock import patch

import app as app_module
from app import app, jobs, jobs_lock, validate_job_payload


class AppValidationTests(unittest.TestCase):
    def valid_payload(self, **overrides):
        payload = {
            "sessionid": "session-value",
            "csrftoken": "csrf-value",
            "username": "example.user",
            "user_id": "123456789",
            "relationship": "followers",
            "max_results": "100",
        }
        payload.update(overrides)
        return payload

    def test_valid_payload_is_normalized(self):
        result = validate_job_payload(self.valid_payload(username="@example.user"))

        self.assertEqual(result["username"], "example.user")
        self.assertEqual(result["max_results"], 100)

    def test_blank_max_means_all(self):
        result = validate_job_payload(self.valid_payload(max_results=""))

        self.assertIsNone(result["max_results"])

    def test_rejects_non_numeric_profile_id(self):
        with self.assertRaisesRegex(ValueError, "numbers only"):
            validate_job_payload(self.valid_payload(user_id="abc"))

    def test_rejects_unknown_list_type(self):
        with self.assertRaisesRegex(ValueError, "Followers or Following"):
            validate_job_payload(self.valid_payload(relationship="likes"))

    def test_home_has_no_store_and_security_headers(self):
        with app.test_client() as client:
            response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_job_status_never_stores_or_returns_credentials(self):
        with patch.object(app_module.executor, "submit") as submit:
            with app.test_client() as client:
                response = client.post(
                    "/api/jobs",
                    json=self.valid_payload(),
                    headers={"Origin": "http://localhost"},
                )

        self.assertEqual(response.status_code, 202)
        body = response.get_json()
        self.assertNotIn("sessionid", body)
        self.assertNotIn("csrftoken", body)
        with jobs_lock:
            stored_job = jobs.pop(body["id"])
        self.assertNotIn("sessionid", stored_job)
        self.assertNotIn("csrftoken", stored_job)
        submitted_form = submit.call_args.args[2]
        self.assertEqual(submitted_form["sessionid"], "session-value")

    def test_cross_site_submission_is_rejected(self):
        with app.test_client() as client:
            response = client.post(
                "/api/jobs",
                json=self.valid_payload(),
                headers={"Origin": "https://untrusted.example"},
            )

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
