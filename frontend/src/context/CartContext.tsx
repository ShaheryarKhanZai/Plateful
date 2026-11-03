import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { MenuItem } from "../api/types";
import { toCents } from "../format";

export interface CartLine { id: string; name: string; price: string; qty: number }
interface Cart { restaurantId: string; restaurantName: string; lines: CartLine[] }
interface CartValue {
  cart: Cart | null; count: number; totalCents: number;
  add: (restaurant: { id: string; name: string }, item: MenuItem) => "ok" | "other_restaurant";
  startNewCart: (restaurant: { id: string; name: string }, item: MenuItem) => void;
  setQty: (id: string, qty: number) => void;
  clear: () => void;
}
const KEY = "plateful.cart";
const MAX_QTY = 20;
const CartContext = createContext<CartValue | null>(null);

// The cart is not sensitive (item IDs and quantities), so sessionStorage is fine here.
// The server re-checks every price and item when you place the order anyway.
function load(): Cart | null {
  try { return JSON.parse(sessionStorage.getItem(KEY) ?? "null"); } catch { return null; }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [cart, setCart] = useState<Cart | null>(load);
  useEffect(() => {
    try { cart ? sessionStorage.setItem(KEY, JSON.stringify(cart)) : sessionStorage.removeItem(KEY); } catch { /* storage unavailable */ }
  }, [cart]);

  const line = (item: MenuItem): CartLine => ({ id: item.id, name: item.name, price: item.price, qty: 1 });

  const add: CartValue["add"] = useCallback((r, item) => {
    let result: "ok" | "other_restaurant" = "ok";
    setCart((c) => {
      if (c && c.restaurantId !== r.id && c.lines.length > 0) { result = "other_restaurant"; return c; }
      if (!c || c.restaurantId !== r.id) return { restaurantId: r.id, restaurantName: r.name, lines: [line(item)] };
      const existing = c.lines.find((l) => l.id === item.id);
      return { ...c, lines: existing
        ? c.lines.map((l) => (l.id === item.id ? { ...l, qty: Math.min(MAX_QTY, l.qty + 1) } : l))
        : [...c.lines, line(item)] };
    });
    return result;
  }, []);

  const startNewCart: CartValue["startNewCart"] = useCallback((r, item) =>
    setCart({ restaurantId: r.id, restaurantName: r.name, lines: [line(item)] }), []);

  const setQty = useCallback((id: string, qty: number) =>
    setCart((c) => {
      if (!c) return c;
      const lines = c.lines.flatMap((l) => (l.id !== id ? [l] : qty <= 0 ? [] : [{ ...l, qty: Math.min(MAX_QTY, qty) }]));
      return lines.length ? { ...c, lines } : null;
    }), []);

  const clear = useCallback(() => setCart(null), []);
  const count = cart?.lines.reduce((n, l) => n + l.qty, 0) ?? 0;
  const totalCents = cart?.lines.reduce((n, l) => n + toCents(l.price) * l.qty, 0) ?? 0;

  const value = useMemo(() => ({ cart, count, totalCents, add, startNewCart, setQty, clear }),
    [cart, count, totalCents, add, startNewCart, setQty, clear]);
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside <CartProvider>");
  return ctx;
}
