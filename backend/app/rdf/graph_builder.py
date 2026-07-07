from decimal import Decimal, InvalidOperation
from typing import Any

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from app.rdf.iri import category_iri, event_iri, offer_iri, venue_address_iri, venue_geo_iri, venue_iri
from app.rdf.namespaces import PLANORAMA, SCHEMA


def _decimal(value: Any) -> Literal | None:
    if value is None:
        return None
    try:
        return Literal(Decimal(str(value)), datatype=XSD.decimal)
    except InvalidOperation:
        return None


def _float(value: Any) -> Literal | None:
    if value is None:
        return None
    try:
        return Literal(float(value), datatype=XSD.decimal)
    except (TypeError, ValueError):
        return None


def _primary_classification(event_data: dict) -> dict | None:
    classifications = event_data.get("classifications") or []
    for c in classifications:
        if c.get("primary"):
            return c
    return classifications[0] if classifications else None


def _description(event_data: dict, classification: dict | None) -> str:
    info = event_data.get("info") or event_data.get("pleaseNote")
    if info:
        return info
    name = event_data.get("name", "")
    if classification:
        segment = (classification.get("segment") or {}).get("name")
        genre = (classification.get("genre") or {}).get("name")
        if segment and genre:
            return f"{name} ({segment} - {genre})"
        if segment:
            return f"{name} ({segment})"
    return name


def _best_image(event_data: dict) -> str | None:
    images = event_data.get("images") or []
    for img in images:
        if img.get("ratio") == "16_9" and img.get("width", 0) >= 1024:
            return img.get("url")
    return images[0].get("url") if images else None


def _add_venue(graph: Graph, venue_data: dict) -> URIRef:
    venue_id = venue_data.get("id")
    venue_uri = venue_iri(venue_id)

    if (venue_uri, RDF.type, SCHEMA.Place) in graph:
        return venue_uri

    graph.add((venue_uri, RDF.type, SCHEMA.Place))
    graph.add((venue_uri, PLANORAMA.sourceId, Literal(venue_id)))
    if venue_data.get("name"):
        graph.add((venue_uri, SCHEMA.name, Literal(venue_data["name"])))
    if venue_data.get("url"):
        graph.add((venue_uri, SCHEMA.url, URIRef(venue_data["url"])))

    accessibility_note = venue_data.get("accessibleSeatingDetail")
    graph.add((venue_uri, PLANORAMA.hasAccessibleSeating, Literal(bool(accessibility_note))))
    if accessibility_note:
        graph.add((venue_uri, PLANORAMA.accessibilityNote, Literal(accessibility_note)))

    # Deterministic sub-IRIs, not blank nodes: a blank node minted fresh on
    # every event upsert doesn't dedupe against the one minted for the same
    # venue by a previous upsert, so a popular venue accumulates one
    # "duplicate" address/geo node per event ever ingested for it. Virtuoso
    # then has to join every event at that venue against every one of those
    # near-identical address nodes -- an N x N blowup that made any
    # location-filtered query on a busy venue hang (hit in practice: one
    # venue had 2,024 duplicate address nodes and a 2-million-row join).
    # A deterministic IRI means re-inserting the same triples is a no-op.
    address = venue_data.get("address") or {}
    address_node = venue_address_iri(venue_id)
    graph.add((venue_uri, SCHEMA.address, address_node))
    graph.add((address_node, RDF.type, SCHEMA.PostalAddress))
    if address.get("line1"):
        graph.add((address_node, SCHEMA.streetAddress, Literal(address["line1"])))
    if venue_data.get("postalCode"):
        graph.add((address_node, SCHEMA.postalCode, Literal(venue_data["postalCode"])))
    if venue_data.get("city", {}).get("name"):
        graph.add((address_node, SCHEMA.addressLocality, Literal(venue_data["city"]["name"])))
    if venue_data.get("state", {}).get("name"):
        graph.add((address_node, SCHEMA.addressRegion, Literal(venue_data["state"]["name"])))
    if venue_data.get("country", {}).get("name"):
        graph.add((address_node, SCHEMA.addressCountry, Literal(venue_data["country"]["name"])))

    location = venue_data.get("location") or {}
    lat = _float(location.get("latitude"))
    lon = _float(location.get("longitude"))
    if lat is not None and lon is not None:
        geo_node = venue_geo_iri(venue_id)
        graph.add((venue_uri, SCHEMA.geo, geo_node))
        graph.add((geo_node, RDF.type, SCHEMA.GeoCoordinates))
        graph.add((geo_node, SCHEMA.latitude, lat))
        graph.add((geo_node, SCHEMA.longitude, lon))

    return venue_uri


