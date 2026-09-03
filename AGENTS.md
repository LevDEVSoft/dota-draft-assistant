# Repository workflow

After every successfully completed task:

1. Run the relevant tests.
2. Run `git diff --check`.
3. Review `git status --short`.
4. If verification passes, create one meaningful commit.
5. Push the commit to `origin main`.
6. Verify that the push succeeded.
7. Report the commit hash and push result.

Never:
- commit or push failing code
- force-push
- create empty or artificial commits
- commit secrets, API tokens, generated snapshots, caches, or ignored local data
