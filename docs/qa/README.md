# QA evidence

Each pass has a Persian report (`report.md`) and the machine-readable
observations captured in Chromium (`observations.json`).

**Screenshots are deliberately not tracked.** They are reproduced locally by
`scripts/qa/*.cjs` against a production build:

```bash
cd apps/studio && npm run build          # bundle the Studio
node scripts/qa/fourth-pass-live.cjs before   # baseline bundle
node scripts/qa/fourth-pass-live.cjs after    # current bundle
```

The scripts write into `docs/qa/<pass>/{before,after}/`; `.gitignore` ignores
`docs/qa/**/*.jpg`, so a local run never dirties the working tree. The reports
name the screenshots in prose (which image shows what) rather than linking to
them, and the `observations.json` files carry the claims that matter, so the
audit stays readable from a fresh clone.
