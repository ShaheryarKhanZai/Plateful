import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import App from "../App";
import { AuthProvider } from "../context/AuthContext";
import { CartProvider } from "../context/CartContext";
import type { MenuItem, Order, Restaurant, User } from "../api/types";

export interface Req { method: string; path: string; body: any; headers: Record<string, string> }
export type Reply = { status?: number; json?: unknown };
export type Routes = Record<string, Reply | ((req: Req) => Reply)>;

/** Replaces fetch with a fake server. Keys look like "GET /restaurants". */
export function mockApi(routes: Routes) {
  const calls: Req[] = [];
  const fake = vi.fn(async (input: string, init: RequestInit = {}) => {
    const url = new URL(input);
    const req: Req = {
      method: init.method ?? "GET", path: url.pathname,
      body: init.body ? JSON.parse(String(init.body)) : undefined,
      headers: (init.headers ?? {}) as Record<string, string>,
    };
    calls.push(req);
    const handler = routes[`${req.method} ${req.path}`] ?? (req.path === "/auth/refresh" ? { status: 401, json: { error: { code: "invalid_refresh", message: "Please log in again." } } } : undefined);
    if (!handler) throw new Error(`Unmocked request: ${req.method} ${req.path}`);
    const reply = typeof handler === "function" ? handler(req) : handler;
    const status = reply.status ?? 200;
    return new Response(status === 204 ? null : JSON.stringify(reply.json ?? {}), { status, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fake);
  return { calls, fake };
}

export function renderApp(route = "/") {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider><CartProvider><App /></CartProvider></AuthProvider>
    </MemoryRouter>,
  );
}

// ---- fixtures ----
export const customer: User = { id: "u1", email: "ava@example.com", full_name: "Ava Sample", role: "customer", default_address: "12 Example Street" };
export const staff: User = { id: "u2", email: "sam@example.com", full_name: "Sam Staff", role: "staff", default_address: null };
export const loggedIn = (user: User) => ({ status: 200, json: { access_token: "tok", token_type: "bearer", user } });
export const restaurant: Restaurant = { id: "r1", name: "Basil & Brick", cuisine: "Pizza", description: "Wood-fired pizza.", is_open: true };
export const burger: MenuItem = { id: "m1", name: "Margherita", description: "Tomato, basil", price: "10.50", is_available: true };
export const gone: MenuItem = { id: "m2", name: "Sorbet", description: "Cold", price: "4.25", is_available: false };
export const menuReply = { json: { restaurant, items: [burger, gone] } };
export const order = (over: Partial<Order> = {}): Order => ({
  id: "o1", status: "pending", total: "21.00", delivery_address: "12 Example Street", note: null, payment_method: "mock_cash",
  restaurant_id: "r1", restaurant_name: "Basil & Brick", created_at: "2026-10-28T10:00:00Z", updated_at: "2026-10-28T10:00:00Z",
  items: [{ item_name: "Margherita", unit_price: "10.50", quantity: 2, line_total: "21.00" }], customer_name: "Ava Sample", ...over,
});
export const apiError = (status: number, code: string, message: string, fields: unknown[] = []) =>
  ({ status, json: { error: { code, message, fields } } });
