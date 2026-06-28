# data/rentcast_client.py
"""RentCast data client — active for-sale real estate listings.

Requires RENTCAST_API_KEY environment variable (or pass api_key to constructor).

Mirrors the conventions of the other data clients in this package
(FMPClient, FinnhubSupplyClient): class-based, urllib-only (no requests),
``api_key`` falls back to the environment, request throttling, in-memory
cache, and graceful degradation (returns ``[]`` on network/plan errors).

API reference: https://developers.rentcast.io/reference/
  Endpoint : GET https://api.rentcast.io/v1/listings/sale
  Auth     : X-Api-Key request header
  Paging   : ``limit`` (max 500) + ``offset``; a short page means the end.

RentCast is residential-focused. Its ``propertyType`` values are:
  Single Family, Condo, Townhouse, Manufactured, Multi-Family, Apartment, Land.
There is NO commercial property type — commercial listings need a separate
source (see plan: a future data/crexi_client.py feeding the same schema).
"""

import os
import ssl
import time
import json
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

_BASE = 'https://api.rentcast.io/v1'
_PAGE_LIMIT = 500  # RentCast hard cap per request

# Some Python builds (e.g. the python.org macOS framework build) ship without a
# usable system CA bundle, so HTTPS verification fails with
# CERTIFICATE_VERIFY_FAILED. Prefer certifi's bundle when available; otherwise
# fall back to urllib's default context.
try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = None


class RentCastClient:
    def __init__(self, api_key=None, request_delay=0.5):
        self._api_key = api_key or os.environ.get('RENTCAST_API_KEY', '')
        self._request_delay = request_delay
        self._last_request_time = 0
        self._cache = {}
        # Set by _get on auth/billing/plan errors so callers (e.g. the fetch
        # CLI) can surface an actionable message instead of "0 listings".
        self.last_error = None

    @property
    def available(self):
        """False when no API key is configured — callers can degrade cleanly."""
        return bool(self._api_key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            time.sleep(self._request_delay - elapsed)
        self._last_request_time = time.time()

    def _get(self, path, params=None, _retried=False):
        """GET from the RentCast API. Returns parsed JSON, or None on error.

        429s are retried once after a pause; auth/plan errors (401/402/403)
        and 404s degrade to None rather than raising.
        """
        self._throttle()
        url = _BASE + path
        if params:
            url += '?' + urlencode(params)
        req = Request(url, headers={
            'Accept': 'application/json',
            'X-Api-Key': self._api_key,
        })
        try:
            with urlopen(req, timeout=20, context=_SSL_CONTEXT) as resp:
                return json.loads(resp.read().decode())
        except HTTPError as e:
            if e.code in (401, 402, 403):
                # Bad key, inactive subscription, or plan limit — record why so
                # the caller can report it (404 is just "no results", skipped).
                try:
                    body = json.loads(e.read().decode())
                    msg = body.get('message') or body.get('error') or e.reason
                except Exception:
                    msg = e.reason
                self.last_error = f"HTTP {e.code}: {msg}"
                return None
            if e.code == 404:
                return None  # No matching listings — not an error
            if e.code == 429 and not _retried:
                time.sleep(5)
                return self._get(path, params=params, _retried=True)
            self.last_error = f"HTTP {e.code}: {e.reason}"
            return None
        except (URLError, ValueError) as e:
            self.last_error = str(e)
            return None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def fetch_sale_listings(self, state, *, zip_code=None, city=None,
                            property_type=None, max_records=None):
        """Fetch active for-sale listings for a state (raw RentCast dicts).

        Paginates with ``offset`` until a short page or ``max_records`` is
        reached, then dedupes by listing ``id``. Optional ``zip_code`` / ``city``
        / ``property_type`` narrow the query server-side. Returns a list (never
        None) so ingestion code can concatenate results safely.
        """
        cache_key = ('sale', state, zip_code, city, property_type, max_records)
        if cache_key in self._cache:
            return self._cache[cache_key]

        seen = set()
        out = []
        offset = 0
        while True:
            params = {
                'state': state,
                'status': 'Active',
                'limit': _PAGE_LIMIT,
                'offset': offset,
            }
            if zip_code:
                params['zipCode'] = zip_code
            if city:
                params['city'] = city
            if property_type:
                params['propertyType'] = property_type

            page = self._get('/listings/sale', params)
            if not page:  # None (error) or empty list — nothing more to read
                break

            for rec in page:
                rid = rec.get('id')
                if rid in seen:
                    continue
                seen.add(rid)
                out.append(rec)
                if max_records and len(out) >= max_records:
                    self._cache[cache_key] = out
                    return out

            if len(page) < _PAGE_LIMIT:
                break  # Last page
            offset += _PAGE_LIMIT

        self._cache[cache_key] = out
        return out
