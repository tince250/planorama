import { useState, type FormEvent } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

interface Props {
  onAuthenticated: (username: string) => void;
}

function LogoIcon() {
  return (
    <div className="logo-icon">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round">
        <path d="M4 8V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v2" />
        <path d="M4 8a2 2 0 0 1 0 4v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4a2 2 0 0 1 0-4" />
        <path d="M9 4v16" strokeDasharray="2.5 2.5" />
      </svg>
    </div>
  );
}

export default function AuthForm({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Server returned ${response.status}`);
      onAuthenticated(data.username);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-app">
      <form className="auth-form" onSubmit={submit}>
        <div className="logo">
          <LogoIcon />
          <span className="logo-name">Planorama</span>
        </div>

        {mode === "login" ? (
          <>
            <h1>Welcome back</h1>
            <p className="auth-subtitle">Log in to discover events picked just for you.</p>
          </>
        ) : (
          <>
            <h1>Create your account</h1>
            <p className="auth-subtitle">Tell us who you are — we'll tailor events to your taste.</p>
          </>
        )}

        <label>Username</label>
        <input
          placeholder="you"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          required
        />
        <label>Password</label>
        <input
          type="password"
          placeholder={mode === "login" ? "••••••••" : "Create a password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          minLength={mode === "register" ? 6 : undefined}
          required
        />

        {error && <p className="auth-error">{error}</p>}

        <button type="submit" disabled={loading}>
          {loading ? "..." : mode === "login" ? "Log in" : "Create account"}
        </button>

        <p className="auth-switch">
          {mode === "login" ? (
            <>
              New here?{" "}
              <button type="button" onClick={() => setMode("register")}>
                Create an account
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button type="button" onClick={() => setMode("login")}>
                Log in
              </button>
            </>
          )}
        </p>
      </form>
    </div>
  );
}
