import math
from collections import OrderedDict
from datetime import date

from app.models.event import CategoryOut, EventOut, OfferOut, VenueOut
from app.rdf.escaping import escape_literal as _escape_literal
from app.rdf.iri import event_iri
from app.rdf.namespaces import EVENTS_GRAPH
from app.rdf.sparql_client import sparql_client

PREFIXES = """
PREFIX schema: <https://schema.org/>
PREFIX planorama: <https://planorama.example.org/ontology#>
"""


def _short_id(iri: str) -> str:
    return iri.rsplit("/", 1)[-1]


def _bindings_value(binding: dict, var: str) -> str | None:
    entry = binding.get(var)
    return entry["value"] if entry else None


def _bindings_float(binding: dict, var: str) -> float | None:
    value = _bindings_value(binding, var)
    return float(value) if value is not None else None


def _bindings_bool(binding: dict, var: str) -> bool | None:
    # Virtuoso serializes xsd:boolean as "1"/"0" in SPARQL JSON results, not "true"/"false".
    value = _bindings_value(binding, var)
    return value in ("1", "true") if value is not None else None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _build_filter_body(
    q: str | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    accessible_only: bool = False,
    location: str | None = None,
    venue_iri: str | None = None,
    exclude_event_iri: str | None = None,
) -> str:
    """Only filters that
    are actually needed are added, so events lacking an unrelated optional
    field (e.g. no offers) aren't excluded. Distance/radius
    itself is handled separately in Python."""
    lines = ["?event a schema:Event ; schema:name ?name ; schema:startDate ?startDate ."]
    filters = []

    if venue_iri:
        lines.append(f"?event schema:location <{venue_iri}> .")
    if exclude_event_iri:
        filters.append(f"?event != <{exclude_event_iri}>")

    if q:
        filters.append(f'CONTAINS(LCASE(?name), LCASE("{_escape_literal(q)}"))')

    if category:
        lines.append(
            "?event planorama:hasCategory ?cat . "
            "{ ?cat planorama:segment ?catVal } UNION { ?cat planorama:genre ?catVal } "
            "UNION { ?cat planorama:subGenre ?catVal } ."
        )
        filters.append(f'CONTAINS(LCASE(?catVal), LCASE("{_escape_literal(category)}"))')

    if date_from:
        filters.append(f'?startDate >= "{date_from.isoformat()}T00:00:00"^^xsd:dateTime')
    if date_to:
        filters.append(f'?startDate <= "{date_to.isoformat()}T23:59:59"^^xsd:dateTime')

    if price_min is not None or price_max is not None:
        lines.append(
            "?event schema:offers ?offer . "
            "?offer planorama:minPrice ?offerMin ; planorama:maxPrice ?offerMax ."
        )
        if price_min is not None:
            filters.append(f"?offerMax >= {price_min}")
        if price_max is not None:
            filters.append(f"?offerMin <= {price_max}")

    if accessible_only:
        lines.append(
            "?event schema:location ?accVenue . ?accVenue planorama:hasAccessibleSeating true ."
        )

    if location:
        lines.append(
            "?event schema:location ?locVenue . ?locVenue schema:address ?locAddr . "
            "{ ?locAddr schema:addressLocality ?locVal } UNION { ?locAddr schema:addressRegion ?locVal } "
            "UNION { ?locAddr schema:addressCountry ?locVal } ."
        )
        filters.append(f'CONTAINS(LCASE(?locVal), LCASE("{_escape_literal(location)}"))')

    where_clause = " ".join(lines)
    if filters:
        where_clause += " FILTER(" + " && ".join(f"({f})" for f in filters) + ")"
    return where_clause


def build_candidate_query(
    limit: int | None = None,
    offset: int = 0,
    order_by_start_date: bool = True,
    **filter_kwargs,
) -> str:
    where_clause = _build_filter_body(**filter_kwargs)
    suffix = " ORDER BY ?startDate" if order_by_start_date else ""
    if limit is not None:
        suffix += f" LIMIT {int(limit)} OFFSET {int(offset)}"
    return f"""
{PREFIXES}
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT DISTINCT ?event WHERE {{
  GRAPH <{EVENTS_GRAPH}> {{
    {where_clause}
  }}
}} {suffix}
"""


