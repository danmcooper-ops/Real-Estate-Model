# scripts/build_static_site.py
"""Build the static GitHub Pages site from the local listings cache.

GitHub Pages can't run the Flask app, so this produces a self-contained site
(served from the repo's docs/ folder) that does all filtering and Excel export
in the browser:

    docs/index.html    - the static viewer (committed source, not generated here)
    docs/listings.json - data dumped from output/listings_cache.json

Run scripts/fetch_listings.py first to populate the cache, then this, then
commit + push. Pages is configured to serve from main /docs.

    python scripts/build_static_site.py
"""

import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.config import OUTPUT_DIR, PROJECT_ROOT

CACHE = os.path.join(OUTPUT_DIR, 'listings_cache.json')
DOCS_DIR = os.path.join(PROJECT_ROOT, 'docs')


def main():
    if not os.path.exists(CACHE):
        print(f"ERROR: {CACHE} not found. Run scripts/fetch_listings.py first.",
              file=sys.stderr)
        sys.exit(1)

    with open(CACHE) as f:
        data = json.load(f)

    os.makedirs(DOCS_DIR, exist_ok=True)
    out = os.path.join(DOCS_DIR, 'listings.json')
    with open(out, 'w') as f:
        json.dump(data, f, separators=(',', ':'))  # compact keeps Pages payload small

    size_mb = os.path.getsize(out) / 1e6
    print(f"Wrote {data.get('count', len(data.get('listings', [])))} listings "
          f"to {out} ({size_mb:.1f} MB)")

    index = os.path.join(DOCS_DIR, 'index.html')
    if os.path.exists(index):
        print(f"index.html present at {index}")
    else:
        print(f"WARNING: {index} missing — the static viewer source should live there.",
              file=sys.stderr)

    print("\nNext: commit + push. GitHub Pages serves from main /docs.")


if __name__ == '__main__':
    main()
