# tests/test_listings.py
"""Unit tests for the real estate listings feature (no live API)."""

from scripts.fetch_listings import categorize, normalize_listing
from scripts.listings_app import filter_listings
from scripts.estimate import add_estimates


# --- RentCast -> normalized mapping & category bucketing ---

def test_categorize_buckets():
    assert categorize('Land') == 'land'
    assert categorize('Condo') == 'condo'
    assert categorize('Apartment') == 'apartment'
    assert categorize('Single Family') == 'residential'
    assert categorize('Townhouse') == 'residential'
    assert categorize('Multi-Family') == 'residential'
    assert categorize('Manufactured') == 'residential'


def test_categorize_unknown_is_other():
    assert categorize('Commercial') == 'other'
    assert categorize(None) == 'other'


def test_normalize_listing_maps_fields():
    raw = {
        'id': 'abc-123',
        'formattedAddress': '1 Main St, Burlington, VT 05401',
        'city': 'Burlington',
        'state': 'VT',
        'zipCode': '05401',
        'latitude': 44.47,
        'longitude': -73.21,
        'propertyType': 'Single Family',
        'price': 450000,
        'bedrooms': 3,
        'bathrooms': 2,
        'squareFootage': 1800,
        'lotSize': 6000,
        'yearBuilt': 1995,
        'daysOnMarket': 12,
        'listedDate': '2026-06-01',
    }
    n = normalize_listing(raw)
    assert n['id'] == 'abc-123'
    assert n['zip'] == '05401'
    assert n['category'] == 'residential'
    assert n['price'] == 450000
    assert n['address'].startswith('1 Main St')
    assert n['url'].startswith('https://www.google.com/search?q=')


def test_normalize_listing_handles_missing_fields():
    n = normalize_listing({'id': 'x'})
    assert n['id'] == 'x'
    assert n['address'] == ''
    assert n['url'] == ''
    assert n['category'] == 'other'


# --- filter_listings ---

SAMPLE = [
    {'id': '1', 'price': 200000, 'zip': '10001', 'bedrooms': 2, 'bathrooms': 1, 'category': 'condo'},
    {'id': '2', 'price': 500000, 'zip': '10001', 'bedrooms': 4, 'bathrooms': 3, 'category': 'residential'},
    {'id': '3', 'price': 800000, 'zip': '05401', 'bedrooms': 5, 'bathrooms': 4, 'category': 'residential'},
    {'id': '4', 'price': None,   'zip': '05401', 'bedrooms': None, 'bathrooms': None, 'category': 'land'},
]


def test_filter_no_filters_returns_all():
    assert len(filter_listings(SAMPLE)) == 4


def test_filter_price_range_excludes_null_price():
    out = filter_listings(SAMPLE, price_min=300000, price_max=600000)
    assert [L['id'] for L in out] == ['2']


def test_filter_zip():
    out = filter_listings(SAMPLE, zip='05401')
    assert {L['id'] for L in out} == {'3', '4'}


def test_filter_beds_baths_min_skips_missing():
    out = filter_listings(SAMPLE, beds_min=4, baths_min=3)
    assert {L['id'] for L in out} == {'2', '3'}


def test_filter_categories():
    out = filter_listings(SAMPLE, categories={'residential', 'land'})
    assert {L['id'] for L in out} == {'2', '3', '4'}


def test_filter_combined():
    out = filter_listings(SAMPLE, price_max=600000, zip='10001', categories={'condo'})
    assert [L['id'] for L in out] == ['1']


# --- add_estimates (comparable $/sqft value estimate) ---

def _residential(zip_, price, sqft, id_='x'):
    return {'id': id_, 'state': 'VT', 'zip': zip_, 'category': 'residential',
            'price': price, 'squareFootage': sqft}


def test_estimate_uses_zip_category_median_ppsf():
    # Five comps in 05401 residential at exactly $200/sqft -> median ppsf 200.
    listings = [_residential('05401', 200 * sf, sf, str(i))
                for i, sf in enumerate([1000, 1200, 1500, 1800, 2000])]
    # A target home with 1000 sqft should estimate to 200 * 1000 = 200,000.
    target = _residential('05401', 999_999, 1000, 'target')
    listings.append(target)
    add_estimates(listings, min_comps=5)
    assert target['estimate'] == 200_000
    assert target['estimate_ppsf'] == 200


def test_estimate_none_without_sqft():
    listings = [_residential('05401', 300000, 1500, str(i)) for i in range(6)]
    land = {'id': 'land', 'state': 'VT', 'zip': '05401', 'category': 'land',
            'price': 90000, 'squareFootage': None}
    listings.append(land)
    add_estimates(listings, min_comps=5)
    assert land['estimate'] is None
    assert land['estimate_ppsf'] is None


def test_estimate_falls_back_to_broader_group():
    # Only 2 comps in the ZIP (below min_comps) but enough statewide -> uses
    # the state median rather than leaving the estimate empty.
    listings = [_residential('05401', 200 * sf, sf, f'a{i}')
                for i, sf in enumerate([1000, 1200])]
    listings += [_residential('05602', 200 * sf, sf, f'b{i}')
                 for i, sf in enumerate([1000, 1100, 1300, 1400])]
    target = _residential('05401', 500000, 1000, 'target')
    listings.append(target)
    add_estimates(listings, min_comps=5)
    assert target['estimate'] == 200_000  # state median ppsf 200 * 1000 sqft
