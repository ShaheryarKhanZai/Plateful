import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { burger, menuReply, mockApi, renderApp, restaurant } from "./utils";

describe("browsing restaurants", () => {
  it("shows a loading state, then the restaurants", async () => {
    mockApi({ "GET /restaurants": { json: [restaurant, { ...restaurant, id: "r2", name: "Closed Place", is_open: false }] } });
    renderApp("/");
    expect(screen.getByRole("status")).toHaveTextContent(/finding kitchens/i);
    expect(await screen.findByText("Basil & Brick")).toBeInTheDocument();
    expect(screen.getByText("Closed")).toBeInTheDocument();
  });

  it("shows an empty state when there are no restaurants", async () => {
    mockApi({ "GET /restaurants": { json: [] } });
    renderApp("/");
    expect(await screen.findByText(/no restaurants yet/i)).toBeInTheDocument();
  });

  it("shows a readable error and lets you retry", async () => {
    let attempt = 0;
    const { fake } = mockApi({ "GET /restaurants": () => (++attempt === 1 ? { status: 500, json: { error: { code: "server_error", message: "Something went wrong. Please try again." } } } : { json: [restaurant] }) });
    renderApp("/");
    expect(await screen.findByRole("alert")).toHaveTextContent(/something went wrong/i);
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Basil & Brick")).toBeInTheDocument();
    expect(fake).toHaveBeenCalled();
  });

  it("explains when the backend can't be reached", async () => {
    const { fake } = mockApi({});
    fake.mockRejectedValue(new TypeError("Failed to fetch"));
    renderApp("/");
    expect(await screen.findByRole("alert")).toHaveTextContent(/can't reach the server/i);
  });
});

describe("finding a kitchen", () => {
  const list = [restaurant, { ...restaurant, id: "r2", name: "Noodle Lantern", cuisine: "Pan-Asian", description: "Hand-pulled noodles." }];

  it("filters by cuisine chip", async () => {
    mockApi({ "GET /restaurants": { json: list } });
    renderApp("/");
    await screen.findByText("Basil & Brick");
    await userEvent.click(screen.getByRole("button", { name: "Pan-Asian" }));
    expect(screen.queryByText("Basil & Brick")).not.toBeInTheDocument();
    expect(screen.getByText("Noodle Lantern")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "All" }));
    expect(screen.getByText("Basil & Brick")).toBeInTheDocument();
  });

  it("searches by name, and offers a way out when nothing matches", async () => {
    mockApi({ "GET /restaurants": { json: list } });
    renderApp("/");
    await screen.findByText("Basil & Brick");
    const box = screen.getByRole("searchbox", { name: /search restaurants/i });
    await userEvent.type(box, "noodle");
    expect(screen.queryByText("Basil & Brick")).not.toBeInTheDocument();
    await userEvent.clear(box);
    await userEvent.type(box, "zzz");
    expect(await screen.findByText(/no kitchens match that/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /clear filters/i }));
    expect(await screen.findByText("Basil & Brick")).toBeInTheDocument();
  });
});

describe("menu and cart", () => {
  it("adds items, changes quantity and removes them", async () => {
    mockApi({ "GET /restaurants/r1/menu": menuReply });
    renderApp("/restaurants/r1");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: /add margherita to cart/i }));
    expect(screen.getByText("1 × Margherita")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /add one margherita/i }));
    expect(screen.getByText("2 × Margherita")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();  // unavailable items can't be added

    await user.click(screen.getByRole("link", { name: /review cart/i }));
    expect(await screen.findByRole("heading", { name: /your cart/i })).toBeInTheDocument();
    expect(screen.getByText("$21.00", { selector: "strong" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /remove one margherita/i }));
    expect(screen.getByText("$10.50", { selector: "strong" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^remove margherita$/i }));
    expect(await screen.findByText(/your cart is empty/i)).toBeInTheDocument();
  });

  it("asks before replacing a cart from another restaurant", async () => {
    sessionStorage.setItem("plateful.cart", JSON.stringify({ restaurantId: "other", restaurantName: "Noodle Lantern",
      lines: [{ id: "x", name: "Noodles", price: "11.00", qty: 1 }] }));
    mockApi({ "GET /restaurants/r1/menu": menuReply });
    renderApp("/restaurants/r1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /add margherita to cart/i }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/noodle lantern/i);
    await user.click(within(alert).getByRole("button", { name: /start a new cart/i }));
    await waitFor(() => expect(screen.getByText("1 × Margherita")).toBeInTheDocument());
    expect(burger.price).toBe("10.50");
  });

  it("does not allow ordering from a closed restaurant", async () => {
    mockApi({ "GET /restaurants/r1/menu": { json: { restaurant: { ...restaurant, is_open: false }, items: [burger] } } });
    renderApp("/restaurants/r1");
    expect(await screen.findByText(/is closed right now/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /add margherita/i })).not.toBeInTheDocument();
  });
});
