/**
 * The only file that talks to the backend.
 *
 * Tokens: the short-lived ACCESS token lives only in this variable (JavaScript memory),
 * never in localStorage. The long-lived REFRESH token is an HttpOnly cookie that
 * JavaScript cannot read; the browser sends it automatically to /auth/refresh.
 * After a page reload the access token is gone, so the app silently asks for a new one.
 */
import type { AuthResponse, Menu, Order, PlaceOrderInput, OrderStatus, Restaurant, User } from "./types";

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string,
              public fields: { field: string; message: string }[] = []) {
    super(message);
  }
}

let accessToken: string | null = null;
let onSessionLost: () => void = () => {};
export const setAccessToken = (t: string | null) => { accessToken = t; };
export const setSessionLostHandler = (fn: () => void) => { onSessionLost = fn; };

let refreshInFlight: Promise<AuthResponse | null> | null = null;

/** One refresh at a time: refresh tokens are single-use, so parallel calls would clash. */
export function refreshSession(): Promise<AuthResponse | null> {
  refreshInFlight ??= (async () => {
    try {
      const res = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST", credentials: "include", headers: { "X-Requested-With": "fetch" },
      });
      if (!res.ok) { accessToken = null; return null; }
      const data = (await res.json()) as AuthResponse;
      accessToken = data.access_token;
      return data;
    } catch {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

async function toError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const e = body.error;
    return new ApiError(res.status, e?.code ?? "error", e?.message ?? "Something went wrong.", e?.fields ?? []);
  } catch {
    return new ApiError(res.status, "error", "Something went wrong. Please try again.");
  }
}

interface Options { method?: string; body?: unknown; auth?: boolean }

async function request<T>(path: string, { method = "GET", body, auth = true }: Options = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method, headers, credentials: "include",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "network", "Can't reach the server. Check that the backend is running.");
  }
  if (res.status === 401 && auth && !retried) {
    if (await refreshSession()) return request<T>(path, { method, body, auth }, true);
    onSessionLost();
  }
  if (!res.ok) throw await toError(res);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  register: (b: { email: string; password: string; full_name: string }) =>
    request<AuthResponse>("/auth/register", { method: "POST", body: b, auth: false }),
  login: (b: { email: string; password: string }) =>
    request<AuthResponse>("/auth/login", { method: "POST", body: b, auth: false }),
  logout: async () => {
    try {
      await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include",
                                              headers: { "X-Requested-With": "fetch" } });
    } finally { accessToken = null; }
  },
  updateProfile: (b: { full_name?: string; default_address?: string }) =>
    request<User>("/auth/me", { method: "PATCH", body: b }),
  restaurants: () => request<Restaurant[]>("/restaurants", { auth: false }),
  menu: (id: string) => request<Menu>(`/restaurants/${id}/menu`, { auth: false }),
  placeOrder: (b: PlaceOrderInput) => request<Order>("/orders", { method: "POST", body: b }),
  myOrders: () => request<Order[]>("/orders"),
  myOrder: (id: string) => request<Order>(`/orders/${id}`),
  cancelOrder: (id: string) => request<Order>(`/orders/${id}/cancel`, { method: "POST" }),
  staffOrders: () => request<Order[]>("/staff/orders"),
  setOrderStatus: (id: string, status: OrderStatus) =>
    request<Order>(`/staff/orders/${id}/status`, { method: "PATCH", body: { status } }),
};
