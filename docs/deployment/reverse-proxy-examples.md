# Reverse-proxy examples

Docker Compose and native/systemd include Atlas nginx ingress. External proxies need **one
upstream**: `http://<ATLAS_BIND_ADDRESS>:<ATLAS_PORT>`. The gateway preserves
`/api/*` to FastAPI and routes everything else to Next.js. No separate public
API port, custom `/api` location, public URL setting or CORS entry is required.
These proxy products are optional operator choices, not Atlas dependencies.

Set `ATLAS_TRUSTED_PROXIES` in the protected Atlas `.env` to the external proxy's
actual socket source IP (or a narrow CIDR), comma-separated without spaces.
Recreate the gateway after changing it:

```bash
docker compose --env-file .env -f infra/docker/docker-compose.yml up -d gateway
```

The list starts empty. Direct clients cannot assert HTTPS or arbitrary client
IPs. The trusted external proxy must replace incoming protocol and client
forwarding headers with verified values. Keep `AUTH_COOKIE_SECURE=auto` and
`CORS_ORIGINS=` for normal HTTP/HTTPS same-origin access. An explicit `true`
policy requires HTTPS. See [scheme and proxy trust](single-origin.md#scheme-and-proxy-trust).

## Nginx (external Docker upstream)

Inside the operator's TLS server block (replace the illustrative LAN address):

```nginx
location / {
    proxy_pass http://192.168.3.195:3000;
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

The upstream has no URI suffix; all paths and query strings arrive unchanged.
TLS certificate/listener configuration remains operator-managed.

## Nginx Proxy Manager

Configure one Proxy Host for the chosen hostname, forwarding scheme **http**,
Forward Hostname/IP equal to the Atlas bind address, Forward Port equal to
`ATLAS_PORT` (normally 3000). Configure TLS in NPM as usual. Leave Custom
Locations empty: **no `/api` custom location**. Add NPM's actual source IP to
Atlas's `ATLAS_TRUSTED_PROXIES`. Confirm NPM replaces `X-Forwarded-Proto` with its
verified browser scheme and sends the original Host. Verify Secure cookies
through HTTPS. Do not add the domain to CORS.

## Caddy

```caddyfile
atlas.example.com {
    reverse_proxy 192.168.3.195:3000
}
```

The hostname and address are examples. Caddy terminates TLS and forwards all
paths to the gateway. Add Caddy's source IP to Atlas's trust list.

## Traefik

Use one hostname router and one HTTP service targeting the Atlas gateway bind
address and port. No higher-priority API router or StripPrefix middleware is
needed. Configure TLS normally and allowlist Traefik's source IP in Atlas.

## Optional tunnels and edge services

Point a tunnel at the gateway or the chosen external reverse proxy, with all
paths intact. If HTTPS terminates before an HTTP hop, explicitly trust only the
peer supplying a verified original scheme. No provider-specific runtime,
headers or hostname assumptions are added to Atlas.

## Native/systemd

Use the same single upstream and optional TLS proxy examples above. Bundled
nginx owns the public Atlas port, routes `/api` unchanged to loopback 8000 and
web paths to loopback 3001. The installer manages a dedicated site and nginx
ordering drop-in, validates with `nginx -t`, and preserves unrelated sites.
Do not point an old TLS proxy directly at the private Next.js listener.

Set `ATLAS_TRUSTED_PROXIES` in `/etc/atlas/atlas.env` to the external TLS proxy's
actual source IP or narrow CIDR, then apply it:

```bash
sudo python3 /opt/atlas/infra/install/native_ingress.py
```

Fresh native installations use `AUTH_COOKIE_SECURE=auto`. Upgrades retain the
existing file and explicit policy; deliberately use `auto` for direct HTTP and
trusted HTTPS, or retain `true` for HTTPS-only browser access. Restart the API
after editing cookie policy. Native Uvicorn trusts only loopback, and nginx
accepts forwarded scheme/client headers only from the explicit allowlist. No
proxy is automatically trusted, including another process on the host.

For H3 restore, every external proxy must allow the same 2 GiB upload bound as
bundled ingress and permit streaming; nginx's default 1 MiB causes HTTP 413.
