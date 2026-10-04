# Security policy

Security reports concerning Atlas Impact's current beta application, supported
installers, backup/restore and release tooling are welcome. Use the latest
available matching beta package; older beta builds have no guaranteed security
maintenance period. Atlas has no established response SLA or enterprise security
certification.

## Reporting a vulnerability

Use **GitHub Private Vulnerability Reporting** for Atlas security vulnerabilities.
Open the [official repository](https://github.com/benchristian88/atlas), select its
**Security** (or **Security and quality**) tab, then **Report a vulnerability**
on the advisories page. Submit the report through that private form. See
[GitHub's reporting instructions](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/report-privately).
Do not publish exploitable details, credentials or private inventory in public
Issues, discussions or pull requests.

This policy does not establish that reporting is enabled in GitHub settings.
If the reporting button is absent, do not post vulnerability details publicly.
The repository owner must enable **Private vulnerability reporting** under
**Settings → Advanced Security** if it is not already enabled; see
[GitHub's configuration instructions](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository).

In the private report, include the affected version/build and install
method, the affected component, prerequisites, reproducible steps and observed
impact. Use a disposable environment and redact credentials, session cookies,
setup codes, authenticator seeds, recovery codes and customer data. Do not send
database dumps or backup archives unless a secure transfer is explicitly agreed.

Coordinate disclosure with the maintainer so a fix and operator guidance can be
prepared. There is no promised response or disclosure deadline.

## Operator responsibilities and updates

Protect host access and generated configuration, use HTTPS where appropriate,
limit trusted proxies and keep independent encrypted backups. The API enforces
permissions and customer/site scope. MFA is optional; setup codes and local
recovery commands require protected operator access.

Dependency and security updates are reviewed through the repository's tests and
release process. Update checks are informational; operators install verified
packages themselves. Final dependency and whole-product security qualification
remains part of preparation for 1.0. See the
[installation](docs/deployment/installation.md),
[MFA](docs/deployment/mfa.md), [backup](docs/deployment/backup-restore.md) and
[upgrade](docs/deployment/upgrades.md) guides.
