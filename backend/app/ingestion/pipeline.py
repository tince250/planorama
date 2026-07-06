"""Ingests events from the Ticketmaster Discovery API, maps them to RDF, and
upserts them into Virtuoso. Run on-demand/batch (not on the request path):

    cd backend
    python -m app.ingestion.pipeline --city Austin --classification music
"""

import argparse
import sys

from app.config import settings
from app.ingestion.ticketmaster_client import fetch_events
from app.rdf.graph_builder import build_event_graph
from app.rdf.iri import event_iri
from app.rdf.sparql_client import sparql_client


def upsert_event(event_data: dict) -> None:
    """Idempotently loads one event into the events graph: deletes the
    event subject's existing triples plus its existing offer subjects
    (offers are keyed off the event id, so they can't be targeted by the
    event-subject delete alone), then inserts the freshly built graph.
    Venue/category nodes use deterministic shared IRIs, so re-inserting
    their triples is a no-op if unchanged."""
    event_id = event_data["id"]
    graph_iri = settings.virtuoso_default_graph
    event_uri = event_iri(event_id)

    sparql_client.update(
        f"""
        PREFIX schema: <https://schema.org/>
        DELETE WHERE {{ GRAPH <{graph_iri}> {{ <{event_uri}> schema:offers ?offer . ?offer ?op ?oo }} }};
        DELETE WHERE {{ GRAPH <{graph_iri}> {{ <{event_uri}> ?p ?o }} }}
        """
    )

    graph = build_event_graph(event_data)
    sparql_client.insert_graph(graph_iri, graph)


def run(search_params: dict) -> int:
    if not settings.ticket_master_key:
        print("TICKET_MASTER_KEY is not set (check your .env file).", file=sys.stderr)
        return 1

    count = 0
    for event_data in fetch_events(**search_params):
        try:
            upsert_event(event_data)
            print(f"  loaded {event_data.get('id')}: {event_data.get('name')}")
        except Exception as exc:  # noqa: BLE001 - log and keep ingesting the rest of the batch
            print(f"  FAILED {event_data.get('id')}: {exc}", file=sys.stderr)
            continue
        count += 1

    print(f"Done. {count} events upserted into <{settings.virtuoso_default_graph}>.")
    return 0


def main() -> int:
    # Event names/venues can contain characters (curly quotes, accented
    # letters, em dashes) that Windows' default console codepage can't
    # encode -- without this, a plain print() of such a name raises
    # UnicodeEncodeError and kills the whole ingestion run partway through
    # (hit in practice: London/Madrid runs died after ~1-2% of events).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", help="Ticketmaster city search param")
    parser.add_argument("--classification", dest="classificationName", help="e.g. music, sports")
    parser.add_argument("--country-code", dest="countryCode", default="US")
    args = {k: v for k, v in vars(parser.parse_args()).items() if v is not None}
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
