#!/usr/bin/env bash
# Loads the ontology plus a full real-data snapshot (ontology/data/events_snapshot.ttl,
# exported via SPARQL CONSTRUCT from a live-ingested Virtuoso instance) so every
# teammate ends up with byte-identical event data, without needing a Ticketmaster
# API key or re-running the (slow, rate-limited, non-reproducible-over-time)
# ingestion pipeline. Run from the repo root, with Virtuoso already up:
#   docker compose up -d virtuoso
#   bash docker/virtuoso/load_snapshot.sh
set -euo pipefail

VIRTUOSO_HOST="${VIRTUOSO_HOST:-localhost:8890}"
VIRTUOSO_USER="${VIRTUOSO_USER:-dba}"
VIRTUOSO_PASSWORD="${VIRTUOSO_PASSWORD:-dba}"
ONTOLOGY_GRAPH="${VIRTUOSO_ONTOLOGY_GRAPH:-https://planorama.example.org/ontology}"
EVENTS_GRAPH="${VIRTUOSO_DEFAULT_GRAPH:-https://planorama.example.org/graphs/events}"

drop_graph() {
  local graph="$1"
  echo "Dropping <$graph> (if it exists) for a clean, reproducible import..."
  curl -s --digest -u "$VIRTUOSO_USER:$VIRTUOSO_PASSWORD" -X POST \
    --data-urlencode "update=DROP SILENT GRAPH <$graph>" \
    "http://$VIRTUOSO_HOST/sparql-auth" > /dev/null
}

load_graph() {
  local file="$1" graph="$2"
  echo "Loading $file into <$graph> ..."
  code=$(curl -s -o /dev/null -w "%{http_code}" --digest -u "$VIRTUOSO_USER:$VIRTUOSO_PASSWORD" \
    -X POST -H "Content-Type: text/turtle" \
    --data-binary "@$file" \
    "http://$VIRTUOSO_HOST/sparql-graph-crud-auth?graph-uri=$graph")
  if [ "$code" != "200" ] && [ "$code" != "201" ]; then
    echo "  FAILED (HTTP $code)"
    exit 1
  fi
  echo "  OK ($code)"
}

drop_graph "$ONTOLOGY_GRAPH"
drop_graph "$EVENTS_GRAPH"
load_graph "ontology/planorama.ttl" "$ONTOLOGY_GRAPH"
load_graph "ontology/data/events_snapshot.ttl" "$EVENTS_GRAPH"

echo
echo "Triple count check:"
curl -s -G "http://$VIRTUOSO_HOST/sparql" \
  --data-urlencode "query=PREFIX schema: <https://schema.org/> SELECT (COUNT(DISTINCT ?event) as ?total) WHERE { GRAPH <$EVENTS_GRAPH> { ?event a schema:Event } }" \
  --data-urlencode "format=application/sparql-results+json"
echo
