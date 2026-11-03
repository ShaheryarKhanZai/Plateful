import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { FormError } from "../components/States";
import { useAuth } from "../context/AuthContext";
import { fieldError } from "../hooks";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await register(email.trim(), password, fullName.trim());
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "error", "Something went wrong."));
    } finally { setBusy(false); }
  }

  return (
    <div className="auth-shell">
      <aside className="auth-art" aria-hidden="true">
        <span className="auth-emoji">🍕</span>
        <p className="auth-tag">Hot food, tracked from the stove to your door.</p>
      </aside>
    <section className="auth">
      <h1>Create your account</h1>
      <form onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="name">Full name</label>
          <input id="name" autoComplete="name" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          <p className="field-error">{fieldError(error, "full_name")}</p>
        </div>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <p className="field-error">{fieldError(error, "email")}</p>
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <p className="hint">At least 10 characters, with letters and numbers.</p>
          <p className="field-error">{fieldError(error, "password")}</p>
        </div>
        <FormError message={error && !error.fields.length ? error.message : null} />
        <button className="btn btn-large" disabled={busy}>{busy ? "Creating account…" : "Create account"}</button>
      </form>
      <p className="muted">Already have an account? <Link to="/login">Log in</Link></p>
    </section>
    </div>
  );
}
