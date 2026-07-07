from rdflib import Graph

from SPARQLWrapper import DIGEST, JSON, POST, SPARQLWrapper

from app.config import settings


class SparqlClient:
    """Thin wrapper over SPARQLWrapper: `query()` hits Virtuoso's
    unauthenticated read endpoint, `update()` hits the authenticated
    (HTTP Digest) read/write endpoint. Virtuoso does not accept Basic auth
    on /sparql-auth -- only Digest."""

    def __init__(
        self,
        query_url: str | None = None,
        update_url: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        self.query_url = query_url or settings.virtuoso_sparql_url
        self.update_url = update_url or settings.virtuoso_sparql_auth_url
        self.user = user or settings.virtuoso_user
        self.password = password or settings.virtuoso_password

    def query(self, sparql: str) -> list[dict]:
        # POST, not GET: candidate/detail queries can embed hundreds of
        # event IRIs in a VALUES clause, which overflows a GET query string
        # and gets silently truncated by the HTTP stack before it reaches
        # Virtuoso (surfaces as a confusing SPARQL syntax error).
        wrapper = SPARQLWrapper(self.query_url)
        wrapper.setMethod(POST)
        wrapper.setQuery(sparql)
        wrapper.setReturnFormat(JSON)
        results = wrapper.query().convert()
        return results["results"]["bindings"]

    def ask(self, sparql: str) -> bool:
        wrapper = SPARQLWrapper(self.query_url)
        wrapper.setMethod(POST)
        wrapper.setQuery(sparql)
        wrapper.setReturnFormat(JSON)
        result = wrapper.query().convert()
        return bool(result.get("boolean"))

    def update(self, sparql: str) -> None:
        wrapper = SPARQLWrapper(self.update_url)
        wrapper.setHTTPAuth(DIGEST)
        wrapper.setCredentials(self.user, self.password)
        wrapper.setMethod(POST)
        wrapper.setQuery(sparql)
        wrapper.query()

    def replace_graph(self, graph_iri: str, graph: Graph) -> None:
        """Upserts a whole named graph: drops it, then inserts the given
        triples. Used for the very first bulk load of a graph; per-event
        upserts (see ingestion/pipeline.py) delete+insert individual
        subjects instead so unrelated events in the same graph are untouched."""
        self.update(f"DROP SILENT GRAPH <{graph_iri}>")
        if len(graph) == 0:
            return
        turtle = graph.serialize(format="nt")
        self.update(f"INSERT DATA {{ GRAPH <{graph_iri}> {{ {turtle} }} }}")

    def delete_subject(self, graph_iri: str, subject_iri: str) -> None:
        self.update(
            f"DELETE WHERE {{ GRAPH <{graph_iri}> {{ <{subject_iri}> ?p ?o }} }}"
        )

    def insert_graph(self, graph_iri: str, graph: Graph) -> None:
        if len(graph) == 0:
            return
        turtle = graph.serialize(format="nt")
        self.update(f"INSERT DATA {{ GRAPH <{graph_iri}> {{ {turtle} }} }}")


sparql_client = SparqlClient()
