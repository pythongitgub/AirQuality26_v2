# AQ26 disable automatic smoke-test runs

This patch changes `.github/workflows/smoketest.yml` so it runs manually only.

Why:
- The old smoke-test workflow was triggered on every push.
- Uploading several patch commits caused many duplicate smoke-test runs.
- WeeklyV2 is now the primary evidence workflow.
- Smoke tests should be run only when secrets or provider setup changes.

What changed:
- Removed `push:` trigger.
- Kept `workflow_dispatch:` manual trigger.
- Added concurrency with `cancel-in-progress: true`.
- Reduced artifact retention to 7 days.

Recommended use:
- Run `AQ26 Secret Smoke Test` manually after changing API keys/secrets.
- Run `AQ26 WeeklyV2 Evidence Harvest` for actual weekly evidence generation.
