// Money arrives from the API as strings like "8.50" (exact decimals, no float rounding).
export type Role = "customer" | "staff";
export type OrderStatus =
  | "pending" | "confirmed" | "preparing" | "out_for_delivery" | "delivered" | "cancelled";

export interface User {
  id: string; email: string; full_name: string; role: Role; default_address: string | null;
}
export interface AuthResponse { access_token: string; token_type: string; user: User }
export interface Restaurant {
  id: string; name: string; description: string; cuisine: string; is_open: boolean;
}
export interface MenuItem {
  id: string; name: string; description: string; price: string; is_available: boolean;
}
export interface Menu { restaurant: Restaurant; items: MenuItem[] }
export interface OrderItem { item_name: string; unit_price: string; quantity: number; line_total: string }
export interface Order {
  id: string; status: OrderStatus; total: string; delivery_address: string; note: string | null;
  payment_method: string; restaurant_id: string; restaurant_name: string;
  created_at: string; updated_at: string; items: OrderItem[]; customer_name?: string;
}
export interface PlaceOrderInput {
  restaurant_id: string;
  items: { menu_item_id: string; quantity: number }[];
  delivery_address: string; note?: string | null; payment_method: "mock_cash" | "mock_card";
}