def build_count_query(**filter_kwargs) -> str:
    where_clause = _build_filter_body(**filter_kwargs)
    return f"""
{PREFIXES}
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT (COUNT(DISTINCT ?event) AS ?total) WHERE {{
  GRAPH <{EVENTS_GRAPH}> {{
    {where_clause}
  }}
}}
"""


def build_geo_query(**filter_kwargs) -> str:
    """Lightweight variant of the candidate query that also returns each
    matched event's venue lat/lon (if any), without the heavier
    offers/category/performer joins of build_detail_query. Used only when
    distance sorting/filtering is requested, so we can rank+paginate the
    whole filtered set cheaply before fetching full detail for just the
    final page."""
    where_clause = _build_filter_body(**filter_kwargs)
    return f"""
{PREFIXES}
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT DISTINCT ?event ?lat ?lon WHERE {{
  GRAPH <{EVENTS_GRAPH}> {{
    {where_clause}
    OPTIONAL {{
      ?event schema:location ?geoVenue .
      ?geoVenue schema:geo ?geo .
      ?geo schema:latitude ?lat ; schema:longitude ?lon .
    }}
  }}
}}
"""


def build_detail_query(event_iris: list[str]) -> str:
    values = " ".join(f"<{iri}>" for iri in event_iris)
    return f"""
{PREFIXES}
SELECT ?event ?name ?description ?startDate ?image ?url ?organizer ?performer
       ?venue ?venueName ?street ?locality ?region ?lat ?lon ?accessible ?accessibilityNote
       ?catSegment ?catGenre ?catSubGenre
       ?offerMin ?offerMax ?offerCurrency ?offerUrl
WHERE {{
  GRAPH <{EVENTS_GRAPH}> {{
    VALUES ?event {{ {values} }}
    ?event a schema:Event ; schema:name ?name .
    OPTIONAL {{ ?event schema:description ?description }}
    OPTIONAL {{ ?event schema:startDate ?startDate }}
    OPTIONAL {{ ?event schema:image ?image }}
    OPTIONAL {{ ?event schema:url ?url }}
    OPTIONAL {{ ?event schema:organizer ?organizer }}
    OPTIONAL {{ ?event schema:performer ?performer }}
    OPTIONAL {{
      ?event schema:location ?venue .
      ?venue schema:name ?venueName .
      OPTIONAL {{ ?venue schema:address ?addr . ?addr schema:streetAddress ?street }}
      OPTIONAL {{ ?venue schema:address ?addr . ?addr schema:addressLocality ?locality }}
      OPTIONAL {{ ?venue schema:address ?addr . ?addr schema:addressRegion ?region }}
      OPTIONAL {{ ?venue schema:geo ?geo . ?geo schema:latitude ?lat }}
      OPTIONAL {{ ?venue schema:geo ?geo . ?geo schema:longitude ?lon }}
      OPTIONAL {{ ?venue planorama:hasAccessibleSeating ?accessible }}
      OPTIONAL {{ ?venue planorama:accessibilityNote ?accessibilityNote }}
    }}
    OPTIONAL {{
      ?event planorama:hasCategory ?cat .
      OPTIONAL {{ ?cat planorama:segment ?catSegment }}
      OPTIONAL {{ ?cat planorama:genre ?catGenre }}
      OPTIONAL {{ ?cat planorama:subGenre ?catSubGenre }}
    }}
    OPTIONAL {{
      ?event schema:offers ?offer .
      OPTIONAL {{ ?offer planorama:minPrice ?offerMin }}
      OPTIONAL {{ ?offer planorama:maxPrice ?offerMax }}
      OPTIONAL {{ ?offer schema:priceCurrency ?offerCurrency }}
      OPTIONAL {{ ?offer schema:url ?offerUrl }}
    }}
  }}
}}
"""


