import type { OrderStatus } from "./api/types";

const fmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
/** For DISPLAY only. The server is the source of truth for every amount. */
export const money = (value: string | number) => fmt.format(Number(value));
export const toCents = (price: string) => Math.round(Number(price) * 100);
export const centsToMoney = (cents: number) => fmt.format(cents / 100);

export const STATUS_LABEL: Record<OrderStatus, string> = {
  pending: "Waiting for restaurant", confirmed: "Confirmed", preparing: "Being prepared",
  out_for_delivery: "On the way", delivered: "Delivered", cancelled: "Cancelled",
};
export const STATUS_FLOW: OrderStatus[] = ["pending", "confirmed", "preparing", "out_for_delivery", "delivered"];
export const FINAL: OrderStatus[] = ["delivered", "cancelled"];
/** Usability only: the backend enforces the real rules. */
export const NEXT_STATUSES: Record<OrderStatus, OrderStatus[]> = {
  pending: ["confirmed", "cancelled"], confirmed: ["preparing", "cancelled"],
  preparing: ["out_for_delivery"], out_for_delivery: ["delivered"], delivered: [], cancelled: [],
};
export const ACTION_LABEL: Record<OrderStatus, string> = {
  pending: "Reset", confirmed: "Confirm order", preparing: "Start preparing",
  out_for_delivery: "Send out for delivery", delivered: "Mark delivered", cancelled: "Cancel order",
};

export const when = (iso: string) =>
  new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
