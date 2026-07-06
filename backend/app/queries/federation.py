from app.rdf.escaping import escape_literal
from app.rdf.namespaces import EVENTS_GRAPH
from app.rdf.sparql_client import sparql_client

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"


def enrich_performer(name: str) -> dict | None:
    """Looks up a performer/artist/band that appears in our own ingested
    event data and enriches it with live facts from Wikidata via a
    federated SPARQL query (SERVICE) -- one query, issued to our own
    Virtuoso endpoint, that joins our local schema:performer triple with
    Wikidata's public graph over the network.

    Gotchas this had to work around (see the conversation that led here):
    (1) Wikidata's own triples use the plain http:// (not https://)
    schema.org namespace -- these are different, non-equal RDF terms, even
    though they're "the same" vocabulary conceptually; (2) our local
    performer literal has no language tag, but Wikidata's rdfs:label
    values are all @en-tagged, so a bare string won't unify -- hence the
    BIND(STRLANG(...)) cast; (3) neither `SERVICE SILENT` nor a negation
    pattern (MINUS / FILTER NOT EXISTS) *inside* the SERVICE block work on
    this Virtuoso instance -- both hit the same "no write permission on
    graph <wikidata-url>" error, which is really Virtuoso's federation
    query rewriter mis-planning negation/optionality as needing a remote
    write-like capability, not an actual permissions problem we can grant
    our way out of. So: no SILENT (resilience is a Python try/except
    instead), and disambiguation-page exclusion happens by fetching a
    handful of candidates and filtering in Python (see below) rather than
    with MINUS in the query. Label matching is inherently ambiguous for
    common names -- a same-named unrelated entity can still occasionally
    win -- acceptable for a demo, not for anything that needs
    guaranteed-correct identity resolution."""
    escaped = escape_literal(name)
    query = f"""
        PREFIX localschema: <https://schema.org/>
        PREFIX schema: <http://schema.org/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?description ?wikipediaUrl WHERE {{
          GRAPH <{EVENTS_GRAPH}> {{
            ?event localschema:performer ?performer .
            FILTER(?performer = "{escaped}")
          }}
          BIND(STRLANG(?performer, "en") AS ?performerEn)
          SERVICE <{WIKIDATA_ENDPOINT}> {{
            ?person rdfs:label ?performerEn .
            OPTIONAL {{ ?person schema:description ?description . FILTER(LANG(?description) = "en") }}
            OPTIONAL {{ ?wikipediaUrl schema:about ?person ; schema:isPartOf <https://en.wikipedia.org/> . }}
          }}
        }} LIMIT 5
        """
    try:
        rows = sparql_client.query(query)
    except Exception:  # noqa: BLE001 - Wikidata being slow/down shouldn't break the chat turn
        return None

    candidates = []
    for row in rows:
        description = row.get("description", {}).get("value")
        wikipedia_url = row.get("wikipediaUrl", {}).get("value")
        if description == "Wikimedia disambiguation page" or not (description or wikipedia_url):
            continue
        candidates.append({"name": name, "description": description, "wikipedia_url": wikipedia_url})

    if not candidates:
        return None
    # Prefer a candidate with an actual Wikipedia article -- SPARQL doesn't
    # guarantee row order, and for an ambiguous common-word name (e.g. the
    # band "Wilco" vs. the radio procedure word "wilco") the first
    # candidate is otherwise a coin flip. Having an English Wikipedia
    # article is a reasonable proxy for "the notable entity this name
    # probably refers to."
    return next((c for c in candidates if c["wikipedia_url"]), candidates[0])
