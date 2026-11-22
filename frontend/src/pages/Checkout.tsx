import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { EmptyState, FormError } from "../components/States";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import { centsToMoney } from "../format";
import { fieldError } from "../hooks";

export default function Checkout() {
  const { user } = useAuth();
  const { cart, totalCents, clear } = useCart();
  const navigate = useNavigate();
  const [address, setAddress] = useState(user?.default_address ?? "");
  const [note, setNote] = useState("");
  const [payment, setPayment] = useState<"mock_cash" | "mock_card">("mock_cash");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  if (!cart) {
    return <EmptyState title="Nothing to check out" action={{ to: "/", label: "Browse restaurants" }}>Your cart is empty.</EmptyState>;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || !cart) return;
    setBusy(true);
    setError(null);
    try {
      const order = await api.placeOrder({
        restaurant_id: cart.restaurantId,
        // Only IDs and quantities are sent. The server looks up the real prices.
        items: cart.lines.map((l) => ({ menu_item_id: l.id, quantity: l.qty })),
        delivery_address: address, note: note.trim() || null, payment_method: payment,
      });
      clear();
      navigate(`/orders/${order.id}`, { state: { placed: true } });
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, "error", "Something went wrong."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Checkout</h1>
      <div className="checkout">
        <form onSubmit={submit} noValidate>
          <div className="field">
            <label htmlFor="address">Delivery address</label>
            <input id="address" value={address} onChange={(e) => setAddress(e.target.value)} autoComplete="street-address"
                   aria-invalid={!!fieldError(error, "delivery_address")} aria-describedby="address-err" required />
            <p id="address-err" className="field-error">{fieldError(error, "delivery_address")}</p>
          </div>
          <div className="field">
            <label htmlFor="note">Note for the restaurant <span className="muted">(optional)</span></label>
            <input id="note" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} />
          </div>

          <fieldset className="field mock">
            <legend>Payment (mock feature)</legend>
            <p className="muted small">Demo only. No payment is taken and no card details are collected. Never type real card details into this app.</p>
            <label className="radio"><input type="radio" name="payment" checked={payment === "mock_cash"} onChange={() => setPayment("mock_cash")} /> Pay on delivery (mock)</label>
            <label className="radio"><input type="radio" name="payment" checked={payment === "mock_card"} onChange={() => setPayment("mock_card")} /> Card (mock, nothing to enter)</label>
          </fieldset>

          <FormError message={error && !error.fields.length ? error.message : error ? "Please fix the highlighted field." : null} />
          <button className="btn btn-large" disabled={busy}>{busy ? "Placing order…" : `Place order · ${centsToMoney(totalCents)}`}</button>
        </form>

        <aside className="panel" aria-label="Order summary">
          <h2>{cart.restaurantName}</h2>
          <ul className="summary">
            {cart.lines.map((l) => <li key={l.id}><span>{l.qty} × {l.name}</span></li>)}
          </ul>
          <p className="summary-total"><span>Estimated total</span><strong>{centsToMoney(totalCents)}</strong></p>
          <Link to="/cart" className="muted small">Change items</Link>
        </aside>
      </div>
    </>
  );
}