def bindings_to_events(bindings: list[dict]) -> "OrderedDict[str, EventOut]":
    events: "OrderedDict[str, EventOut]" = OrderedDict()
    performers: dict[str, set[str]] = {}
    offers: dict[str, set[tuple]] = {}

    for b in bindings:
        event_iri = _bindings_value(b, "event")
        if event_iri is None:
            continue

        if event_iri not in events:
            venue = None
            venue_iri = _bindings_value(b, "venue")
            if venue_iri:
                address_parts = [
                    _bindings_value(b, "street"),
                    _bindings_value(b, "locality"),
                    _bindings_value(b, "region"),
                ]
                address = ", ".join(p for p in address_parts if p) or None
                venue = VenueOut(
                    id=_short_id(venue_iri),
                    name=_bindings_value(b, "venueName") or "",
                    address=address,
                    lat=_bindings_float(b, "lat"),
                    lon=_bindings_float(b, "lon"),
                    accessible=_bindings_bool(b, "accessible"),
                    accessibility_note=_bindings_value(b, "accessibilityNote"),
                )

            category = None
            if any(_bindings_value(b, v) for v in ("catSegment", "catGenre", "catSubGenre")):
                category = CategoryOut(
                    segment=_bindings_value(b, "catSegment"),
                    genre=_bindings_value(b, "catGenre"),
                    sub_genre=_bindings_value(b, "catSubGenre"),
                )

            start_date = _bindings_value(b, "startDate")
            events[event_iri] = EventOut(
                id=_short_id(event_iri),
                name=_bindings_value(b, "name") or "",
                description=_bindings_value(b, "description"),
                start_date=start_date,
                image=_bindings_value(b, "image"),
                url=_bindings_value(b, "url"),
                organizer=_bindings_value(b, "organizer"),
                venue=venue,
                category=category,
            )
            performers[event_iri] = set()
            offers[event_iri] = set()

        performer = _bindings_value(b, "performer")
        if performer:
            performers[event_iri].add(performer)

        offer_min = _bindings_value(b, "offerMin")
        offer_max = _bindings_value(b, "offerMax")
        offer_currency = _bindings_value(b, "offerCurrency")
        offer_url = _bindings_value(b, "offerUrl")
        if offer_min or offer_max or offer_currency:
            offers[event_iri].add((offer_min, offer_max, offer_currency, offer_url))

    for event_iri, event in events.items():
        event.performers = sorted(performers[event_iri])
        event.offers = [
            OfferOut(
                price_min=float(mn) if mn else None,
                price_max=float(mx) if mx else None,
                currency=cur,
                url=url,
            )
            for mn, mx, cur, url in offers[event_iri]
        ]

    return events


def fetch_events_by_iri(event_iris: list[str]) -> list[EventOut]:
    if not event_iris:
        return []
    events_by_iri = bindings_to_events(sparql_client.query(build_detail_query(event_iris)))
    return [events_by_iri[iri] for iri in event_iris if iri in events_by_iri]


def search_events(
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
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[EventOut], int]:
    filter_kwargs = dict(
        q=q,
        category=category,
        date_from=date_from,
        date_to=date_to,
        price_min=price_min,
        price_max=price_max,
        accessible_only=accessible_only,
        location=location,
    )

    if lat is not None and lon is not None:
        # Distance sort/filter needs every matching event's coordinates up
        # front, but not full detail (offers/category/performers)
        geo_bindings = sparql_client.query(build_geo_query(**filter_kwargs))
        ranked: list[tuple[str, float | None]] = []
        for b in geo_bindings:
            event_lat = _bindings_float(b, "lat")
            event_lon = _bindings_float(b, "lon")
            distance = (
                haversine_km(lat, lon, event_lat, event_lon)
                if event_lat is not None and event_lon is not None
                else None
            )
            ranked.append((b["event"]["value"], distance))

        if radius_km is not None:
            ranked = [(iri, d) for iri, d in ranked if d is not None and d <= radius_km]
        ranked.sort(key=lambda pair: (pair[1] is None, pair[1] if pair[1] is not None else 0))

        total = len(ranked)
        page = ranked[offset : offset + limit]
        distance_by_iri = {iri: d for iri, d in page}
        events = fetch_events_by_iri([iri for iri, _ in page])
        for event in events:
            distance = distance_by_iri.get(str(event_iri(event.id)))
            if distance is not None:
                event.distance_km = round(distance, 2)
        return events, total

    total = int(sparql_client.query(build_count_query(**filter_kwargs))[0]["total"]["value"])
    page_iris = [
        b["event"]["value"]
        for b in sparql_client.query(build_candidate_query(limit=limit, offset=offset, **filter_kwargs))
    ]
    return fetch_events_by_iri(page_iris), total
