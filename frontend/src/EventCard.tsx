import { categoryTint, formatDate, formatPrice, type EventSummary } from "./types";
import { BookmarkIcon, CalendarIcon, MapPinIcon, TicketIcon } from "./icons";

interface Props {
  event: EventSummary;
  saved: boolean;
  onToggleSave: (event: EventSummary) => void;
}

export default function EventCard({ event, saved, onToggleSave }: Props) {
  const tint = categoryTint(event.category?.segment);
  const price = formatPrice(event.offers);
  const date = formatDate(event.start_date);

  return (
    <div className="event-card">
      <div
        className="event-card-image"
        style={
          event.image
            ? { backgroundImage: `url(${event.image})` }
            : { background: `linear-gradient(135deg, ${tint} 0%, ${tint}bb 100%)` }
        }
      >
        <span className="event-badge">{event.category?.segment || "Event"}</span>
      </div>
      <div className="event-card-body">
        <div className="event-title">{event.name}</div>
        {event.venue && (
          <div className="event-meta">
            <MapPinIcon width={14} height={14} />
            <span>{event.venue.name}</span>
          </div>
        )}
        {date && (
          <div className="event-meta">
            <CalendarIcon width={14} height={14} />
            <span>{date}</span>
          </div>
        )}
        {price && (
          <div className="event-price">
            <span className="event-price-label">from</span>
            <span className="event-price-value">{price}</span>
          </div>
        )}
        <div className="event-actions">
          <button className={`save-btn${saved ? " saved" : ""}`} onClick={() => onToggleSave(event)}>
            <BookmarkIcon width={16} height={16} filled={saved} />
            {saved ? "Saved" : "Save"}
          </button>
          {event.url && (
            <a className="tickets-btn" href={event.url} target="_blank" rel="noreferrer">
              <TicketIcon width={15} height={15} />
              Tickets
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
