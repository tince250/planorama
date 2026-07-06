#!/usr/bin/env bash
# Loads the ontology and hand-crafted sample events into a running Virtuoso
# instance (see ../../docker-compose.yml). Run from the repo root:
#   bash docker/virtuoso/load_samples.sh
set -euo pipefail

VIRTUOSO_HOST="${VIRTUOSO_HOST:-localhost:8890}"
VIRTUOSO_USER="${VIRTUOSO_USER:-dba}"
VIRTUOSO_PASSWORD="${VIRTUOSO_PASSWORD:-dba}"
ONTOLOGY_GRAPH="${VIRTUOSO_ONTOLOGY_GRAPH:-https://planorama.example.org/ontology}"
EVENTS_GRAPH="${VIRTUOSO_DEFAULT_GRAPH:-https://planorama.example.org/graphs/events}"

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

load_graph "ontology/planorama.ttl" "$ONTOLOGY_GRAPH"
load_graph "ontology/samples/sample_events.ttl" "$EVENTS_GRAPH"

echo
echo "Smoke-test read query:"
curl -s -G "http://$VIRTUOSO_HOST/sparql" \
  --data-urlencode "query=PREFIX schema: <https://schema.org/> PREFIX planorama: <https://planorama.example.org/ontology#> SELECT ?name ?venueName ?segment WHERE { GRAPH <$EVENTS_GRAPH> { ?event a schema:Event ; schema:name ?name ; schema:location ?venue ; planorama:hasCategory ?cat . ?venue schema:name ?venueName . ?cat planorama:segment ?segment } } ORDER BY ?name" \
  --data-urlencode "format=application/sparql-results+json"
echo
