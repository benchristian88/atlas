# Security policy

Security reports concerning Atlas Impact's current beta application, supported
installers, backup/restore and release tooling are welcome. Use the latest
available matching beta package; older beta builds have no guaranteed security
maintenance period. Atlas has no established response SLA or enterprise security
certification.

## Reporting a vulnerability

Do not publish exploitable details, credentials or private inventory in public
issues. The repository currently documents no established private reporting
channel. Through the existing [project owner identity](https://github.com/benchristian88),
request a private reporting route before sending sensitive details. Do not assume
a security email, enabled GitHub private reporting or a public issue is private.

Once a private route is agreed, include the affected version/build and install
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
