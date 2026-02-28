# AccomFinder — KL Rental Scraper

A Flask web app that scrapes **7 Malaysian property portals** in parallel and ranks apartment/condo rental listings by distance from a target location.

## Features

- Paste a Google Maps URL → extracts coordinates → sorts listings by distance
- Searches 7 sites simultaneously using `ThreadPoolExecutor`
- Geocodes listing addresses via Nominatim (cached, rate-limited)
- Interactive Leaflet map with colour-coded markers per source
- Filter by site, sort by distance or price

## Supported Sites

| Site | Method | Notes |
|------|--------|-------|
| [PropertyGuru](https://www.propertyguru.com.my) | cloudscraper + HTML | Cloudflare bypass |
| [iProperty](https://www.iproperty.com.my) | cloudscraper + `__NEXT_DATA__` | Next.js JSON |
| [EdgeProp](https://www.edgeprop.my) | requests + `__NEXT_DATA__` | Native lat/lng in data |
| [DotProperty](https://www.dotproperty.com.my) | requests + HTML | Standard HTML |
| [Rentola](https://www.rentola.com) | requests + HTML | Standard HTML |
| [Mudah](https://www.mudah.my) | cloudscraper + JSON/HTML | Classifieds site |
| [StarProperty](https://www.starproperty.my) | cloudscraper + JSON/HTML | Verified listings |

## Stack

- **Backend**: Python 3.11+, Flask, `cloudscraper`, `beautifulsoup4`, `geopy`
- **Frontend**: Tailwind CSS (CDN), Leaflet.js, vanilla JS
- No database — all results are fetched live per request

## Setup

```bash
# Clone
git clone https://github.com/Shinorkon/accomodation-scraper.git
cd accomodation-scraper

# Install dependencies
pip install -r requirements.txt

# Run
python app.py
# → http://localhost:5001
```

## Usage

1. Open `http://localhost:5001`
2. Paste a Google Maps link (short `maps.app.goo.gl` or full URL)
3. Select number of bedrooms
4. Toggle which sites to search
5. Click **Search** — results appear sorted by distance within ~30–60 s

## Project Structure

```
accommodation_scraper/
├── app.py              # Flask app + /search endpoint
├── location.py         # Google Maps URL parser, geocoder, haversine
├── requirements.txt
├── scrapers/
│   ├── __init__.py     # Parallel scraper runner
│   ├── base.py         # Listing dataclass + shared HEADERS
│   ├── propertyguru.py
│   ├── iproperty.py
│   ├── edgeprop.py
│   ├── dotproperty.py
│   ├── rentola.py
│   ├── mudah.py
│   └── starproperty.py
└── templates/
    └── index.html      # Single-page UI
```

## Notes

- Scrapers use CSS selectors / JSON paths that may break if sites update their markup — check logs if a source returns 0 results
- Nominatim geocoding is capped at 40 unique calls per search to keep response times reasonable
- No API keys required
