import type { OrderStatus } from "../api/types";
import { STATUS_FLOW, STATUS_LABEL } from "../format";

export function StatusBadge({ status }: { status: OrderStatus }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABEL[status]}</span>;
}

/** The signature element: a rail that shows how far the order has travelled. */
export function OrderTracker({ status }: { status: OrderStatus }) {
  if (status === "cancelled") {
    return <p className="tracker-cancelled" role="status">This order was cancelled.</p>;
  }
  const current = STATUS_FLOW.indexOf(status);
  return (
    <ol className="tracker" aria-label={`Order progress: ${STATUS_LABEL[status]}`}>
      {STATUS_FLOW.map((s, i) => (
        <li key={s} className={i < current ? "done" : i === current ? "current" : ""} aria-current={i === current ? "step" : undefined}>
          {i === current && <span className="rider" aria-hidden="true">{s === "delivered" ? "🎉" : s === "out_for_delivery" ? "🛵" : "🍳"}</span>}
          <span className="node" aria-hidden="true" />
          <span className="tracker-label">{STATUS_LABEL[s]}</span>
        </li>
      ))}
    </ol>
  );
}
