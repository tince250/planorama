import { useEffect, useState } from "react";
import EventCard from "./EventCard";
import { BackIcon, CloseIcon, LogoutIcon } from "./icons";
import type { EventSummary } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

interface Preferences {
  categories: string[];
  budget_min: number | null;
  budget_max: number | null;
}

interface Props {
  username: string;
  onBack: () => void;
  onLogout: () => void;
  savedIds: Set<string>;
  onToggleSave: (event: EventSummary) => void;
}

function budgetLabel(prefs: Preferences): string | null {
  if (prefs.budget_min != null && prefs.budget_max != null) return `$${prefs.budget_min} - $${prefs.budget_max}`;
  if (prefs.budget_max != null) return `Up to $${prefs.budget_max}`;
  if (prefs.budget_min != null) return `From $${prefs.budget_min}`;
  return null;
}

export default function ProfilePage({ username, onBack, onLogout, savedIds, onToggleSave }: Props) {
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [savedEvents, setSavedEvents] = useState<EventSummary[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/users/${username}/preferences`)
      .then((r) => r.json())
      .then(setPrefs);
    fetch(`${API_BASE}/users/${username}/saved`)
      .then((r) => r.json())
      .then((d) => setSavedEvents(d.results));
  }, [username]);

  async function removeCategory(category: string) {
    setPrefs((p) => (p ? { ...p, categories: p.categories.filter((c) => c !== category) } : p));
    await fetch(`${API_BASE}/users/${username}/preferences/categories?category=${encodeURIComponent(category)}`, {
      method: "DELETE",
    });
  }

  async function clearAllCategories() {
    if (!prefs) return;
    const categories = prefs.categories;
    setPrefs((p) => (p ? { ...p, categories: [] } : p));
    await Promise.all(
      categories.map((c) =>
        fetch(`${API_BASE}/users/${username}/preferences/categories?category=${encodeURIComponent(c)}`, {
          method: "DELETE",
        })
      )
    );
  }

  function unsaveEvent(event: EventSummary) {
    onToggleSave(event);
    setSavedEvents((events) => events.filter((e) => e.id !== event.id));
  }

  const budget = prefs ? budgetLabel(prefs) : null;

  return (
    <main className="profile-page">
      <div className="profile-inner">
        <button className="back-btn" onClick={onBack}>
          <BackIcon width={16} height={16} />
          Back to chat
        </button>

        <div className="identity-card">
          <div className="avatar">{username.trim()[0]?.toUpperCase() || "?"}</div>
          <div className="account-info">
            <div className="identity-name">{username}</div>
          </div>
          <button className="logout-pill" onClick={onLogout}>
            <LogoutIcon width={16} height={16} />
            Log out
          </button>
        </div>

        <div className="section-header">
          <div>
            <h2>Your preferences</h2>
            <p>We use these to personalize recommendations. Remove anything you're no longer into.</p>
          </div>
          {prefs && prefs.categories.length > 0 && (
            <button className="clear-all-btn" onClick={clearAllCategories}>
              Clear all
            </button>
          )}
        </div>

        <div className="pref-card">
          <div className="pref-card-header">
            <span className="pref-dot" />
            <span>Favorite categories</span>
          </div>
          {prefs && prefs.categories.length > 0 ? (
            <div className="chip-row">
              {prefs.categories.map((c) => (
                <span className="chip" key={c}>
                  {c}
                  <button title="Remove" onClick={() => removeCategory(c)}>
                    <CloseIcon width={12} height={12} />
                  </button>
                </span>
              ))}
            </div>
          ) : (
            <div className="pref-empty">No categories yet.</div>
          )}
        </div>

        <div className="pref-card">
          <div className="pref-card-header">
            <span className="pref-dot" style={{ background: "#2f6bed" }} />
            <span>Budget</span>
          </div>
          {budget ? <div className="budget-value">{budget}</div> : <div className="pref-empty">No budget set yet.</div>}
        </div>

        <div className="section-header">
          <div>
            <h2>Saved events</h2>
            <p>Events you've bookmarked from chat.</p>
          </div>
        </div>

        {savedEvents.length > 0 ? (
          <div className="event-grid">
            {savedEvents.map((ev) => (
              <EventCard key={ev.id} event={ev} saved={savedIds.has(ev.id)} onToggleSave={unsaveEvent} />
            ))}
          </div>
        ) : (
          <div className="pref-empty">No saved events yet.</div>
        )}
      </div>
    </main>
  );
}
