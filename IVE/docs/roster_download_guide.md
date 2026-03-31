# Roster Download Guide

This guide walks through pulling a class roster CSV from ASU's MyASU system using the GAVEL CLI.

---

## Prerequisites checklist

- [ ] Python environment is set up and `GAVEL` is installed/runnable
- [ ] `IVE/.env` contains `ROSTER_AUTH_METHOD=selenium` (see [Configuration](#configuration))
- [ ] Google Chrome is installed
- [ ] ChromeDriver matching your Chrome version is on your `PATH`
- [ ] You have faculty-level access to the roster on MyASU
- [ ] You know your ASU term code (e.g., `2261`) — if you don't, `list-terms` will show you the name alongside the code (see Step 1)

---

## Configuration

Add one line to `IVE/.env`:

```env
ROSTER_AUTH_METHOD=selenium
```

That's all that is required. A Chrome browser will open and prompt you to log in with Duo MFA when you run a roster command.

---

## Step-by-step checklist

### 1. Confirm your term code (optional)

If you don't know the term code, list available terms first:

```bash
python -m GAVEL.cli.main roster list-terms
```

Note the code in the left column (e.g., `2261`).

---

### 2. Choose a download mode

**Option A — Direct (you already know the class number):**

```bash
python -m GAVEL.cli.main roster download \
  --term <TERM_CODE> \
  --class-number <5-DIGIT-CLASS-NUMBER> \
  --output roster.csv
```

Example:

```bash
python -m GAVEL.cli.main roster download \
  --term 2261 \
  --class-number 12345 \
  --output roster.csv
```

**Option B — Catalog lookup (you only know subject + catalog number):**

```bash
python -m GAVEL.cli.main roster download \
  --term <TERM_CODE> \
  --subject <SUBJECT> \
  --catalog-number <CATALOG-NUMBER> \
  --output roster.csv
```

Example:

```bash
python -m GAVEL.cli.main roster download \
  --term 2261 \
  --subject SER \
  --catalog-number 401 \
  --output roster.csv
```

If more than one section is found, the CLI will prompt you to select one.

---

### 3. Selenium auth — complete the browser login

> Skip this section if using `ROSTER_AUTH_METHOD=cookies`.

- [ ] A Chrome browser window opens automatically
- [ ] Log in with your ASU credentials on the CAS login page
- [ ] Complete Duo MFA when prompted
- [ ] Wait for the `[AUTH] Authentication successful` message in the terminal
- [ ] The browser minimizes , do not close it until the download finishes

The tool performs **one** browser login and reuses the session for both the catalog API token and the roster download. You will **not** be prompted for a second Duo push in the same session.

> If the session expires (default TTL: 10 minutes), the tool will attempt a **silent refresh** using the existing CAS session before falling back to a full re-login.

---

### 4. Verify the output

- [ ] `roster.csv` was created at the path you specified
- [ ] Open in Excel — rows should appear without extra blank lines
- [ ] Confirm the expected students are present

---

## Flags reference

| Flag | Required | Description |
| --- | --- | --- |
| `--term` | Yes | ASU term code (e.g., `2261`) |
| `--class-number` | Mode A | Five-digit class number |
| `--subject` | Mode B | Subject prefix (e.g., `SER`) |
| `--catalog-number` | Mode B | Catalog number (e.g., `401`) |
| `--output` / `-o` | No | Save CSV to file; omit to print to stdout |
| `--info-only` | No | Print resolved term/class number without downloading, like a dry run |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `ROSTER_AUTH_METHOD not set; roster features disabled` | Missing env var | Set `ROSTER_AUTH_METHOD` in `.env` |
| `Authentication timed out or browser closed` | Duo MFA took too long | Increase `ROSTER_MFA_TIMEOUT` in `.env` |
| `Received HTML instead of CSV` | Insufficient permissions or bad term/class | Verify faculty access; confirm term and class number with `--info-only` |
| `Session expired or invalid. Re-authentication required` | MyASU cookies expired | Re-run the command; a fresh browser login will be triggered |

---

## Environment variable reference

All variables go in `IVE/.env`. Only `ROSTER_AUTH_METHOD` is required for Selenium.

| Variable | Default | Description |
| --- | --- | --- |
| `ROSTER_AUTH_METHOD` | _(none)_ | Auth method to use. Must be `selenium` or `cookies`. Roster features are disabled if unset. |
| `ROSTER_TOKEN` | _(none)_ | Pre-existing catalog API JWT. If set, skips the catalog token fetch step during auth entirely. |
| `ROSTER_MFA_TIMEOUT` | `120` | Seconds to wait for you to complete CAS login and Duo MFA in the browser before timing out. |
| `ROSTER_SESSION_TTL` | `600` | Seconds before the cached session is considered expired. After expiry, the tool attempts a silent refresh before prompting for a full re-login. |
| `ROSTER_HTTP_TIMEOUT` | `30` | Seconds to wait for each HTTP request (CSV download, catalog API calls). |
| `ROSTER_PAGE_LOAD_TIMEOUT` | `30` | Seconds to wait for the browser to land on the expected domain after a navigation. |
| `ROSTER_TOKEN_EXCHANGE_TIMEOUT` | `30` | Seconds to wait for the catalog SPA to exchange the OAuth code for a JWT after redirect. |
| `ROSTER_COOKIE_FILE` | _(none)_ | Path to a Netscape-format cookie file. Required when `ROSTER_AUTH_METHOD=cookies`. |

---

## Addendum: cookie-file auth (headless, no browser)

If you need to run without a browser (e.g., on a server), you can authenticate using a Netscape-format cookie file exported from a logged-in browser session.

Set these two variables in `IVE/.env`:

```env
ROSTER_AUTH_METHOD=cookies
ROSTER_COOKIE_FILE=/path/to/cookies.txt
```

Everything else in this guide works the same. The CLI will load the cookie file instead of opening Chrome, and no Duo MFA prompt will appear.

> The cookie file must contain valid, unexpired MyASU session cookies. If the file is stale, the download will fail with `Session expired or invalid. Re-authentication required` — re-export the cookies from your browser and try again.
