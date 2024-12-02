import os
from dotenv import load_dotenv
from typing import Dict, Any, List

load_dotenv()

TICKET_MASTER_KEY = os.getenv("TICKET_MASTER_KEY")


def map_to_schema(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Maps the API response to the schema.org Event structure, handling multiple offers and venues."""
    api_response = api_response.get('_embedded')
    events = api_response.get('events', [])
    
    if not events:
        raise ValueError("No event data found in the response.")
    
    mapped_events = []

    for event_data in events:
        mapped_event = {
            "@context": "https://schema.org",
            "@type": "Event",
            "name": event_data.get("name"),
            "description": event_data.get("classifications")[0].get("segment").get("name") if event_data.get("classifications") else None,
            "startDate": event_data.get("dates", {}).get("start", {}).get("dateTime"),
            "offers": [],
            "location": []
        }

        price_ranges = event_data.get("priceRanges", [])
        for price_range in price_ranges:
            mapped_event["offers"].append({
                "@type": "Offer",
                "url": event_data.get("url"),
                "priceCurrency": price_range.get("currency"),
                "price": f"{price_range.get('min')} - {price_range.get('max')}",
            })

        venues = event_data.get('_embedded', {}).get("venues", [])
        for venue in venues:
            mapped_event["location"].append({
                "@type": "PostalAddress",
                "streetAddress": venue.get("address", {}).get("line1"),
                "postalCode": venue.get("postalCode"),
                "addressRegion": venue.get("state", {}).get("name"),
                "addressLocality": venue.get("city", {}).get("name"),
            })

        mapped_events.append(mapped_event)
    
    return mapped_events


import json

with open("example.json", "r") as f:
    api_response = json.load(f)

mapped_events = map_to_schema(api_response)

print(json.dumps(mapped_events, indent=4))
