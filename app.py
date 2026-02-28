import os
import sys
import logging
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
    body = request.get_json(force=True)
    maps_url = (body.get("maps_url") or "").strip()
    bedrooms = int(body.get("bedrooms") or 1)
    enabled_sites = body.get("sites") or None  # None = all sites

    target_lat = None
    target_lng = None
    location_name = None

    if maps_url:
        from location import parse_google_maps_url
        coords = parse_google_maps_url(maps_url)
        if coords:
            target_lat, target_lng = coords
            location_name = f"{target_lat:.5f}, {target_lng:.5f}"
            app.logger.info(f"Target coords: {target_lat}, {target_lng}")
        else:
            app.logger.warning(f"Could not parse coordinates from: {maps_url}")

    from scrapers import run_all_scrapers
    listings, errors = run_all_scrapers(
        bedrooms=bedrooms,
        target_lat=target_lat,
        target_lng=target_lng,
        enabled=enabled_sites,
    )

    return jsonify({
        "listings": listings,
        "errors": errors,
        "target": {
            "lat": target_lat,
            "lng": target_lng,
            "name": location_name,
        },
        "count": len(listings),
    })


if __name__ == "__main__":
    app.run(debug=True, port=5001)
