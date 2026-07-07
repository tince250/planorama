import re

from rdflib import URIRef

from app.rdf.namespaces import PRES

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    return _SLUG_RE.sub("-", value.lower()).strip("-")


def event_iri(ticketmaster_event_id: str) -> URIRef:
    return PRES[f"event/{ticketmaster_event_id}"]


def venue_iri(ticketmaster_venue_id: str) -> URIRef:
    return PRES[f"venue/{ticketmaster_venue_id}"]


def venue_address_iri(ticketmaster_venue_id: str) -> URIRef:
    return PRES[f"venue/{ticketmaster_venue_id}/address"]


def venue_geo_iri(ticketmaster_venue_id: str) -> URIRef:
    return PRES[f"venue/{ticketmaster_venue_id}/geo"]


def offer_iri(ticketmaster_event_id: str, index: int) -> URIRef:
    return PRES[f"offer/{ticketmaster_event_id}-{index}"]


def category_iri(segment: str | None, genre: str | None, sub_genre: str | None) -> URIRef:
    parts = [p for p in (segment, genre, sub_genre) if p]
    slug = "-".join(_slugify(p) for p in parts) or "uncategorized"
    return PRES[f"category/{slug}"]


def user_iri(username: str) -> URIRef:
    return PRES[f"user/{username}"]


def budget_iri(username: str) -> URIRef:
    return PRES[f"budget/{username}"]
