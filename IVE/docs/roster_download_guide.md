# Roster Download Guide

This guide walks through pulling a class roster CSV from ASU's MyASU system using the GAVEL tool.

The roster can be downloaded through one of two ways: The Command Line Interface (CLI) or the Graphical User Interface (GUI). This guide covers the use of the CLI tool.

---

## Prerequisites checklist

Before you can download the roster using any method, the following must be true:

- [ ] Python environment is set up and `GAVEL` is installed/runnable
- [ ] Google Chrome is installed
- [ ] ChromeDriver matching your Chrome version is on your `PATH`
- [ ] You have faculty-level access to the roster on MyASU

---

## Configuration

The `IVE/.env` file is used to control many shared configuration variables across the GAVEL applicaiton. To download the roster in all cases, the tool needs a way to authenticate. By default, it uses selenium. If you are in an environment without browser access and would like, you can change the `.env` file to use a cookie file instead. See [cookie-file auth](#addendum-cookie-file-auth-headless-no-browser)

Confirm that the `IVE/.env` has the following line configured, or it is not set at all to allow the default. 

```env
ROSTER_AUTH_METHOD=selenium
```

That's all that is required. A Chrome browser will open and prompt you to log in with Duo MFA when you run a roster command.

---

## Step-by-step checklist

### 1. Navigate to the IVE path

For example
`cd /git/SER401_Team5/IVE`

**Note**: All commands in this guide use python -m to run GAVEL as a module. This is required because GAVEL uses relative imports. Always run commands from the IVE/ directory in the form:


`python -m GAVEL.cli.main <command> [options]`


### 2. Confirm your term code (optional)

myASU requires a `term code` to be provided when downloading a roster. The term codes are static and follow a 4-digit format: 

#### Term Format
`2[YY][T]`

| Segment | Description |
|---------|-------------|
| `2` | Fixed prefix |
| `YY` | Two-digit calendar year |
| `T` | Term identifier digit |

#### Term Identifier Digits

| Digit | Term |
|-------|------|
| `1` | Spring |
| `4` | Summer |
| `7` | Fall |
| `9` | Winter |

#### Examples
 
| Code | Breakdown | Term |
|------|-----------|------|
| 2267 | 2 + 26 + 7 | Fall 2026 |
| 2264 | 2 + 26 + 4 | Summer 2026 |
| 2261 | 2 + 26 + 1 | Spring 2026 |
| 2109 | 2 + 10 + 9 | Winter 2010 |

#### Reference
For reference you can use this table of terms as of Spring 2026

| Code | Term |
|------|------|
| 2267 | Fall 2026 (default) |
| 2264 | Summer 2026 |
| 2261 | Spring 2026 |
| 2257 | Fall 2025 |
| 2254 | Summer 2025 |
| 2251 | Spring 2025 |
| 2247 | Fall 2024 |
| 2244 | Summer 2024 |
| 2241 | Spring 2024 |
| 2237 | Fall 2023 |
| 2234 | Summer 2023 |
| 2231 | Spring 2023 |
| 2227 | Fall 2022 |
| 2224 | Summer 2022 |
| 2221 | Spring 2022 |
| 2217 | Fall 2021 |
| 2214 | Summer 2021 |
| 2211 | Spring 2021 |
| 2207 | Fall 2020 |
| 2204 | Summer 2020 |
| 2201 | Spring 2020 |
| 2197 | Fall 2019 |
| 2194 | Summer 2019 |
| 2191 | Spring 2019 |
| 2187 | Fall 2018 |
| 2184 | Summer 2018 |
| 2181 | Spring 2018 |
| 2177 | Fall 2017 |
| 2174 | Summer 2017 |
| 2171 | Spring 2017 |
| 2167 | Fall 2016 |
| 2164 | Summer 2016 |
| 2161 | Spring 2016 |
| 2157 | Fall 2015 |
| 2154 | Summer 2015 |
| 2151 | Spring 2015 |
| 2147 | Fall 2014 |
| 2144 | Summer 2014 |
| 2141 | Spring 2014 |
| 2137 | Fall 2013 |
| 2134 | Summer 2013 |
| 2131 | Spring 2013 |
| 2127 | Fall 2012 |
| 2124 | Summer 2012 |
| 2121 | Spring 2012 |
| 2117 | Fall 2011 |
| 2114 | Summer 2011 |
| 2111 | Spring 2011 |
| 2109 | Winter 2010 |
| 2107 | Fall 2010 |
| 2104 | Summer 2010 |
| 2101 | Spring 2010 |
| 2099 | Winter 2009 |
| 2097 | Fall 2009 |
| 2094 | Summer 2009 |
| 2091 | Spring 2009 |
| 2089 | Winter 2008 |
| 2087 | Fall 2008 |
| 2084 | Summer 2008 |
| 2081 | Spring 2008 |
| 2079 | Winter 2007 |
| 2077 | Fall 2007 |


#### Lookup
If you don't know the term code and want to verify what you derived from above, you can quickly list available terms first:

```bash
python -m GAVEL.cli.main roster list-terms
```

Note the code in the left column (e.g., `2261`).

---

### (CLI) 3. Choose a download mode

The roster can be downloaded through the CLI using one of two methods:

**Option A — Direct (you already know the class number):**

```bash
python -m GAVEL.cli.main roster download \
  --term <TERM_CODE> \
  --class-number <5-DIGIT-CLASS-NUMBER> \
  --course-folder <COURSE_FOLDER>
```

Example:

```bash
python -m GAVEL.cli.main roster download \
  --term 2261 \
  --class-number 12345 \
  --course-folder ser401_26f_12345
```

**Option B — Catalog lookup (you only know subject + catalog number):**

```bash
python -m GAVEL.cli.main roster download \
  --term <TERM_CODE> \
  --subject <SUBJECT> \
  --catalog-number <CATALOG-NUMBER>
```

Example:

```bash
python -m GAVEL.cli.main roster download \
  --term 2261 \
  --subject SER \
  --catalog-number 401
```

If more than one section is found, the CLI will prompt you to select one.

The roster is saved as `original/roster.csv` inside the course folder,
`<workspace>/courses/<course folder>/` (see `docs/workspace_layout.md`). In lookup
mode the course folder is named from the term and the section you pick; in direct
mode a class number alone cannot name it, so `--course-folder` is required.

---

### 4. Selenium auth — complete the browser login

> Skip this section if using `ROSTER_AUTH_METHOD=cookies`.

- [ ] A Chrome browser window opens automatically
- [ ] If a sign-in page appears, log in with your ASU credentials on the CAS login page (filled in for you when `CANVAS_USERNAME` and `CANVAS_PASSWORD` are set in `.env`)
- [ ] Complete Duo MFA if prompted
- [ ] Wait for the `[AUTH] Roster session ready.` message in the terminal
- [ ] The browser minimizes , do not close it until the download finishes

The tool performs **one** browser login and reuses the session for both the catalog API token and the roster download. You will **not** be prompted for a second Duo push in the same session.

> If the session expires (default TTL: 10 minutes), the tool will attempt a **silent refresh** using the existing CAS session before falling back to a full re-login.

#### Staying signed in

The roster download and the Gradescope download share one login browser:

- **Within one run of the app**, the first download that needs an ASU login performs it and the browser stays open (minimized) afterwards. Later downloads reuse it, so "Download All" in the GUI asks for Duo once at most. The browser closes when the app or the CLI command exits. If you close it yourself, the next download opens a new one.
- **Between runs**, the browser's ASU and Duo cookies are saved when a download finishes and put back the next time a browser is started. The tool also answers Duo's "Is this your device?" question with "Yes, this is my device", so Duo can remember the browser. How long that skips the login is decided by ASU's session and Duo policies, not by this tool. When the saved login is no longer accepted, the normal sign-in page appears and you log in as before.

The saved login is a file of cookies in your user profile, outside the project folder:

| OS | Location |
| --- | --- |
| Windows | `%LOCALAPPDATA%\GAVEL\asu_login_cookies.json` |
| macOS | `~/Library/Application Support/GAVEL/asu_login_cookies.json` |
| Linux | `~/.local/state/GAVEL/asu_login_cookies.json` |

Treat that file like a logged-in browser: anyone who can read it can act as you on ASU sites until the cookies expire. To delete it:

```bash
python -m GAVEL.cli.main asu-login forget
```

On a shared computer, set `ASU_LOGIN_REMEMBER=false` in `.env`. Nothing is saved, any existing saved login is deleted on the next start, and Duo is told the device is shared.

---

### 5. Verify the output

- [ ] `original/roster.csv` was created inside the course folder, and `manifest.json` next to it lists it
- [ ] Open in Excel. The rows should appear without extra blank lines
- [ ] Confirm the expected students are present

---

## Flags reference

| Flag | Required | Description |
| --- | --- | --- |
| `--term` | Yes | ASU term code (e.g., `2261`) |
| `--class-number` | Mode A | Five-digit class number |
| `--subject` | Mode B | Subject prefix (e.g., `SER`) |
| `--catalog-number` | Mode B | Catalog number (e.g., `401`) |
| `--workspace` | No | Workspace root. Defaults to `DEFAULT_OUTPUT_DIR` from `.env`, else `~/Downloads/GAVEL` |
| `--course-folder` | See note | Course folder name such as `ser222_25sc_12345`. Canvas commands derive it from `--course-id` when omitted |
| `--overwrite` | No | Replace files already downloaded into the course folder; without it a second download is refused |
| `--info-only` | No | Print resolved term/class number without downloading, like a dry run |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `ROSTER_AUTH_METHOD not set; roster features disabled` | Missing env var | Set `ROSTER_AUTH_METHOD` in `.env` |
| `Authentication timed out or browser closed` | Duo MFA took too long | Increase `ROSTER_MFA_TIMEOUT` in `.env` |
| `Could not obtain catalog token` or `Timed out ... waiting for the ASU login to finish` | The login was not completed in time, or the saved credentials were rejected | Finish the login in the browser window; check `CANVAS_USERNAME` / `CANVAS_PASSWORD`; increase `ROSTER_MFA_TIMEOUT` |
| `The ASU catalog rejected the login token (HTTP 401)` | `ROSTER_TOKEN` in `.env` has expired | Remove `ROSTER_TOKEN` to sign in through the browser, or paste a new token |
| Asked to log in on every run even with `ASU_LOGIN_REMEMBER=true` | The saved login expired, or ASU's Duo policy does not remember browsers for long | Nothing to fix; run `asu-login forget` and log in once more if the saved login seems stuck |
| `Received HTML instead of CSV` | Insufficient permissions or bad term/class | Verify faculty access; confirm term and class number with `--info-only` |
| `Session expired or invalid. Re-authentication required` | MyASU cookies expired | Re-run the command; a fresh browser login will be triggered |

---

## Environment variable reference

All variables go in `IVE/.env`.

| Variable | Default | Description |
| --- | --- | --- |
| `ROSTER_AUTH_METHOD` | _(none)_ | Auth method to use. Must be `selenium` or `cookies`. Roster features are disabled if unset. |
| `ROSTER_TOKEN` | _(none)_ | Pre-existing catalog API JWT. If set, skips the catalog token fetch step during auth entirely. |
| `ASU_LOGIN_REMEMBER` | `true` | `true` keeps the browser's ASU login between runs (see [Staying signed in](#staying-signed-in)). `false` signs in fresh each run and deletes any saved login. |
| `ROSTER_MFA_TIMEOUT` | `120` | Seconds to wait for you to complete CAS login and Duo MFA in the browser before timing out. Also applies to the Gradescope download's login. |
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