def _add_category(graph: Graph, classification: dict | None) -> URIRef | None:
    if not classification:
        return None
    segment = (classification.get("segment") or {}).get("name")
    genre = (classification.get("genre") or {}).get("name")
    sub_genre = (classification.get("subGenre") or {}).get("name")
    if not (segment or genre or sub_genre):
        return None

    category_uri = category_iri(segment, genre, sub_genre)
    if (category_uri, RDF.type, PLANORAMA.EventCategory) in graph:
        return category_uri

    graph.add((category_uri, RDF.type, PLANORAMA.EventCategory))
    if segment:
        graph.add((category_uri, PLANORAMA.segment, Literal(segment)))
    if genre:
        graph.add((category_uri, PLANORAMA.genre, Literal(genre)))
    if sub_genre:
        graph.add((category_uri, PLANORAMA.subGenre, Literal(sub_genre)))
    return category_uri


def build_event_graph(event_data: dict) -> Graph:
    """Maps a single Ticketmaster Discovery API event (an entry from
    `_embedded.events[]`) into an rdflib.Graph of Schema.org + planorama:
    triples. Deterministic IRIs (minted from Ticketmaster ids) make this
    idempotent across repeated ingestion runs."""
    graph = Graph()
    graph.bind("schema", SCHEMA)
    graph.bind("planorama", PLANORAMA)

    event_id = event_data["id"]
    event_uri = event_iri(event_id)
    classification = _primary_classification(event_data)

    graph.add((event_uri, RDF.type, SCHEMA.Event))
    graph.add((event_uri, PLANORAMA.sourceId, Literal(event_id)))
    graph.add((event_uri, SCHEMA.name, Literal(event_data.get("name", ""))))
    graph.add((event_uri, SCHEMA.description, Literal(_description(event_data, classification))))
    if event_data.get("url"):
        graph.add((event_uri, SCHEMA.url, URIRef(event_data["url"])))

    image = _best_image(event_data)
    if image:
        graph.add((event_uri, SCHEMA.image, URIRef(image)))

    start = (event_data.get("dates") or {}).get("start") or {}
    start_date_time = start.get("dateTime")
    if start_date_time:
        graph.add((event_uri, SCHEMA.startDate, Literal(start_date_time, datatype=XSD.dateTime)))
    elif start.get("localDate"):
        # dateTime missing/TBD -- fall back to the local date only.
        graph.add((event_uri, SCHEMA.startDate, Literal(start["localDate"], datatype=XSD.date)))

    promoter = event_data.get("promoter") or {}
    if promoter.get("name"):
        graph.add((event_uri, SCHEMA.organizer, Literal(promoter["name"])))

    for attraction in (event_data.get("_embedded") or {}).get("attractions", []):
        if attraction.get("name"):
            graph.add((event_uri, SCHEMA.performer, Literal(attraction["name"])))

    category_uri = _add_category(graph, classification)
    if category_uri is not None:
        graph.add((event_uri, PLANORAMA.hasCategory, category_uri))

    venues = (event_data.get("_embedded") or {}).get("venues", [])
    for venue_data in venues:
        venue_uri = _add_venue(graph, venue_data)
        graph.add((event_uri, SCHEMA.location, venue_uri))

    for index, price_range in enumerate(event_data.get("priceRanges", [])):
        offer_uri = offer_iri(event_id, index)
        graph.add((offer_uri, RDF.type, SCHEMA.Offer))
        if event_data.get("url"):
            graph.add((offer_uri, SCHEMA.url, URIRef(event_data["url"])))
        if price_range.get("currency"):
            graph.add((offer_uri, SCHEMA.priceCurrency, Literal(price_range["currency"])))
        min_price = _decimal(price_range.get("min"))
        max_price = _decimal(price_range.get("max"))
        if min_price is not None:
            graph.add((offer_uri, SCHEMA.price, min_price))
            graph.add((offer_uri, PLANORAMA.minPrice, min_price))
        if max_price is not None:
            graph.add((offer_uri, PLANORAMA.maxPrice, max_price))
        graph.add((event_uri, SCHEMA.offers, offer_uri))

    return graph


def build_events_graph(api_response: dict) -> Graph:
    """Maps a full Ticketmaster Discovery API `/events` response (as returned
    by the paginated client) into a single merged rdflib.Graph."""
    events = (api_response.get("_embedded") or {}).get("events", [])
    merged = Graph()
    merged.bind("schema", SCHEMA)
    merged.bind("planorama", PLANORAMA)
    for event_data in events:
        merged += build_event_graph(event_data)
    return merged
