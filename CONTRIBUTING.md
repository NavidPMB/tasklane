# Contributing to Tasklane

Bug reports, improvements and pull requests are welcome.

1. Follow the [README](README.md) to install Tasklane and create your own account.
2. Create a branch for your change.
3. Keep project-specific logic in `backend/modules/work/`. Browser and MCP operations should share validation and permissions through `services.execute` and `OPERATIONS`.
4. Read `AGENTS.md` for repository conventions. Frontend changes should also follow `frontend/AGENTS.md` and the documentation shipped with the installed Next.js version.
5. Add meaningful tests for changes to access control, hierarchy, workflow or MCP behavior. PostgreSQL is also required for tests.
6. Run `make test` and `make check`, then open a pull request describing the behavior and how you verified it.

Keep `.env`, real credentials, database exports and generated dependencies out of commits. Documentation examples should use placeholder accounts such as `you@example.com`. The default setup intentionally creates no shared demo account.

User-facing text is currently German. Keep the README and public setup instructions approachable for people who are new to the project.
