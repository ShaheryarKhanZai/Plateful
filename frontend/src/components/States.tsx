import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { ApiError } from "../api/client";

export function Loading({ label = "Loading", skeleton }: { label?: string; skeleton?: "cards" }) {
  if (skeleton === "cards") {
    return (
      <div role="status">
        <span className="sr-only">{label}…</span>
        <div className="cards" aria-hidden="true">
          {[0, 1, 2, 3].map((i) => <div key={i} className="card skeleton" />)}
        </div>
      </div>
    );
  }
  return <p className="state state-loading" role="status"><span className="spinner" aria-hidden="true" />{label}…</p>;
}

export function ErrorState({ error, onRetry }: { error: ApiError | Error; onRetry?: () => void }) {
  return (
    <div className="state state-error" role="alert">
      <p className="state-title">We couldn't load this</p>
      <p>{error.message}</p>
      {onRetry && <button className="btn btn-quiet" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: { to: string; label: string } }) {
  return (
    <div className="state state-empty">
      <p className="state-title">{title}</p>
      {children && <p>{children}</p>}
      {action && <Link className="btn" to={action.to}>{action.label}</Link>}
    </div>
  );
}

/** Inline form-level error. */
export function FormError({ message }: { message?: string | null }) {
  return message ? <p className="form-error" role="alert">{message}</p> : null;
}
