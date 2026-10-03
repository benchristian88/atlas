#!/bin/sh
set -eu

# Numeric IP/CIDR entries only. nginx validates address/range syntax at startup.
# An empty list trusts no external peer; never infer trust from private ranges.
target="${ATLAS_TRUSTED_PROXIES_FILE:-/etc/nginx/atlas-trusted-proxies.conf}"
: > "$target"
old_ifs="$IFS"
IFS=,
set -f
for proxy in ${ATLAS_TRUSTED_PROXIES:-}; do
    case "$proxy" in
        ''|*[!0-9a-fA-F.:/]*)
            echo "ATLAS_TRUSTED_PROXIES must contain comma-separated IP addresses or CIDRs." >&2
            exit 1
            ;;
    esac
    printf '%s 1;\n' "$proxy" >> "$target"
done
IFS="$old_ifs"
