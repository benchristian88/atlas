# Asset icons

Edit an Asset and enter an **Asset icon URL** to give it recognizable artwork.
Use a publicly reachable **HTTPS PNG, JPEG or WebP** URL on the standard HTTPS
port. Save the Asset, display it, then reload after a few seconds to see its
cached icon. Existing Assets with icon URLs work automatically without edits.

Atlas securely retrieves the image once and keeps a local copy. Normal use of
the Asset list, detail page, Knowledge Graph and dashboard then loads that copy
from Atlas, without contacting the original icon provider.

- Changing the source URL retrieves a new copy. Until it succeeds, Atlas uses
  the fallback instead of displaying the old image as the new one.
- Clearing the URL uses the Asset Type default. Without a working type default,
  Atlas uses its generic Asset icon.
- An unchanged successful URL is never refreshed automatically. To replace an
  image hosted at the same URL, configure a new versioned URL.
- Failed retrievals do not prevent saving or using an Asset. Another display
  after five minutes can retry. There is no refresh schedule or polling.

Private/local addresses (including homelab hosts and cloud metadata addresses),
URLs containing credentials, unsafe redirects, SVG and unsupported image
formats are blocked. Sources are limited to 2 MiB, 2048 pixels per side and four
million pixels total. Atlas stores a static, metadata-free PNG up to 256×256.
Animated WebP/PNG sources use their first frame.

Asset Type defaults remain administrator-configured HTTPS images loaded directly
by the browser. Their behavior is unchanged. Asset-specific icons require the
same viewing permissions as their Asset, including Customer and Site scope.

For administrators: the cache persists in the existing PostgreSQL database and
its Docker volume. Apply normal migrations during upgrade; no new volume or
worker configuration is required. API logs contain the Asset ID and a safe
retrieval failure reason. See the [technical design](../architecture/asset-icon-cache.md)
for limits, recovery behavior and deployment details.
