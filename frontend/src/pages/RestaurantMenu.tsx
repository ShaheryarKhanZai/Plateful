import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { MenuItem } from "../api/types";
import { ErrorState, Loading } from "../components/States";
import { Stepper } from "../components/Stepper";
import { useCart } from "../context/CartContext";
import { centsToMoney, money } from "../format";
import { useFetch } from "../hooks";
import { cuisineEmoji, itemEmoji, themeFor } from "../visuals";

export default function RestaurantMenu() {
  const { id = "" } = useParams();
  const { data, error, loading, reload } = useFetch(() => api.menu(id), [id]);
  const { cart, add, startNewCart, setQty, totalCents, count } = useCart();
  const [conflict, setConflict] = useState<MenuItem | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // The little "Added" message disappears by itself.
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 1800);
    return () => clearTimeout(t);
  }, [toast]);

  if (loading) return <Loading label="Loading menu" />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return null;

  const { restaurant, items } = data;
  const theme = themeFor(restaurant.name, restaurant.cuisine);
  const here = cart?.restaurantId === restaurant.id ? cart : null;
  const qtyOf = (itemId: string) => here?.lines.find((l) => l.id === itemId)?.qty ?? 0;

  const tryAdd = (item: MenuItem) => {
    if (add(restaurant, item) === "other_restaurant") setConflict(item);
    else setToast(`${item.name} added`);
  };

  return (
    <>
      <header className="banner" style={{ background: theme.gradient }}>
        <div className="banner-copy">
          <Link to="/" className="crumb-light">All restaurants</Link>
          <h1>{restaurant.name}</h1>
          <div className="banner-meta">
            <span className="chip-light">{restaurant.cuisine}</span>
            <span className={restaurant.is_open ? "pill pill-open" : "pill pill-closed"}>{restaurant.is_open ? "Open" : "Closed"}</span>
          </div>
          <p>{restaurant.description}</p>
        </div>
        <span className="banner-emoji" aria-hidden="true">{cuisineEmoji(restaurant.cuisine)}</span>
      </header>

      {!restaurant.is_open && <p className="notice">This restaurant is closed right now, so you can look but not order.</p>}
      {conflict && (
        <div className="notice" role="alert">
          <p>Your cart has items from {cart?.restaurantName}. A cart can only hold one restaurant at a time.</p>
          <div className="btn-row">
            <button className="btn" onClick={() => { startNewCart(restaurant, conflict); setConflict(null); setToast(`${conflict.name} added`); }}>Start a new cart</button>
            <button className="btn btn-quiet" onClick={() => setConflict(null)}>Keep my current cart</button>
          </div>
        </div>
      )}

      <div className="menu-layout">
        <ul className="menu-list" aria-label="Menu">
          {items.map((item) => {
            const qty = qtyOf(item.id);
            return (
              <li key={item.id} className={item.is_available ? "menu-item" : "menu-item unavailable"}>
                <span className="item-emoji" style={{ background: theme.tint }} aria-hidden="true">{itemEmoji(item.name, restaurant.cuisine)}</span>
                <div className="item-text">
                  <h2 className="item-name">{item.name}</h2>
                  <p className="muted">{item.description}</p>
                  <span className="price">{money(item.price)}</span>
                </div>
                <div className="item-side">
                  {!item.is_available ? <span className="muted">Unavailable</span>
                    : !restaurant.is_open ? null
                    : qty > 0 ? <Stepper qty={qty} name={item.name} onChange={(q) => setQty(item.id, q)} />
                    : <button className="btn btn-small btn-add" onClick={() => tryAdd(item)} aria-label={`Add ${item.name} to cart`}>Add</button>}
                </div>
              </li>
            );
          })}
        </ul>

        <aside className="panel" aria-label="Your order">
          <h2>Your order</h2>
          {!here ? <p className="muted">Nothing yet. Tap Add on anything that looks good.</p> : (
            <>
              <ul className="summary">
                {here.lines.map((l) => (
                  <li key={l.id}><span>{l.qty} × {l.name}</span><span>{centsToMoney(Number(l.price) * 100 * l.qty)}</span></li>
                ))}
              </ul>
              <p className="summary-total"><span>Estimated total</span><strong>{centsToMoney(totalCents)}</strong></p>
              <Link to="/cart" className="btn btn-block">Review cart ({count})</Link>
            </>
          )}
        </aside>
      </div>

      {here && (
        <Link to="/cart" className="cart-bar">
          <span className="cart-bar-count">{count}</span>
          <span>View cart</span>
          <span className="cart-bar-total">{centsToMoney(totalCents)}</span>
        </Link>
      )}
      {toast && <p className="toast" role="status">{toast}</p>}
    </>
  );
}
