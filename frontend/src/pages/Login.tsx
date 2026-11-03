import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { FormError } from "../components/States";
import { useAuth } from "../context/AuthContext";
import { fieldError } from "../hooks";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const user = await login(email.trim(), password);
      navigate(user.role === "staff" ? "/staff" : from ?? "/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "error", "Something went wrong."));
    } finally { setBusy(false); }
  }

  return (
    <div className="auth-shell">
      <aside className="auth-art" aria-hidden="true">
        <span className="auth-emoji">🍜</span>
        <p className="auth-tag">Welcome back. Your next meal is a few taps away.</p>
      </aside>
    <section className="auth">
      <h1>Log in</h1>
      <form onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                 aria-invalid={!!fieldError(error, "email")} />
          <p className="field-error">{fieldError(error, "email")}</p>
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <FormError message={error && !error.fields.length ? error.message : null} />
        <button className="btn btn-large" disabled={busy}>{busy ? "Logging in…" : "Log in"}</button>
      </form>
      <p className="muted">New here? <Link to="/register">Create an account</Link></p>
    </section>
    </div>
  );
}
