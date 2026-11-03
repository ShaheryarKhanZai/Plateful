import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api/client";
import { FormError } from "../components/States";
import { useAuth } from "../context/AuthContext";
import { fieldError } from "../hooks";

export default function Profile() {
  const { user, setUser } = useAuth();
  const [name, setName] = useState(user?.full_name ?? "");
  const [address, setAddress] = useState(user?.default_address ?? "");
  const [error, setError] = useState<ApiError | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!user) return null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null); setSaved(false);
    try {
      const body: { full_name: string; default_address?: string } = { full_name: name };
      if (address.trim()) body.default_address = address;
      setUser(await api.updateProfile(body));
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "error", "Something went wrong."));
    } finally { setBusy(false); }
  }

  return (
    <section className="auth">
      <h1>Your profile</h1>
      <dl className="facts"><dt>Email</dt><dd>{user.email}</dd><dt>Account type</dt><dd>{user.role === "staff" ? "Restaurant staff" : "Customer"}</dd></dl>
      <form onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="name">Full name</label>
          <input id="name" value={name} onChange={(e) => setName(e.target.value)} />
          <p className="field-error">{fieldError(error, "full_name")}</p>
        </div>
        {user.role === "customer" && (
          <div className="field">
            <label htmlFor="addr">Default delivery address</label>
            <input id="addr" value={address} onChange={(e) => setAddress(e.target.value)} autoComplete="street-address" />
            <p className="field-error">{fieldError(error, "default_address")}</p>
          </div>
        )}
        <FormError message={error && !error.fields.length ? error.message : null} />
        {saved && <p className="notice notice-good" role="status">Profile saved.</p>}
        <button className="btn" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button>
      </form>
    </section>
  );
}
