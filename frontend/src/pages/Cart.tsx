import { Link } from "react-router-dom";
import { EmptyState } from "../components/States";
import { Stepper } from "../components/Stepper";
import { useCart } from "../context/CartContext";
import { centsToMoney, money, toCents } from "../format";
import { itemEmoji } from "../visuals";

export default function Cart() {
  const { cart, setQty, totalCents, clear } = useCart();
  if (!cart) {
    return (
      <>
        <h1>Your cart</h1>
        <EmptyState title="Your cart is empty" action={{ to: "/", label: "Browse restaurants" }}>
          Pick a restaurant and add a few things.
        </EmptyState>
      </>
    );
  }
  return (
    <>
      <h1>Your cart</h1>
      <p className="muted">From <Link to={`/restaurants/${cart.restaurantId}`}>{cart.restaurantName}</Link></p>
      <ul className="cart-lines">
        {cart.lines.map((l) => (
          <li key={l.id} className="cart-line">
            <div className="cart-item">
              <span className="item-emoji" aria-hidden="true">{itemEmoji(l.name, cart.restaurantName)}</span>
              <div><h2 className="item-name">{l.name}</h2><p className="muted">{money(l.price)} each</p></div>
            </div>
            <Stepper qty={l.qty} name={l.name} onChange={(q) => setQty(l.id, q)} />
            <span className="price">{centsToMoney(toCents(l.price) * l.qty)}</span>
            <button className="btn btn-quiet btn-small" onClick={() => setQty(l.id, 0)} aria-label={`Remove ${l.name}`}>Remove</button>
          </li>
        ))}
      </ul>
      <div className="totals">
        <p className="summary-total"><span>Estimated total</span><strong>{centsToMoney(totalCents)}</strong></p>
        <p className="muted small">The restaurant's current prices are applied when you place the order.</p>
        <div className="btn-row">
          <Link to="/checkout" className="btn">Continue to checkout</Link>
          <button className="btn btn-quiet" onClick={clear}>Empty cart</button>
        </div>
      </div>
    </>
  );
}
