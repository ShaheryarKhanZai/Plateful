import { useState } from "react";
import { api, ApiError } from "../api/client";
import type { Order, OrderStatus } from "../api/types";
import { EmptyState, ErrorState, Loading } from "../components/States";
import { StatusBadge } from "../components/StatusBadge";
import { ACTION_LABEL, NEXT_STATUSES, money, when } from "../format";
import { useFetch, useInterval } from "../hooks";

type Filter = "active" | OrderStatus | "all";
const FILTERS: { value: Filter; label: string }[] = [
  { value: "active", label: "Active" }, { value: "pending", label: "New" },
  { value: "confirmed", label: "Confirmed" }, { value: "preparing", label: "Preparing" },
  { value: "out_for_delivery", label: "On the way" }, { value: "delivered", label: "Delivered" },
  { value: "cancelled", label: "Cancelled" }, { value: "all", label: "All" },
];

export default function StaffOrders() {
  const { data, error, loading, reload, refreshQuietly } = useFetch(api.staffOrders, []);
  const [filter, setFilter] = useState<Filter>("active");
  const [overrides, setOverrides] = useState<Record<string, Order>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  useInterval(refreshQuietly, 15000);  // pick up new orders automatically

  if (loading) return <Loading label="Loading incoming orders" />;
  if (error) return <ErrorState error={error} onRetry={reload} />;

  const orders = (data ?? []).map((o) => overrides[o.id] && overrides[o.id].updated_at >= o.updated_at ? overrides[o.id] : o);
  const count = (s: OrderStatus) => orders.filter((o) => o.status === s).length;
  const shown = orders.filter((o) =>
    filter === "all" ? true : filter === "active" ? !["delivered", "cancelled"].includes(o.status) : o.status === filter);

  async function change(order: Order, status: OrderStatus) {
    setBusyId(order.id);
    setErrors((e) => ({ ...e, [order.id]: "" }));
    try {
      const updated = await api.setOrderStatus(order.id, status);
      setOverrides((o) => ({ ...o, [order.id]: updated }));
    } catch (e) {
      setErrors((x) => ({ ...x, [order.id]: e instanceof ApiError ? e.message : "Couldn't update the order." }));
      refreshQuietly();  // the order may have changed under us
    } finally { setBusyId(null); }
  }

  return (
    <>
      <h1>Incoming orders</h1>
      <div className="stats" aria-label="Order counts">
        <div className="stat stat-new"><strong>{count("pending")}</strong><span>New</span></div>
        <div className="stat stat-cook"><strong>{count("confirmed") + count("preparing")}</strong><span>In the kitchen</span></div>
        <div className="stat stat-go"><strong>{count("out_for_delivery")}</strong><span>Out for delivery</span></div>
        <div className="stat stat-done"><strong>{count("delivered")}</strong><span>Completed</span></div>
      </div>
      <div className="filters" role="group" aria-label="Filter by status">
        {FILTERS.map((f) => (
          <button key={f.value} className={filter === f.value ? "chip chip-on" : "chip"} aria-pressed={filter === f.value}
                  onClick={() => setFilter(f.value)}>{f.label}</button>
        ))}
        <button className="btn btn-quiet btn-small" onClick={reload}>Refresh</button>
      </div>

      {shown.length === 0 ? (
        <EmptyState title={filter === "active" ? "No active orders" : "No orders here"}>
          New orders appear automatically.
        </EmptyState>
      ) : (
        <ul className="staff-list">
          {shown.map((o) => (
            <li key={o.id} className={`staff-order status-${o.status}`}>
              <div className="staff-top">
                <div>
                  <h2 className="item-name">{o.customer_name}</h2>
                  <p className="row-meta">{o.restaurant_name}, {when(o.created_at)}</p>
                </div>
                <StatusBadge status={o.status} />
              </div>
              <ul className="summary">
                {o.items.map((i) => <li key={i.item_name}><span>{i.quantity} × {i.item_name}</span><span>{money(i.line_total)}</span></li>)}
              </ul>
              <p className="muted small">Deliver to: {o.delivery_address}{o.note ? `. Note: ${o.note}` : ""}</p>
              <div className="staff-actions">
                <strong>{money(o.total)}</strong>
                <div className="btn-row">
                  {NEXT_STATUSES[o.status].map((s) => (
                    <button key={s} className={s === "cancelled" ? "btn btn-danger btn-small" : "btn btn-small"}
                            disabled={busyId === o.id} onClick={() => change(o, s)}>{ACTION_LABEL[s]}</button>
                  ))}
                </div>
              </div>
              {errors[o.id] && <p className="form-error" role="alert">{errors[o.id]}</p>}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
