# Single-origin deployment

Atlas's standard browser routing contract is:

```text
https://<ATLAS_HOST>/*      -> Next.js web service, port 3000
https://<ATLAS_HOST>/api/* -> FastAPI API service, port 8000
```

The reverse proxy must preserve the `/api` prefix. Atlas does not require or
read a public-hostname setting. DNS, TLS termination, and proxy selection belong
to the operator, and the same Atlas images can move between hostnames without a
hostname-only rebuild.

The web client uses `/api` when `NEXT_PUBLIC_API_URL` is blank or absent. The
reference environment sets it explicitly for clarity:

```dotenv
NEXT_PUBLIC_API_URL=/api
AUTH_COOKIE_SECURE=true
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

Direct access to the web container on port 3000 does not proxy relative
`/api/*` requests; with the default `/api` base they correctly return a Next.js
404. Use the single-origin reverse-proxy entry point for production, or configure
the absolute API base and exact CORS origin described above for split-port
development.

Atlas does not trust arbitrary forwarded headers in application code. Configure
the selected proxy to replace standard forwarding headers, restrict direct
access according to your network design, and use the ASGI server's supported
trusted-proxy configuration only when your deployment genuinely needs it.
