from datetime import datetime

from pydantic import BaseModel


class OfferOut(BaseModel):
    price_min: float | None = None
    price_max: float | None = None
    currency: str | None = None
    url: str | None = None


class VenueOut(BaseModel):
    id: str
    name: str
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    accessible: bool | None = None
    accessibility_note: str | None = None


class CategoryOut(BaseModel):
    segment: str | None = None
    genre: str | None = None
    sub_genre: str | None = None


class EventOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    start_date: datetime | None = None
    image: str | None = None
    url: str | None = None
    organizer: str | None = None
    performers: list[str] = []
    venue: VenueOut | None = None
    category: CategoryOut | None = None
    offers: list[OfferOut] = []
    distance_km: float | None = None


class EventSearchResponse(BaseModel):
    results: list[EventOut]
    total: int


class ChatMessage(BaseModel):
    role: str
    content: str
    events: list[EventOut] | None = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    username: str | None = None
    user_lat: float | None = None
    user_lon: float | None = None


class ChatResponse(BaseModel):
    reply: str
    events: list[EventOut] = []
