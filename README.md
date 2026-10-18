# Instagram Followers Scraper — Export Followers & Following to CSV / JSON

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey.svg)

**Instagram Followers Scraper** is a free, open-source Python tool that exports the
**followers list** or **following list** of any Instagram profile you can see to
**CSV** (Excel / Google Sheets) and **JSON**.

It comes with a simple **local web app** (no coding needed) and a **command-line
interface**. No paid API, no third-party server, and no Instagram password: it runs
on your own computer (`127.0.0.1`) using your browser session cookie.

**Use it to:** download Instagram followers to Excel, back up who you follow, analyze
an audience, find mutual followers, or build a lead list from a public profile.

> [!WARNING]
> Instagram has no official API for exporting followers. Automated access may break
> Instagram's Terms of Use or trigger rate limits. Use small limits, only export data
> you are allowed to access, and handle personal data responsibly (GDPR/CCPA).

## Contents

- [Features](#features)
- [Quick start](#quick-start)
- [Get your Instagram cookies](#1-get-your-sessionid-and-csrftoken-cookies)
- [Find the profile ID](#2-find-the-profile-id)
- [Output format (CSV / JSON)](#output-format-csv--json)
- [Command-line usage](#command-line-usage)
- [Privacy and security](#privacy-and-security)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

## Features

- ✅ Export **Instagram followers** or **following** for any profile you can view
- ✅ Download results as **CSV** (opens in Excel) and **JSON**
- ✅ **Web interface** with live progress, plus an optional **CLI**
- ✅ One command to install and run (`./start.sh`)
- ✅ Built-in random delays to reduce rate limiting
- ✅ Automatic de-duplication and partial saves if Instagram stops a run
- ✅ Runs **locally only**: cookies are never saved to disk or sent anywhere except Instagram
- ✅ Offline test suite, no Instagram account needed to run tests

## Quick start

Requirements: macOS or Linux, **Python 3.9+**, and Chrome or Edge.

```bash
git clone https://github.com/husseinelsaadii/instagram-followers-scraper.git
cd instagram-followers-scraper
./start.sh
```

On first run, `start.sh` creates a virtual environment, installs the dependencies,
starts the server, and opens **http://127.0.0.1:5000** in your browser.
Stop it with **Ctrl+C**.

If you get "permission denied", run `chmod +x start.sh` once.

<details>
<summary>Manual install (pip)</summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

</details>

## How to use it

The app shows this guide on screen too. You need three things.

### 1. Get your `sessionid` and `csrftoken` cookies

1. Sign in at [instagram.com](https://www.instagram.com/) in Chrome or Edge.
2. Right-click the page and choose **Inspect** (or press `⌘ ⌥ I` / `Ctrl Shift I`).
3. Open **Application → Storage → Cookies → https://www.instagram.com**.
4. Copy the value of the `sessionid` cookie.
5. Copy the value of the `csrftoken` cookie.

> [!CAUTION]
> Your `sessionid` works like a password. Never paste it into a GitHub issue,
> screenshot, commit, or chat.

### 2. Find the profile ID

1. Keep DevTools open and select the **Network** tab.
2. Open the target profile and click its **followers** or **following** count.
3. Type `friendships` in the Network filter.
4. Find a request URL like this one:

```text
/api/v1/friendships/787132/followers/
```

The number (`787132` here) is the numeric Instagram user ID.

### 3. Start the export

Paste the cookies, enter the username and ID, choose **Followers** or **Following**,
set a maximum (start with 100), and click **Start export**. When it finishes, click
**Download CSV** or **Download JSON**.

## Output format (CSV / JSON)

Each run saves uniquely named files in the git-ignored `output/` folder:

```text
natgeo_followers_20261018-120000_abc123.csv
natgeo_followers_20261018-120000_abc123.json
```

| Column | Description |
| --- | --- |
| `id` | Instagram account ID |
| `username` | Account username |
| `full_name` | Display name |
| `is_private` | Whether the account is private |
| `is_verified` | Whether the account is verified (blue check) |
| `profile_url` | Link to the profile |
| `profile_pic_url` | Profile picture URL |
| `source_username` | Profile whose list was exported |

See [`examples/sample_output.json`](examples/sample_output.json) for an example.
CSV files are UTF-8 with BOM, so emoji and accented names display correctly in Excel.

## Command-line usage

```bash
cp config/settings.example.json config/settings.json   # then add your cookies
python3 scraper.py natgeo --user-id 787132 --list followers --max 100
python3 scraper.py natgeo --user-id 787132 --list following --max 100
```

You can also pass the cookie as an environment variable instead of a file:

```bash
IG_SESSIONID="your-session-id" python3 scraper.py natgeo --user-id 787132
```

| Option | Default | Description |
| --- | --- | --- |
| `username` | required | Target profile, without `@` |
| `--user-id` | looked up | Numeric profile ID (recommended) |
| `--list` | `followers` | `followers` or `following` |
| `--max` | `100` | Maximum accounts to fetch |
| `--out` | `output` | Output folder |

`config/settings.json` is git-ignored, so your cookies are not committed.

## Privacy and security

- The server listens on `127.0.0.1` only, not on your network.
- Cookies are typed into password fields and cleared from the page after you submit.
- Cookies are kept in memory only during the export. They are never written to config
  files, logs, URLs, job status, or output files.
- Cross-site requests are rejected, and strict security headers (CSP, no-frame,
  no-referrer) are sent.
- `config/settings.json` and `output/` are excluded by `.gitignore`.
- If you think your cookie leaked, log out of Instagram to invalidate the session.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Session invalid or expired | Sign in again and copy fresh `sessionid` and `csrftoken` values. |
| HTTP 429 / "Please wait a few minutes" | Instagram rate-limited you. Wait, then retry with a smaller maximum. |
| `checkpoint_required` | Open Instagram in the browser, finish the security check, then copy fresh cookies. |
| Private profile returns nothing | Your account must follow that private profile. |
| No `friendships` request in Network | Clear the list, make sure recording is on, and reopen the followers dialog. |
| Port 5000 is in use | Run `PORT=5001 ./start.sh` and open `http://127.0.0.1:5001`. |

If Instagram stops a run partway, the accounts collected so far are still saved.

## FAQ

**Is this an official Instagram API?**
No. It uses the same internal web endpoints that instagram.com calls in your browser.

**Do I need my Instagram password?**
No. It uses your browser's session cookie and never asks for your password.

**Can I export followers of a private account?**
Only if your account already follows it.

**How many followers can I export?**
Up to 100,000 per run in the web app. Large lists take time because requests are
spaced out on purpose. Very large exports are more likely to hit rate limits.

**Does it work on Windows?**
The Python code is cross-platform. On Windows, use the manual install steps
(activate with `.venv\Scripts\activate`) instead of `start.sh`.

## Tests

The tests use fake Instagram responses and need no account or network access:

```bash
python3 -m unittest
```

## Project structure

```text
app.py                  local web server and background export jobs
templates/index.html    web interface and setup guide
static/                 styles and browser code
start.sh                one-command setup and launch
scraper.py              command-line interface
instagram/client.py     Instagram requests, pagination, rate limiting
instagram/parser.py     turns API records into flat rows
instagram/exporter.py   CSV and JSON writers
tests/                  offline tests
examples/               sample output
```

## Contributing

Issues and pull requests are welcome. If this project helped you, please give it a ⭐.
Stars help other people find it.

## Disclaimer

This project is for personal and educational use. It is not affiliated with,
endorsed by, or connected to Instagram or Meta. You are responsible for following
Instagram's Terms of Use and applicable privacy laws.

## License

[MIT](LICENSE)
