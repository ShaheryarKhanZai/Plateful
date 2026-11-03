import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { apiError, customer, loggedIn, mockApi, order, renderApp } from "./utils";

beforeEach(() => {
  sessionStorage.setItem("plateful.cart", JSON.stringify({ restaurantId: "r1", restaurantName: "Basil & Brick",
    lines: [{ id: "m1", name: "Margherita", price: "10.50", qty: 2 }] }));
});

describe("checkout", () => {
  it("labels payment as a mock and never asks for card details", async () => {
    mockApi({ "POST /auth/refresh": loggedIn(customer) });
    renderApp("/checkout");
    expect(await screen.findByText(/payment \(mock feature\)/i)).toBeInTheDocument();
    expect(screen.getByText(/never type real card details/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/card number|cvv|expiry/i)).not.toBeInTheDocument();
  });

  it("sends only IDs and quantities, then shows the new order", async () => {
    const { calls } = mockApi({
      "POST /auth/refresh": loggedIn(customer),
      "POST /orders": { status: 201, json: order() },
      "GET /orders/o1": { json: order() },
    });
    renderApp("/checkout");
    const user = userEvent.setup();
    expect(await screen.findByLabelText(/delivery address/i)).toHaveValue("12 Example Street");  // prefilled from profile
    await user.click(screen.getByRole("button", { name: /place order/i }));

    expect(await screen.findByText(/order placed/i)).toBeInTheDocument();
    const sent = calls.find((c) => c.path === "/orders" && c.method === "POST")!;
    expect(sent.body.items).toEqual([{ menu_item_id: "m1", quantity: 2 }]);
    expect(JSON.stringify(sent.body)).not.toMatch(/price|total/i);  // the browser never sends money values
    expect(sent.headers["Authorization"]).toBe("Bearer tok");
    expect(sessionStorage.getItem("plateful.cart")).toBeNull();      // cart cleared after success
  });

  it("shows the server's reason when an item is no longer available, and keeps the cart", async () => {
    mockApi({
      "POST /auth/refresh": loggedIn(customer),
      "POST /orders": apiError(409, "item_unavailable", "No longer available: Margherita."),
    });
    renderApp("/checkout");
    await userEvent.click(await screen.findByRole("button", { name: /place order/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No longer available: Margherita.");
    expect(sessionStorage.getItem("plateful.cart")).not.toBeNull();
  });

  it("shows a field error for a bad address", async () => {
    mockApi({
      "POST /auth/refresh": loggedIn({ ...customer, default_address: null }),
      "POST /orders": apiError(422, "validation_error", "Some fields are invalid.",
        [{ field: "body.delivery_address", message: "String should have at least 5 characters" }]),
    });
    renderApp("/checkout");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText(/delivery address/i), "x");
    await user.click(screen.getByRole("button", { name: /place order/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/fix the highlighted field/i);
  });

  it("lets a customer cancel a pending order", async () => {
    mockApi({
      "POST /auth/refresh": loggedIn(customer),
      "GET /orders/o1": { json: order() },
      "POST /orders/o1/cancel": { json: order({ status: "cancelled" }) },
    });
    renderApp("/orders/o1");
    await userEvent.click(await screen.findByRole("button", { name: /cancel order/i }));
    expect(await screen.findByText(/this order was cancelled/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cancel order/i })).not.toBeInTheDocument();
  });
});
