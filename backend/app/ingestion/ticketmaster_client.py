import time
from typing import Iterator

import httpx

from app.config import settings

DISCOVERY_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
EVENT_DETAIL_URL = "https://app.ticketmaster.com/discovery/v2/events/{event_id}.json"
PAGE_SIZE = 100
RATE_LIMIT_SLEEP_SECONDS = 0.25
MAX_RETRIES = 3


def fetch_event_detail(event_id: str) -> dict | None:
    """Fetches the live, full Ticketmaster event object for a single event
    id -- richer than what we store in Virtuoso (full description/pleaseNote,
    ticket limits, sales windows, seatmap, accessibility text), since our RDF
    mapping only keeps a deliberately narrowed subset. Returns None if the
    event no longer exists on Ticketmaster (404)."""
    with httpx.Client(timeout=30.0) as client:
        params = {"apikey": settings.ticket_master_key}
        response = client.get(EVENT_DETAIL_URL.format(event_id=event_id), params=params)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


def fetch_events(**search_params: str) -> Iterator[dict]:
    """Yields raw Ticketmaster event dicts (entries from `_embedded.events[]`)
    across all pages for the given Discovery API search params (e.g.
    city="Austin", classificationName="music"). Paginates via page.number /
    page.totalPages, rate-limited to stay under Ticketmaster's free-tier
    5 req/sec cap, and retries once on HTTP 429."""
    with httpx.Client(timeout=30.0) as client:
        page = 0
        while True:
            params = {
                **search_params,
                "apikey": settings.ticket_master_key,
                "page": page,
                "size": PAGE_SIZE,
            }
            try:
                response = _get_with_retry(client, params)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 400 and page > 0:
                    # Ticketmaster caps how deep you can page (page * size
                    # beyond roughly 1000 results returns 400 instead of an
                    # empty page) -- treat that as "no more results" rather
                    # than crashing the whole ingestion run. Queries with
                    # more matches than this cap (e.g. large cities) will
                    # only yield the first ~1000; that's a real API limit,
                    # not a bug here.
                    break
                raise
            payload = response.json()

            events = (payload.get("_embedded") or {}).get("events", [])
            yield from events

            page_info = payload.get("page", {})
            total_pages = page_info.get("totalPages", 0)
            if not events or page + 1 >= total_pages:
                break
            page += 1
            time.sleep(RATE_LIMIT_SLEEP_SECONDS)


def _get_with_retry(client: httpx.Client, params: dict) -> httpx.Response:
    for attempt in range(MAX_RETRIES):
        response = client.get(DISCOVERY_URL, params=params)
        if response.status_code != 429:
            response.raise_for_status()
            return response
        time.sleep(2**attempt)
    response.raise_for_status()
    return response
