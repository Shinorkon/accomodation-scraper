from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Listing:
    title: str
    price: str              # display string e.g. "RM 1,800/mo"
    price_numeric: float    # sortable float e.g. 1800.0
    location: str           # area name e.g. "Bukit Jalil, Kuala Lumpur"
    bedrooms: int
    image_url: str
    listing_url: str
    source: str             # "PropertyGuru" | "DotProperty" | "Rentola" | "iProperty" | "EdgeProp" | "Mudah" | "StarProperty"
    lat: Optional[float] = None
    lng: Optional[float] = None
    distance_km: Optional[float] = None

    def to_dict(self):
        return {
            "title": self.title,
            "price": self.price,
            "price_numeric": self.price_numeric,
            "location": self.location,
            "bedrooms": self.bedrooms,
            "image_url": self.image_url,
            "listing_url": self.listing_url,
            "source": self.source,
            "lat": self.lat,
            "lng": self.lng,
            "distance_km": round(self.distance_km, 2) if self.distance_km is not None else None,
        }


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}
