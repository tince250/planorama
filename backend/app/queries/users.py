from app.queries.search import fetch_events_by_iri
from app.rdf.escaping import escape_literal
from app.rdf.iri import budget_iri, event_iri, user_iri
from app.rdf.namespaces import USERS_GRAPH
from app.rdf.sparql_client import sparql_client

PREFIXES = """
PREFIX schema: <https://schema.org/>
PREFIX planorama: <https://planorama.example.org/ontology#>
"""


def user_exists(username: str) -> bool:
    return sparql_client.ask(
        f"""
        {PREFIXES}
        ASK {{ GRAPH <{USERS_GRAPH}> {{ <{user_iri(username)}> a schema:Person }} }}
        """
    )


def create_user(username: str, password_hash: str, salt: str) -> None:
    sparql_client.update(
        f"""
        {PREFIXES}
        INSERT DATA {{
          GRAPH <{USERS_GRAPH}> {{
            <{user_iri(username)}> a schema:Person ;
              planorama:username "{escape_literal(username)}" ;
              planorama:passwordHash "{password_hash}" ;
              planorama:passwordSalt "{salt}" .
          }}
        }}
        """
    )


def get_credentials(username: str) -> tuple[str, str] | None:
    rows = sparql_client.query(
        f"""
        {PREFIXES}
        SELECT ?hash ?salt WHERE {{
          GRAPH <{USERS_GRAPH}> {{
            <{user_iri(username)}> planorama:passwordHash ?hash ; planorama:passwordSalt ?salt .
          }}
        }}
        """
    )
    if not rows:
        return None
    return rows[0]["hash"]["value"], rows[0]["salt"]["value"]


def add_preferred_categories(username: str, categories: list[str]) -> None:
    if not categories:
        return
    triples = "\n".join(
        f'<{user_iri(username)}> planorama:prefersCategory "{escape_literal(c)}" .' for c in categories
    )
    sparql_client.update(
        f"""
        {PREFIXES}
        INSERT DATA {{ GRAPH <{USERS_GRAPH}> {{ {triples} }} }}
        """
    )


def set_budget(username: str, budget_min: float | None, budget_max: float | None) -> None:
    b_iri = budget_iri(username)
    sparql_client.update(
        f"""
        {PREFIXES}
        DELETE WHERE {{ GRAPH <{USERS_GRAPH}> {{ <{user_iri(username)}> planorama:hasBudget ?b . ?b ?p ?o }} }};
        DELETE WHERE {{ GRAPH <{USERS_GRAPH}> {{ <{user_iri(username)}> planorama:hasBudget ?b }} }}
        """
    )
    fields = []
    if budget_min is not None:
        fields.append(f"planorama:minBudget {float(budget_min)}")
    if budget_max is not None:
        fields.append(f"planorama:maxBudget {float(budget_max)}")
    if not fields:
        return
    sparql_client.update(
        f"""
        {PREFIXES}
        INSERT DATA {{
          GRAPH <{USERS_GRAPH}> {{
            <{user_iri(username)}> planorama:hasBudget <{b_iri}> .
            <{b_iri}> a planorama:BudgetRange ; {" ; ".join(fields)} .
          }}
        }}
        """
    )


def set_home_location(username: str, lat: float, lon: float) -> None:
    sparql_client.update(
        f"""
        {PREFIXES}
        DELETE WHERE {{ GRAPH <{USERS_GRAPH}> {{ <{user_iri(username)}> planorama:homeLat ?a }} }};
        DELETE WHERE {{ GRAPH <{USERS_GRAPH}> {{ <{user_iri(username)}> planorama:homeLon ?b }} }};
        INSERT DATA {{
          GRAPH <{USERS_GRAPH}> {{
            <{user_iri(username)}> planorama:homeLat {float(lat)} ; planorama:homeLon {float(lon)} .
          }}
        }}
        """
    )


def save_event(username: str, event_id: str) -> None:
    sparql_client.update(
        f"""
        {PREFIXES}
        INSERT DATA {{ GRAPH <{USERS_GRAPH}> {{ <{user_iri(username)}> planorama:savedEvent <{event_iri(event_id)}> }} }}
        """
    )


def remove_saved_event(username: str, event_id: str) -> None:
    sparql_client.update(
        f"""
        {PREFIXES}
        DELETE DATA {{ GRAPH <{USERS_GRAPH}> {{ <{user_iri(username)}> planorama:savedEvent <{event_iri(event_id)}> }} }}
        """
    )


def remove_preferred_category(username: str, category: str) -> None:
    sparql_client.update(
        f"""
        {PREFIXES}
        DELETE DATA {{ GRAPH <{USERS_GRAPH}> {{ <{user_iri(username)}> planorama:prefersCategory "{escape_literal(category)}" }} }}
        """
    )


def get_preferences(username: str) -> dict:
    rows = sparql_client.query(
        f"""
        {PREFIXES}
        SELECT ?category ?minBudget ?maxBudget ?homeLat ?homeLon WHERE {{
          GRAPH <{USERS_GRAPH}> {{
            OPTIONAL {{ <{user_iri(username)}> planorama:prefersCategory ?category }}
            OPTIONAL {{ <{user_iri(username)}> planorama:hasBudget ?b . ?b planorama:minBudget ?minBudget }}
            OPTIONAL {{ <{user_iri(username)}> planorama:hasBudget ?b . ?b planorama:maxBudget ?maxBudget }}
            OPTIONAL {{ <{user_iri(username)}> planorama:homeLat ?homeLat }}
            OPTIONAL {{ <{user_iri(username)}> planorama:homeLon ?homeLon }}
          }}
        }}
        """
    )
    categories = sorted({r["category"]["value"] for r in rows if "category" in r})
    budget_min = next((r["minBudget"]["value"] for r in rows if "minBudget" in r), None)
    budget_max = next((r["maxBudget"]["value"] for r in rows if "maxBudget" in r), None)
    home_lat = next((r["homeLat"]["value"] for r in rows if "homeLat" in r), None)
    home_lon = next((r["homeLon"]["value"] for r in rows if "homeLon" in r), None)
    return {
        "categories": categories,
        "budget_min": float(budget_min) if budget_min else None,
        "budget_max": float(budget_max) if budget_max else None,
        "home_lat": float(home_lat) if home_lat else None,
        "home_lon": float(home_lon) if home_lon else None,
    }


def list_saved_events(username: str) -> list:
    rows = sparql_client.query(
        f"""
        {PREFIXES}
        SELECT ?event WHERE {{ GRAPH <{USERS_GRAPH}> {{ <{user_iri(username)}> planorama:savedEvent ?event }} }}
        """
    )
    return fetch_events_by_iri([r["event"]["value"] for r in rows])
