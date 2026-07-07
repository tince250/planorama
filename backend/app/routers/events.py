from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.models.event import EventOut, EventSearchResponse
from app.queries.search import build_candidate_query, fetch_events_by_iri, search_events
from app.rdf.iri import event_iri, venue_iri
from app.rdf.sparql_client import sparql_client

router = APIRouter()


@router.get("/events", response_model=EventSearchResponse)
def list_events(
    q: str | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float | None = None,
    accessible_only: bool = False,
    location: str | None = None,
    limit: int = Query(default=20, le=100, ge=1),
    offset: int = Query(default=0, ge=0),
):
    events, total = search_events(
        q=q,
        category=category,
        date_from=date_from,
        date_to=date_to,
        price_min=price_min,
        price_max=price_max,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        accessible_only=accessible_only,
        location=location,
        limit=limit,
        offset=offset,
    )
    return EventSearchResponse(results=events, total=total)


@router.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: str):
    events = fetch_events_by_iri([str(event_iri(event_id))])
    if not events:
        raise HTTPException(status_code=404, detail="Event not found")
    return events[0]


@router.get("/venues/{venue_id}/events", response_model=EventSearchResponse)
def get_venue_events(venue_id: str, exclude_event_id: str | None = None):
    exclude_iri = str(event_iri(exclude_event_id)) if exclude_event_id else None
    candidate_query = build_candidate_query(
        venue_iri=str(venue_iri(venue_id)), exclude_event_iri=exclude_iri
    )
    event_iris = [b["event"]["value"] for b in sparql_client.query(candidate_query)]
    events = fetch_events_by_iri(event_iris)
    events.sort(key=lambda e: (e.start_date is None, e.start_date))
    return EventSearchResponse(results=events, total=len(events))
