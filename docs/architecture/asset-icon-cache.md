# Secure locally cached Asset icons

The optional Asset icon URL (`Asset.icon_url` in the API) is an external source.
Atlas retrieves a validated local copy when an authorized user first displays
that Asset icon. Existing Assets need no edits. The list, detail header,
Knowledge Graph, dashboard Environment Overview, topology cards, graph inspector
and Service Asset relationship cards use the same `AssetIcon` component.

Resolution is **cached Asset image → Asset Type default → generic Atlas icon**.
While loading, the fixed icon box retains a generic placeholder. Failed or
missing local images fall back without displaying a broken-image glyph. Icons
preserve aspect ratio and use existing light/dark surface tokens.

## Cache lifetime and storage

`asset_icon_cache` stores at most one 512 KiB PNG per Asset, plus source/content
SHA-256 hashes and attempt state. PostgreSQL is the existing persistent store;
Docker's `postgres_data` volume also persists this cache. No filesystem paths,
new volumes, media service, Redis queues or worker are needed. Cache writes are
separate from Asset knowledge, assertions, history and `updated_at`.

Migration `20260912_0018` adds only this table, with an Asset foreign key and
cascade cleanup. Run the normal `alembic upgrade head` before starting the new
API. No data backfill/network activity occurs during migration. Cache bytes are
covered by ordinary database access controls and backups. Downgrade removes only
the disposable cache table.

A successful image is reused indefinitely while the source URL is unchanged.
There is no TTL refresh. Changing the URL changes the icon request version;
the previous bytes remain stored until a validated replacement can be committed
atomically. They are **not served for the new source**, even if its retrieval
fails. Clearing the URL deletes its cache; deleting the Asset cascades cleanup.
An archived Asset remains eligible wherever the user can legitimately view it.

The authenticated icon endpoint makes a database claim before attaching a
FastAPI background task. The response is sent before third-party retrieval.
One persisted attempt token/lease per Asset suppresses simultaneous requests
across processes. Work is capped at four concurrent fetches per API process.
Failed, interrupted or capacity-limited attempts can retry on a subsequent icon
request after five minutes. Changing the URL permits a new attempt immediately.
A successful cache is never refreshed merely because that interval passed.
A late task checks the current source and token before publishing; edits and
deletions cannot restore obsolete cache data. No durable job queue is implied.
After a first fetch, reload the page to see the cached image; there is no polling.

## Retrieval boundary

Only public HTTPS URLs on port 443 are fetched. Credentials in URLs, localhost,
private, loopback, link-local, metadata, multicast, unspecified, reserved and
special-use addresses (including IPv6 transition ranges) are rejected.
All DNS answers are validated; mixed public/private answers fail closed.
The connector uses those numeric addresses without a second hostname lookup,
keeps TLS hostname/certificate verification, and checks the actual TLS peer
before allowing HTTP to use the transport. Each of at most three redirects
receives the same URL/DNS/peer validation.

The dedicated client forwards no Atlas headers/cookies, ignores environment
proxy/netrc credentials, has no cookie jar, and uses an Atlas User-Agent.
Connect and read timeouts are two seconds; per-response total is eight seconds,
and the entire redirect/download sequence has a ten-second budget. Downloads
are streamed with a 2 MiB ceiling, including when Content-Length is absent.
Encoded HTTP bodies are rejected rather than decompressed without bounds.

Actual PNG, JPEG and WebP bytes are decoded with Pillow, regardless of claimed
Content-Type. SVG, HTML, XML, GIF and other formats are rejected. Images must be
at most 2048 pixels per side and four million pixels total. Output is a static,
metadata-free PNG contained within 256×256 pixels. Cache responses verify the
stored content hash; missing or damaged bytes trigger the same bounded lazy
recovery path. Keep the pinned image/network dependencies patched.

Implementation references: [aiohttp client controls](https://docs.aiohttp.org/en/stable/client_reference.html)
and [Pillow image security](https://pillow.readthedocs.io/en/stable/handbook/security.html).
The connector peer check uses aiohttp's `_wrap_create_connection` extension;
its regression test must pass when upgrading aiohttp.

## Serving and compatibility

`GET /api/assets/{asset_id}/icon` requires authentication, `assets.view` and the
same Customer/Site object scope as Asset detail. Missing and inaccessible Assets
have identical 404 responses. Authorization runs before ETag handling; guessing
an ID or presenting a cached ETag cannot bypass it. Valid responses are PNG with
`nosniff`, `private, no-cache` and an ETag, allowing browser byte reuse only after
access revalidation. Unavailable images return an uncacheable 204; the component
advances to its normal fallback. API routes and source URL fields are preserved.

Asset DTOs, Asset graph nodes and Service Asset dependency DTOs add
`cached_icon_url` and `default_icon_url`. The former is a local lookup URL, **not
a promise that retrieval has completed**. `resolved_icon_url` now points at that
lookup when a source is configured, or the type default. The web component never
uses the external Asset source as an image src. Normal graph/list serialization
performs no downloads or extra cache queries. The existing API-base setting is
honoured for split-origin development; production normally routes `/api` through
the same origin.

The CSP is unchanged: `img-src 'self' https: data:`. Asset-specific images use
Atlas only. Existing administrator-configured Asset Type defaults still load
HTTPS images directly, and local generic SVG data images remain supported.
This feature does not introduce remote SVG sanitization or a media library.
Logs contain Asset IDs and fixed failure reasons, never source URLs, query
strings, credentials, response bodies or exception text.
