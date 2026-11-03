import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { apiError, loggedIn, mockApi, order, renderApp, staff } from "./utils";

describe("staff orders", () => {
  it("lists incoming orders and updates a status", async () => {
    const { calls } = mockApi({
      "POST /auth/refresh": loggedIn(staff),
      "GET /staff/orders": { json: [order()] },
      "PATCH /staff/orders/o1/status": { json: order({ status: "confirmed", updated_at: "2026-10-28T10:05:00Z" }) },
    });
    renderApp("/staff");
    const card = (await screen.findByText("Ava Sample")).closest("li")!;
    expect(within(card).getByText("2 × Margherita")).toBeInTheDocument();

    await userEvent.click(within(card).getByRole("button", { name: /confirm order/i }));
    expect(await within(card).findByRole("button", { name: /start preparing/i })).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ status: "confirmed" });
  });

  it("only offers the next valid steps", async () => {
    mockApi({ "POST /auth/refresh": loggedIn(staff), "GET /staff/orders": { json: [order({ status: "preparing" })] } });
    renderApp("/staff");
    const card = (await screen.findByText("Ava Sample")).closest("li")!;
    expect(within(card).getByRole("button", { name: /send out for delivery/i })).toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: /cancel order/i })).not.toBeInTheDocument();
  });

  it("shows the server's message if a change is rejected", async () => {
    mockApi({
      "POST /auth/refresh": loggedIn(staff),
      "GET /staff/orders": { json: [order()] },
      "PATCH /staff/orders/o1/status": apiError(409, "invalid_transition", "An order that is 'cancelled' can't be changed to 'confirmed'."),
    });
    renderApp("/staff");
    await userEvent.click(await screen.findByRole("button", { name: /confirm order/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/can't be changed/i);
  });

  it("shows an empty state, and filters by status", async () => {
    mockApi({ "POST /auth/refresh": loggedIn(staff), "GET /staff/orders": { json: [order({ status: "delivered" })] } });
    renderApp("/staff");
    expect(await screen.findByText(/no active orders/i)).toBeInTheDocument();   // delivered is hidden under "Active"
    await userEvent.click(screen.getByRole("button", { name: "Delivered" }));
    expect(await screen.findByText("Ava Sample")).toBeInTheDocument();
  });
});
