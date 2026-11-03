import { useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Order } from "../api/types";
import { ErrorState, FormError, Loading } from "../components/States";
import { OrderTracker, StatusBadge } from "../components/StatusBadge";
import { FINAL, money, when } from "../format";
import { useFetch, useInterval } from "../hooks";

export default function OrderDetail() {
  const { id = "" } = useParams();
  const placed = (useLocation().state as { placed?: boolean } | null)?.placed;
  const { data, error, loading, reload, refreshQuietly } = useFetch(() => api.myOrder(id), [id]);
  const [cancelled, setCancelled] = useState<Order | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const order = cancelled ?? data;
  // Check for status changes every 8 seconds until the order is finished.
  useInterval(refreshQuietly, 8000, !!order && !FINAL.includes(order.status));

  if (loading) return <Loading label="Loading order" />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!order) return null;

  async function cancel() {
    setBusy(true); setCancelError(null);
    try { setCancelled(await api.cancelOrder(order!.id)); }
    catch (e) { setCancelError(e instanceof ApiError ? e.message : "Couldn't cancel the order."); reload(); }
    finally { setBusy(false); }
  }

  const live = cancelled && data && data.status !== "pending" ? data : cancelled ?? data!;
  return (
    <>
      <p className="crumb"><Link to="/orders">My orders</Link></p>
      {placed && live.status === "pending" && <p className="notice notice-good" role="status">Order placed. The restaurant will confirm it shortly.</p>}
      <header className="menu-head">
        <h1>{live.restaurant_name}</h1>
        <p className="row-meta">Ordered {when(live.created_at)}</p>
        <StatusBadge status={live.status} />
      </header>
      <div className="tracker-card"><OrderTracker status={live.status} /></div>

      <section className="panel receipt" aria-label="Order details">
        <ul className="summary">
          {live.items.map((i) => (
            <li key={i.item_name}><span>{i.quantity} × {i.item_name}</span><span>{money(i.line_total)}</span></li>
          ))}
        </ul>
        <p className="summary-total"><span>Total</span><strong>{money(live.total)}</strong></p>
        <dl className="facts">
          <dt>Delivering to</dt><dd>{live.delivery_address}</dd>
          {live.note && (<><dt>Your note</dt><dd>{live.note}</dd></>)}
          <dt>Payment</dt><dd>{live.payment_method === "mock_cash" ? "Cash on delivery" : "Card"}</dd>
        </dl>
        <FormError message={cancelError} />
        {live.status === "pending" && (
          <button className="btn btn-danger" onClick={cancel} disabled={busy}>{busy ? "Cancelling…" : "Cancel order"}</button>
        )}
      </section>
    </>
  );
}
