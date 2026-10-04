#!/usr/bin/env bash
# Ubuntu 24.04 CI only. No Atlas installation or service activation.
set -euo pipefail

# Signed PGDG packages supply the same client major as the disposable server.
curl --fail --silent --show-error --proto '=https' --tlsv1.2 \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc -o "$RUNNER_TEMP/pgdg.asc"
test "$(gpg --show-keys --with-colons "$RUNNER_TEMP/pgdg.asc" | awk -F: '$1 == "fpr" {print $10; exit}')" = B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8
sudo install -m 0644 "$RUNNER_TEMP/pgdg.asc" /usr/share/keyrings/atlas-ci-pgdg.asc
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/atlas-ci-pgdg.asc] https://apt.postgresql.org/pub/repos/apt noble-pgdg main' \
  | sudo tee /etc/apt/sources.list.d/atlas-ci-pgdg.list > /dev/null
sudo apt-get update
sudo apt-get install --yes --no-install-recommends postgresql-client-17 libpcre2-dev zlib1g-dev
printf '%s\n' /usr/lib/postgresql/17/bin >> "$GITHUB_PATH"
/usr/lib/postgresql/17/bin/pg_dump --version
/usr/lib/postgresql/17/bin/pg_restore --version

# Ubuntu's nginx 1.24 lacks open-source upstream "resolve" used by the gateway.
# Build a fixed official source archive in temporary storage, never via sudo.
curl --fail --silent --show-error --proto '=https' --tlsv1.2 \
  https://nginx.org/download/nginx-1.28.3.tar.gz -o "$RUNNER_TEMP/nginx.tar.gz"
printf '%s  %s\n' 2c96a946bfb0882a21744ed429770a2123ae1828c7c48665092993ddee91a918 "$RUNNER_TEMP/nginx.tar.gz" | sha256sum -c -
tar -xzf "$RUNNER_TEMP/nginx.tar.gz" -C "$RUNNER_TEMP"
pushd "$RUNNER_TEMP/nginx-1.28.3"
./configure --prefix="$RUNNER_TEMP/atlas-ci-nginx"
make -j2
make install
popd
printf 'ATLAS_TEST_NGINX=%s/atlas-ci-nginx/sbin/nginx\n' "$RUNNER_TEMP" >> "$GITHUB_ENV"
"$RUNNER_TEMP/atlas-ci-nginx/sbin/nginx" -v
