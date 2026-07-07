import { useState, useRef, useEffect, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";
import AuthForm from "./AuthForm";
import EventCard from "./EventCard";
import ProfilePage from "./ProfilePage";
import { ChatEmptyIcon, ClearIcon, LogoutIcon, SendIcon } from "./icons";
import type { EventSummary } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const USERNAME_KEY = "planorama_username";

interface Message {
  role: "user" | "assistant";
  content: string;
  events?: EventSummary[];
}

function initialMessages(): Message[] {
  return [
    {
      role: "assistant",
      content:
        "Hey! I can help you discover live events near you — concerts, sports, comedy and theater. Tell me what you're in the mood for.",
    },
  ];
}

function LogoIcon() {
  return (
    <div className="logo-icon">
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round">
        <path d="M4 8V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v2" />
        <path d="M4 8a2 2 0 0 1 0 4v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4a2 2 0 0 1 0-4" />
        <path d="M9 4v16" strokeDasharray="2.5 2.5" />
      </svg>
    </div>
  );
}

export default function App() {
  const [username, setUsername] = useState<string | null>(() => localStorage.getItem(USERNAME_KEY));
  const [view, setView] = useState<"chat" | "profile">("chat");
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [userLocation, setUserLocation] = useState<{ lat: number; lon: number } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, view]);

  useEffect(() => {
    if (!username) return;
    fetch(`${API_BASE}/users/${username}/saved`)
      .then((r) => r.json())
      .then((d) => setSavedIds(new Set(d.results.map((e: EventSummary) => e.id))))
      .catch(() => {});
  }, [username]);

  useEffect(() => {
    if (!username || !navigator.geolocation) return;
    // Best-effort: if the user denies the permission prompt or their
    // browser/device can't provide a location, we just never set
    // userLocation and the bot falls back to asking which city they mean
    // (see the location_note branch in the backend system prompt) --
    // there's no error state to show here, it's a silent enhancement.
    navigator.geolocation.getCurrentPosition(
      (position) => setUserLocation({ lat: position.coords.latitude, lon: position.coords.longitude }),
      () => {},
      { maximumAge: 10 * 60 * 1000, timeout: 8000 }
    );
  }, [username]);

  if (!username) {
    return (
      <AuthForm
        onAuthenticated={(u) => {
          localStorage.setItem(USERNAME_KEY, u);
          setUsername(u);
          setMessages(initialMessages());
          setView("chat");
        }}
      />
    );
  }

  function logout() {
    localStorage.removeItem(USERNAME_KEY);
    setUsername(null);
    setMessages(initialMessages());
    setSavedIds(new Set());
    setView("chat");
  }

  function clearChat() {
    setMessages([]);
    setView("chat");
  }

  async function toggleSave(event: EventSummary) {
    const isSaved = savedIds.has(event.id);
    setSavedIds((prev) => {
      const next = new Set(prev);
      if (isSaved) next.delete(event.id);
      else next.add(event.id);
      return next;
    });
    await fetch(`${API_BASE}/users/${username}/saved/${event.id}`, { method: isSaved ? "DELETE" : "POST" });
  }

  async function sendMessage(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const nextMessages: Message[] = [...messages, { role: "user", content: text }];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          user_lat: userLocation?.lat,
          user_lon: userLocation?.lon,
          // `events` is included for assistant turns so the backend can
          // resolve later follow-ups ("tell me more about that one") back
          // to a real event id -- see _to_openai_message on the backend.
          messages: nextMessages.map(({ role, content, events }) => ({ role, content, events })),
        }),
      });
      if (!response.ok) throw new Error(`Server returned ${response.status}`);
      const data = await response.json();
      setMessages([...nextMessages, { role: "assistant", content: data.reply, events: data.events }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="logo">
          <LogoIcon />
          <span className="logo-name">Planorama</span>
        </div>

        <button className="clear-chat-btn" onClick={clearChat}>
          <ClearIcon width={18} height={18} />
          Clear chat
        </button>

        <div className="account-block">
          <div className="account" onClick={() => setView("profile")}>
            <div className="avatar">{username.trim()[0]?.toUpperCase() || "?"}</div>
            <div className="account-info">
              <div className="account-name">{username}</div>
              <div className="account-sub">View profile</div>
            </div>
            <button
              className="icon-btn"
              title="Log out"
              onClick={(e) => {
                e.stopPropagation();
                logout();
              }}
            >
              <LogoutIcon width={18} height={18} />
            </button>
          </div>
        </div>
      </aside>

      {view === "profile" ? (
        <ProfilePage username={username} onBack={() => setView("chat")} onLogout={logout} savedIds={savedIds} onToggleSave={toggleSave} />
      ) : (
        <main className="chat-main">
          <div className="chat-scroll">
            <div className="chat-content">
              {messages.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-state-icon">
                    <ChatEmptyIcon width={26} height={26} />
                  </div>
                  <div className="empty-state-title">Start a new conversation</div>
                  <div className="empty-state-sub">Ask about concerts, sports, comedy or theater near you — or your saved events.</div>
                </div>
              ) : (
                <>
                  {messages.map((m, i) =>
                    m.role === "user" ? (
                      <div className="user-row" key={i}>
                        <div className="user-bubble">{m.content}</div>
                        <div className="avatar">{username.trim()[0]?.toUpperCase() || "?"}</div>
                      </div>
                    ) : (
                      <div key={i}>
                        <div className="assistant-text">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                        </div>
                        {m.events && m.events.length > 0 && (
                          <div className="event-grid">
                            {m.events.map((ev) => (
                              <EventCard key={ev.id} event={ev} saved={savedIds.has(ev.id)} onToggleSave={toggleSave} />
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  )}
                  {loading && <div className="typing-indicator">Thinking…</div>}
                  {error && <div className="error-banner">Error: {error}</div>}
                </>
              )}
              <div ref={bottomRef} />
            </div>
          </div>

          <form className="chat-input-bar" onSubmit={sendMessage}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about events, artists, dates…"
              disabled={loading}
            />
            <button className="send-btn" type="submit" disabled={loading || !input.trim()}>
              <SendIcon width={20} height={20} />
            </button>
          </form>
        </main>
      )}
    </div>
  );
}
