import { Link } from "react-router-dom";
import { api } from "../api/client";
import { EmptyState, ErrorState, Loading } from "../components/States";
import { StatusBadge } from "../components/StatusBadge";
import { money, when } from "../format";
import { useFetch } from "../hooks";

export default function Orders() {
  const { data, error, loading, reload } = useFetch(api.myOrders, []);
  return (
    <>
      <h1>My orders</h1>
      {loading && <Loading label="Loading your orders" />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {data && data.length === 0 && (
        <EmptyState title="No orders yet" action={{ to: "/", label: "Find something to eat" }}>Your orders will show up here.</EmptyState>
      )}
      {data && data.length > 0 && (
        <ul className="rows">
          {data.map((o) => (
            <li key={o.id}>
              <Link to={`/orders/${o.id}`} className="row">
                <span className="row-main">
                  <span className="row-title">{o.restaurant_name}</span>
                  <span className="row-meta">{when(o.created_at)}</span>
                  <span className="muted">{o.items.map((i) => `${i.quantity} × ${i.item_name}`).join(", ")}</span>
                </span>
                <span className="row-end"><StatusBadge status={o.status} /><strong>{money(o.total)}</strong></span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
