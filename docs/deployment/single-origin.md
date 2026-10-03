# Single-origin deployment

Atlas's standard browser routing contract, at one HTTP or HTTPS origin, is:

```text
https://<ATLAS_HOST>/*      -> Next.js web service, port 3000
https://<ATLAS_HOST>/api/* -> FastAPI API service, port 8000
```

In Docker Compose the included nginx gateway implements this routing and
preserves the `/api` prefix. It is the only published service; its host endpoint
is `http://<ATLAS_BIND_ADDRESS>:<ATLAS_PORT>` (default port 3000). Internal web
and API ports are not browser endpoints. An external HTTPS proxy forwards all
paths to that one gateway upstream. Native/systemd has no included gateway and
still needs an operator-configured host proxy with both internal path routes. Atlas does not require or
read a public-hostname setting. DNS, TLS termination, and proxy selection belong
to the operator, and the same Atlas images can move between hostnames without a
hostname-only rebuild.

The web client uses `/api` when `NEXT_PUBLIC_API_URL` is blank or absent. The
reference environment sets it explicitly for clarity:

```dotenv
NEXT_PUBLIC_API_URL=/api
AUTH_COOKIE_SECURE=auto
CORS_ORIGINS=
```

Same-origin browser requests include the existing HttpOnly session cookie and
do not depend on CORS. Keep `CORS_ORIGINS` blank unless the browser deliberately
loads Next.js and FastAPI from different origins. Atlas retains cookie path `/`,
`HttpOnly`, `SameSite=Lax`, and the configured `Secure` behavior.

The canonical operational endpoints are:

```text
GET /api/health
GET /api/docs
GET /api/openapi.json
GET /api/redoc
```

No application or health route remains available without `/api`. Mixed-version
frontend/API deployments are therefore unsupported and must be deployed as a
coordinated release.

## Direct-port development

A reverse proxy is not required for development. Configure an absolute browser
API base and the exact web origin:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api
CORS_ORIGINS=http://localhost:3000
AUTH_COOKIE_SECURE=false
```

Then access Next.js on port 3000 and FastAPI directly on port 8000. An absolute
`NEXT_PUBLIC_API_URL` is compiled into a production browser bundle when used at
build time, so reserve it for an intentionally split deployment and rebuild the
web image after changing it. The reference web container uses Next.js standalone
production output (`next build` followed by `node server.js`); HMR and
`/_next/webpack-hmr` are not part of the deployed stack.

## Verification

After routing is configured, verify through the public entry point:

```bash
curl -fsS https://<ATLAS_HOST>/api/health
```

The expected response is `{"status":"ok"}`. Then verify login, current-user
validation, logout, customer/site context, inventory, administration, and
topology from the same browser origin.

## Session-check troubleshooting

An unauthenticated `GET /api/auth/me` returning `401 Authentication required`
is normal: the protected shell transitions to logged out and opens `/login`.
A `404`, `5xx`, invalid response, or network failure instead indicates an API,
routing, or service problem. Atlas shows a retryable session-validation error
for those failures rather than hiding them behind a login redirect.

Docker host port 3000 now reaches the gateway, so relative `/api/*` requests
work there alongside setup/login/dashboard. The internal Next.js server does
not itself proxy `/api`: optional Compose development access publishes it on
loopback port 3001 and API on 8000, requiring an absolute API base and exact
`http://localhost:3001` CORS origin. Host-run developers retain 3000/8000 as
before. Native web access still requires its host proxy for same-origin use.

## Scheme and proxy trust

Docker generates `AUTH_COOKIE_SECURE=auto`. Direct HTTP issues non-Secure
setup/session cookies; HTTPS through a configured trusted external proxy issues
Secure cookies. Explicit `true` forces Secure and explicit `false` omits it.
HttpOnly, SameSite=Lax, paths, Origin checks and token validation are unchanged.
The cookie helper uses the ASGI request scheme and never inspects raw headers.

`ATLAS_TRUSTED_PROXIES` is empty by default. Set the gateway allowlist to the
actual external proxy source IP or a narrow CIDR (comma-separated, no spaces).
Recreate the gateway after editing it. Only a matching socket peer may supply an
exact `http` or `https` in `X-Forwarded-Proto`; malformed/chained values and all
untrusted forwarding indications use the gateway's own scheme. The gateway
replaces Host-related forwarding and untrusted client IP chains. A trusted
external proxy must overwrite protocol and client forwarding headers rather
than trusting values sent by the browser. Do not trust an entire LAN merely
because its addresses are private. Use the proxy peer seen by the gateway,
which may reflect host/container NAT.

Uvicorn in production Docker accepts the sanitized headers from the trusted
Compose network (`FORWARDED_ALLOW_IPS=*`), with API port 8000 unpublished. This
configuration depends on keeping that network private: do not add a public API
port or connect untrusted containers. Uvicorn's existing loopback-only trust
remains the native/development default; the optional development override
explicitly restores it. No public URL, proxy vendor or DNS setting is required.
CORS is unrelated to same-origin protocol forwarding and remains blank.

The boundary follows [Uvicorn's proxy settings](https://www.uvicorn.org/settings/)
and [nginx proxy header/URI behavior](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).
See [H1.1 acceptance](../testing/h1-docker-ingress.md) for direct HTTP and trusted
external HTTPS regression and real Linux validation.
