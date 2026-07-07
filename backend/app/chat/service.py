import json
from datetime import date

from openai import OpenAI

from app.config import settings
from app.ingestion.ticketmaster_client import fetch_event_detail
from app.models.event import EventOut
from app.queries.federation import enrich_performer
from app.queries.search import search_events
from app.queries.users import (
    add_preferred_categories,
    get_preferences,
    list_saved_events,
    save_event as save_event_query,
    set_budget,
    set_home_location,
)

def _system_prompt(username: str | None, user_lat: float | None, user_lon: float | None) -> str:
    today = date.today()
    if user_lat is not None and user_lon is not None:
        location_note = (
            f"The user's browser has shared their current location: lat={user_lat}, lon={user_lon}. "
            'When they ask for events "near me", "nearby", or otherwise want local results without '
            "naming a place, pass these as search_events' lat/lon (with a reasonable radius_km, e.g. "
            "10-25 depending on how local they want it) instead of asking which city they mean."
        )
    else:
        location_note = (
            'The user has not shared a location. If they ask for events "near me" or similar, '
            "explain you don't have their location and ask which city, region, or country they mean."
        )
    if username:
        login_note = (
            f'The user is logged in as "{username}". You may use update_preferences, '
            "save_event, list_saved_events, and get_my_preferences for them -- e.g. store a "
            'stated interest ("I like jazz and budget $50") via update_preferences, or save an '
            'event they liked via save_event. Do this proactively when they state a preference '
            "or ask to save something, without waiting to be asked to \"remember\" it."
        )
    else:
        login_note = (
            "No user is logged in. If they ask you to save an event or remember a preference, "
            "tell them they need to log in first -- you have no way to persist anything for them."
        )
    return f"""You are Planorama, a friendly assistant that helps users discover live events \
(concerts, sports, comedy, theater, etc.) -- the database covers multiple cities and countries, \
not just one fixed place, so never assume a specific city. If the user hasn't said where they \
want events and it matters for their request, ask which city, region, or country they're \
interested in before searching (pass whatever they say into search_events' location parameter, \
e.g. "Austin", "London", "Berlin", "Germany" -- it matches against the venue's city/region/country \
however the user phrases it, so don't try to normalize it yourself). {location_note} Today's date is \
{today.isoformat()} ({today.strftime("%A")}). Use the search_events tool whenever the user is \
looking for events, asking for recommendations, or refining a previous search with filters \
like category, price, date, location/distance, or accessibility. When the user references a \
relative date or range ("this weekend", "next week", "tonight", "in July"), resolve it yourself \
into concrete date_from/date_to values (YYYY-MM-DD) relative to today's date above before \
calling the tool -- never guess or assume a different "today". Ask a brief clarifying question \
if the request is too vague to search meaningfully, but don't stall on details the user hasn't \
given -- search with what you have and refine from there. IMPORTANT: when search_events returns \
2 or more results, the app renders each one as its own card directly below your message, already \
showing its name, date, venue, and price -- so your text reply must NOT name the individual \
events at all, in any format (no numbered list, no bullets, no "Event X at Venue Y on Date Z", \
not even inline). Treat the cards as the answer. Your text is only a short wrapper around them: \
one sentence introducing the set, optionally a second sentence noting a pattern across them \
(shared venue, price range, timeframe) or asking a follow-up question. If you catch yourself \
about to write a second event's name in the same reply, stop -- that information belongs on the \
card, not in your text. This restriction does not apply when search_events returns exactly one \
result, or when the user asked about one specific named event -- there, describe it normally. \
If a search returns no results, say so plainly and suggest loosening a filter. When the user asks for more detail about a specific event you already \
mentioned (full description, ticket limits, age restrictions, on-sale dates, where exactly to \
buy tickets, seating/accessibility specifics), call get_event_details with that event's id to \
fetch the live, fuller listing directly from Ticketmaster rather than guessing from what's \
already in the conversation. When the user asks who a performer/artist/band is, or wants \
background on one that came up in search results (genre, what they're known for, a link to \
learn more), call enrich_performer with that exact performer name -- it looks them up in a \
public knowledge graph (Wikidata) for a short bio and a Wikipedia link. If it returns nothing, \
say you couldn't find more info rather than inventing details. {login_note} Keep replies concise."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_events",
            "description": (
                "Search the Planorama events database with structured filters. "
                "Returns matching events with venue, price, category, and date info."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "Free-text search on the event name"},
                    "location": {
                        "type": "string",
                        "description": (
                            "City, region, or country to search in, matched against the venue's "
                            "address (e.g. 'Austin', 'London', 'Berlin', 'Germany', 'Texas'). Use "
                            "this whenever the user names a place, rather than assuming a default city."
                        ),
                    },
                    "category": {
                        "type": "string",
                        "description": "Category/segment/genre keyword, e.g. Music, Sports, Rock, Jazz, Basketball",
                    },
                    "date_from": {"type": "string", "description": "Earliest date, YYYY-MM-DD"},
                    "date_to": {"type": "string", "description": "Latest date, YYYY-MM-DD"},
                    "price_min": {"type": "number", "description": "Minimum ticket price in USD"},
                    "price_max": {"type": "number", "description": "Maximum ticket price / budget ceiling in USD"},
                    "lat": {"type": "number", "description": "Latitude to search near"},
                    "lon": {"type": "number", "description": "Longitude to search near"},
                    "radius_km": {"type": "number", "description": "Search radius in km (requires lat and lon)"},
                    "accessible_only": {"type": "boolean", "description": "Only venues with accessible seating"},
                    "limit": {"type": "integer", "description": "Max results to return (default 5, max 10)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_preferences",
            "description": (
                "Store or update the logged-in user's preferences: categories they like (added to "
                "their existing list, not replacing it), and/or their budget and home location "
                "(each replaces any previous value). Only include the fields the user actually "
                "stated; omit the rest."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Category interests to add, e.g. [\"jazz\", \"tech talks\"]",
                    },
                    "budget_min": {"type": "number"},
                    "budget_max": {"type": "number"},
                    "home_lat": {"type": "number"},
                    "home_lon": {"type": "number"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_preferences",
            "description": "Fetch the logged-in user's currently stored preferences (categories, budget, home location).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_event",
            "description": "Save an event to the logged-in user's saved list, e.g. when they say \"save that one\" or \"I want to go to that\".",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "The event id, as returned by search_events"},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_saved_events",
            "description": "List the events the logged-in user has previously saved.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_event_details",
            "description": (
                "Fetch the full, live listing for one specific event directly from Ticketmaster "
                "(by the event id returned from search_events). Use this when the user wants more "
                "detail than a search result summary -- full description, ticket limits, age "
                "restrictions, on-sale dates, where tickets are sold, or accessibility specifics."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "The event id, as returned by search_events"},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enrich_performer",
            "description": (
                "Look up a performer/artist/band (that appears in our event data, e.g. from a "
                "search_events or get_event_details result) on Wikidata for a short bio/description "
                "and a Wikipedia link. Use this when the user asks who someone is or wants background "
                "on an artist. Returns nothing if the performer isn't recognized."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "performer_name": {
                        "type": "string",
                        "description": "Exact performer name, as it appeared in search results",
                    },
                },
                "required": ["performer_name"],
            },
        },
    },
]


def _coerce_args(raw: dict) -> dict:
    args = dict(raw)
    for key in ("date_from", "date_to"):
        if args.get(key):
            args[key] = date.fromisoformat(args[key])
    args["limit"] = max(1, min(int(args.get("limit") or 5), 10))
    return args


def _summarize_events(events: list[EventOut], total: int) -> dict:
    return {
        "total_matches": total,
        "events": [
            {
                "id": e.id,
                "name": e.name,
                "start_date": e.start_date.isoformat() if e.start_date else None,
                "venue": e.venue.name if e.venue else None,
                "category": e.category.segment if e.category else None,
                "price_min": min((o.price_min for o in e.offers if o.price_min is not None), default=None),
                "price_max": max((o.price_max for o in e.offers if o.price_max is not None), default=None),
                "distance_km": e.distance_km,
                "accessible": e.venue.accessible if e.venue else None,
            }
            for e in events
        ],
    }


def _summarize_event_detail(detail: dict | None) -> dict:
    if detail is None:
        return {"error": "No event found with that id (it may no longer be listed on Ticketmaster)."}

    classification = next(
        (c for c in detail.get("classifications", []) if c.get("primary")),
        next(iter(detail.get("classifications", [])), {}),
    )
    venues = (detail.get("_embedded") or {}).get("venues", [])
    venue = venues[0] if venues else {}
    attractions = (detail.get("_embedded") or {}).get("attractions", [])
    sales = (detail.get("sales") or {}).get("public", {})

    return {
        "name": detail.get("name"),
        "url": detail.get("url"),
        "description": detail.get("info") or detail.get("pleaseNote") or detail.get("description"),
        "status": (detail.get("dates") or {}).get("status", {}).get("code"),
        "start_date": (detail.get("dates") or {}).get("start", {}).get("localDate"),
        "start_time": (detail.get("dates") or {}).get("start", {}).get("localTime"),
        "on_sale_start": sales.get("startDateTime"),
        "on_sale_end": sales.get("endDateTime"),
        "category": {
            "segment": (classification.get("segment") or {}).get("name"),
            "genre": (classification.get("genre") or {}).get("name"),
            "sub_genre": (classification.get("subGenre") or {}).get("name"),
        },
        "price_ranges": [
            {"min": p.get("min"), "max": p.get("max"), "currency": p.get("currency")}
            for p in detail.get("priceRanges", [])
        ],
        "ticket_limit_info": (detail.get("ticketLimit") or {}).get("info"),
        "age_restrictions": (detail.get("ageRestrictions") or {}).get("legalAgeEnforced"),
        "outlets": [o.get("url") for o in detail.get("outlets", [])],
        "venue_name": venue.get("name"),
        "venue_accessibility_note": venue.get("accessibleSeatingDetail"),
        "venue_box_office_info": venue.get("boxOfficeInfo"),
        "performers": [a.get("name") for a in attractions],
    }


def _to_openai_message(message: dict) -> dict:
    """Converts one client-supplied message into the {role, content} shape
    OpenAI's API accepts. Our server is stateless across HTTP requests, so
    the only way the model can resolve a later "tell me more about that
    Zoso show" is if the event ids we showed it are still somewhere in the
    conversation -- natural-language replies don't naturally contain ids,
    so we fold a compact id/name reference into the assistant turn's content
    sent to OpenAI (the frontend keeps rendering its own clean text; this
    appendix never reaches the user)."""
    content = message["content"]
    events = message.get("events")
    if message["role"] == "assistant" and events:
        ids = ", ".join(f'"{e["name"]}"=id:{e["id"]}' for e in events)
        content = f"{content}\n\n[event ids for reference: {ids}]"
    return {"role": message["role"], "content": content}


def _execute_tool_call(name: str, args: dict, username: str | None) -> tuple[str, list[EventOut] | None]:
    """Executes one tool call and returns (json content for the model,
    events to surface to the frontend if this was a search)."""
    needs_login = name in ("update_preferences", "get_my_preferences", "save_event", "list_saved_events")
    if needs_login and not username:
        return json.dumps({"error": "Not logged in -- ask the user to log in first."}), None

    if name == "get_event_details":
        return json.dumps(_summarize_event_detail(fetch_event_detail(args["event_id"]))), None

    if name == "enrich_performer":
        result = enrich_performer(args["performer_name"])
        return json.dumps(result or {"error": "No Wikidata info found for that performer."}), None

    if name == "update_preferences":
        if args.get("categories"):
            add_preferred_categories(username, args["categories"])
        if "budget_min" in args or "budget_max" in args:
            set_budget(username, args.get("budget_min"), args.get("budget_max"))
        if "home_lat" in args and "home_lon" in args:
            set_home_location(username, args["home_lat"], args["home_lon"])
        return json.dumps(get_preferences(username)), None

    if name == "get_my_preferences":
        return json.dumps(get_preferences(username)), None

    if name == "save_event":
        save_event_query(username, args["event_id"])
        return json.dumps({"saved": True, "event_id": args["event_id"]}), None

    if name == "list_saved_events":
        events = list_saved_events(username)
        return json.dumps(_summarize_events(events, len(events))), events

    if name == "search_events":
        events, total = search_events(**_coerce_args(args))
        return json.dumps(_summarize_events(events, total)), events

    return json.dumps({"error": f"Unknown tool '{name}'"}), None


MAX_TOOL_ROUNDS = 5


def run_chat(
    messages: list[dict],
    username: str | None = None,
    user_lat: float | None = None,
    user_lon: float | None = None,
) -> tuple[str, list[EventOut]]:
    """Runs one chat turn: sends the conversation (as provided by the
    client, stateless on the server) to the model with tools available, and
    keeps letting it call tools -- e.g. list_saved_events to see what the
    user saved, THEN search_events using what it just learned -- across
    multiple rounds until it stops requesting them, up to MAX_TOOL_ROUNDS as
    a safety cap. (An earlier version only allowed one round: the model
    could call list_saved_events, but by the time it wanted to follow up
    with search_events using the category it just learned, tools were no
    longer offered, so it could only say "let me check that" without
    actually doing it.) Returns the model's final natural-language reply
    plus the events from the last search (if any) for the frontend to
    optionally render alongside the text."""
    client = OpenAI(api_key=settings.openai_api_key)
    openai_messages = [
        {"role": "system", "content": _system_prompt(username, user_lat, user_lon)},
        *(_to_openai_message(m) for m in messages),
    ]
    matched_events: list[EventOut] = []

    for _ in range(MAX_TOOL_ROUNDS):
        completion = client.chat.completions.create(
            model=settings.openai_model,
            messages=openai_messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        message = completion.choices[0].message

        if not message.tool_calls:
            return message.content or "", matched_events

        openai_messages.append(message.model_dump(exclude_none=True))

        for tool_call in message.tool_calls:
            args = json.loads(tool_call.function.arguments or "{}")
            content, events = _execute_tool_call(tool_call.function.name, args, username)
            if events is not None:
                matched_events = events
            openai_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": content,
                }
            )

    # Round budget exhausted (very unusual) -- ask once more without tools
    # so we always return a real reply instead of silently giving up.
    final = client.chat.completions.create(model=settings.openai_model, messages=openai_messages)
    return final.choices[0].message.content or "", matched_events
