# Progression Club: daily Reel automation

One Reel a day, fully automatic: pick the next row in `content/reels.csv` -> render a 1080x1920 text-and-motion video -> post it to Instagram -> mark the row posted -> top up the sheet with Claude when fewer than 5 rows are left. No voice, no AI images, no Facebook.

Cost: Reels cost nothing to render. The only API spend is the refill (a few cents per batch of 10 rows).

## What's in the repo

- `content/reels.csv`: 24 ready Reels (12 handstand, 12 pull-up). Columns: id, product, hook, slides, caption, hashtags, status, posted_at, media_id.
- `pipeline/make_reel.py`: draws the slides and builds the MP4.
- `pipeline/publish.py`: Instagram API with Instagram Login (no Facebook Page needed).
- `pipeline/refill.py`: asks Claude for new rows; drops anything with guarantee, cure, diagnosis or timeline wording.
- `pipeline/run.py`: the daily runner. Also writes `logs/runs.log` each run, which is the keepalive commit that stops GitHub disabling the schedule after 60 days of no activity.
- `.github/workflows/reel.yml`: runs daily at 13:30 UTC (7:00 pm IST). Also has a manual button.
- `fonts/`: Poppins (open font licence).

## Part 1: before Instagram exists (do now, about 10 minutes)

1. In your GitHub account create a **public** repo with an obscure name. It must be public so Instagram can download the video from a `raw.githubusercontent.com` link.
2. Upload every file from this folder (keep the folder layout, including the hidden `.github` folder). Easiest: unzip, then drag the contents into the repo's "Add file -> Upload files" page, or use GitHub Desktop.
3. Repo -> Settings -> Secrets and variables -> Actions -> **New repository secret**: add `ANTHROPIC_API_KEY`. Leave the two Instagram secrets for Part 2.
4. Repo -> Settings -> Actions -> General -> Workflow permissions -> choose **Read and write permissions**, Save.
5. Actions tab -> "Daily Reel" -> **Run workflow** (leave "dry run" ticked). When it finishes, open the run and download the `dry-run-reel` file to watch the first Reel. Nothing is posted or changed by a dry run.

## Part 2: after you create the Instagram account

1. Create the account on your phone. Switch it to a **Professional** account (Settings -> Account type and tools -> Switch to professional account, Creator is fine). Add the Whop link to the bio.
2. Go to developers.facebook.com -> create an app of type **Business** -> add the product **Instagram -> API setup with Instagram login**. (Your Meta developer login can be your normal Facebook login; no Facebook Page is created or linked to Instagram.)
3. Add your Instagram account as an **Instagram tester** and accept the invite inside Instagram (Settings -> Apps and websites -> Tester invites).
4. In "API setup with Instagram login" use **Generate access token** for your account, tick `instagram_business_basic` and `instagram_business_content_publish`. Copy the token and your Instagram user ID shown on that screen.
5. Add two more repo secrets: `IG_ACCESS_TOKEN` and `IG_USER_ID`.
6. Run the workflow once with "dry run" **unticked**. It should post Reel 001. Check Instagram.
7. From then on it posts daily on its own.

## Things to know

- **Token expiry.** Instagram User tokens normally last 60 days (from memory; Meta's publishing page doesn't state it). Every ~50 days run `IG_ACCESS_TOKEN=<token> python pipeline/publish.py refresh` on any computer, then paste the printed token into the `IG_ACCESS_TOKEN` secret. Put a calendar reminder on it. GitHub cannot refresh the secret by itself.
- **Pull-up Reels** are skipped until you turn them on. Repo -> Settings -> Secrets and variables -> Actions -> Variables -> new variable `ENABLED_PRODUCTS` = `handstand,pullup`. Do that when the pull-up product is live on Whop, so Reels never point at something you can't sell.
- **Scheduled runs** can start up to ~30 minutes late on GitHub. Normal.
- **Review before trusting.** Watch the first 3 to 5 posts. If a Reel looks wrong, edit its row in `content/reels.csv` (GitHub's web editor is fine) before it comes up.
- **Kill switch.** Actions tab -> Daily Reel -> "..." menu -> Disable workflow.
- **Instagram may limit new, never-warmed accounts.** You chose to skip warm-up. If posts are rejected or reach is near zero in the first days, that is the likely cause, not a bug.
- **Compliance.** All seed copy avoids medical claims, guarantees and promised timelines, and every caption ends with the "not medical advice" line. Keep that rule if you edit rows.
