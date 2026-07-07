from fastapi import APIRouter

from app.models.event import EventSearchResponse
from app.models.user import PreferencesOut
from app.queries.users import (
    get_preferences,
    list_saved_events,
    remove_preferred_category,
    remove_saved_event,
    save_event,
)

router = APIRouter(prefix="/users")


@router.get("/{username}/preferences", response_model=PreferencesOut)
def get_user_preferences(username: str):
    return PreferencesOut(**get_preferences(username))


@router.delete("/{username}/preferences/categories")
def delete_user_category(username: str, category: str):
    remove_preferred_category(username, category)
    return {"removed": category}


@router.get("/{username}/saved", response_model=EventSearchResponse)
def get_saved(username: str):
    events = list_saved_events(username)
    return EventSearchResponse(results=events, total=len(events))


@router.post("/{username}/saved/{event_id}")
def add_saved(username: str, event_id: str):
    save_event(username, event_id)
    return {"saved": event_id}


@router.delete("/{username}/saved/{event_id}")
def delete_saved(username: str, event_id: str):
    remove_saved_event(username, event_id)
    return {"removed": event_id}
