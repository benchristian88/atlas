# Reverse-proxy examples

These examples implement one routing rule: preserve `/api/*` and send it to
FastAPI; send every other path to Next.js. They are examples, not Atlas runtime
dependencies. TLS can be terminated by any operator-selected infrastructure.

## Nginx

When Nginx shares the Compose network, the confirmed service names are `api`
and `web`:

```nginx
location /api/ {
    proxy_pass http://api:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location / {
    proxy_pass http://web:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

The API `proxy_pass` intentionally has no trailing slash after port 8000, so
Nginx preserves `/api/...`. `proxy_pass http://api:8000/;` has different URI
replacement behavior and can strip the matched prefix.

## Nginx Proxy Manager

Nginx Proxy Manager is optional. Configure one proxy host for the
operator-selected Atlas hostname pointing to the web service on port 3000, then
add a custom `/api/` location pointing to the API service on port 8000. Preserve
the `/api/` path unchanged. A second public API hostname is not required.

## Caddy

```caddyfile
<ATLAS_HOST> {
    handle /api/* {
        reverse_proxy api:8000
    }
    handle {
        reverse_proxy web:3000
    }
}
```

Use `handle`, not `handle_path`; `handle_path` strips the matched prefix.

## Traefik

Create a higher-priority router with `PathPrefix(`/api`)` targeting the API
service on port 8000, plus a lower-priority catch-all router targeting the web
service on port 3000. Do not attach a `StripPrefix` middleware to the API router.

## Optional tunnels and edge services

Cloudflare and similar services are optional. When used, point the tunnel at the
single reverse-proxy entry point; that proxy continues to route `/api/*` and
`/*`. Atlas contains no provider-specific libraries, headers, environment
variables, or hostname assumptions.
