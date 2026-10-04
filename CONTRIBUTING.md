# Contributing

Issues, reproducible bug reports, feedback and feature discussion are welcome.
Discuss external code contributions with the
[project maintainer](https://github.com/benchristian88) before submission.
Acceptance may require separate contributor/licensing terms in future; no such
terms or contributor agreement are established by this document.

The repository grants **AGPL-3.0-only** under [LICENSE](LICENSE). See
[commercial licensing](COMMERCIAL-LICENSING.md) for the separate position on
alternative terms.

Development normally starts from `dev`, uses a focused feature branch and a pull
request back to `dev`. Follow [AGENTS.md](AGENTS.md), inspect existing code/tests
before changing it and preserve user data, provenance and authorization.
Do not include secrets or real customer inventory in fixtures or screenshots.
Use [SECURITY.md](SECURITY.md) for vulnerability reports.

Run the relevant regressions and `git diff --check`; substantive changes need
appropriate tests and truthful documentation. UI changes must follow the
[UI architecture](docs/architecture/ui-architecture.md) and include responsive,
theme and accessibility checks. CI protects Backend / PostgreSQL, Frontend and
Release & Deployment Integrity. See [local checks](docs/testing/continuous-integration.md)
and [development setup](docs/development/from-source.md).
