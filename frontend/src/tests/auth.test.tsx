import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { apiError, customer, loggedIn, mockApi, order, renderApp, staff } from "./utils";

describe("login", () => {
  it("shows the server's message for wrong credentials", async () => {
    mockApi({ "POST /auth/login": apiError(401, "invalid_credentials", "Incorrect email or password.") });
    renderApp("/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText(/email/i), "ava@example.com");
    await user.type(screen.getByLabelText(/password/i), "wrong-password-1");
    await user.click(screen.getByRole("button", { name: /^log in$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
  });

  it("logs in a customer and shows their name", async () => {
    const { calls } = mockApi({ "POST /auth/login": loggedIn(customer), "GET /restaurants": { json: [] } });
    renderApp("/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText(/email/i), "ava@example.com");
    await user.type(screen.getByLabelText(/password/i), "Correct-horse-9");
    await user.click(screen.getByRole("button", { name: /^log in$/i }));
    expect(await screen.findByRole("link", { name: "Ava Sample" })).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/auth/login")?.body).toEqual({ email: "ava@example.com", password: "Correct-horse-9" });
  });

  it("shows per-field errors on registration", async () => {
    mockApi({ "POST /auth/register": apiError(422, "validation_error", "Some fields are invalid.",
      [{ field: "password", message: "String should have at least 10 characters" }]) });
    renderApp("/register");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText(/full name/i), "Ava");
    await user.type(screen.getByLabelText(/email/i), "ava@example.com");
    await user.type(screen.getByLabelText(/^password/i), "short1");
    await user.click(screen.getByRole("button", { name: /create account/i }));
    expect(await screen.findByText(/at least 10 characters$/i, { selector: ".field-error" })).toBeInTheDocument();
  });

  it("restores the session silently on page load via the refresh cookie", async () => {
    const { calls } = mockApi({ "POST /auth/refresh": loggedIn(customer), "GET /restaurants": { json: [] } });
    renderApp("/");
    expect(await screen.findByRole("link", { name: "Ava Sample" })).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/auth/refresh")?.headers["X-Requested-With"]).toBe("fetch");  // required by the backend's CSRF check
  });
});

describe("route protection", () => {
  it("sends logged-out visitors to the login page", async () => {
    mockApi({});
    renderApp("/orders");
    expect(await screen.findByRole("heading", { name: /log in/i })).toBeInTheDocument();
  });

  it("keeps customers out of the staff page", async () => {
    mockApi({ "POST /auth/refresh": loggedIn(customer), "GET /restaurants": { json: [] } });
    renderApp("/staff");
    expect(await screen.findByRole("heading", { name: /cravings, delivered/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /incoming orders/i })).not.toBeInTheDocument();
  });

  it("shows a customer their orders", async () => {
    mockApi({ "POST /auth/refresh": loggedIn(customer), "GET /orders": { json: [order()] } });
    renderApp("/orders");
    expect(await screen.findByText("Basil & Brick")).toBeInTheDocument();
    expect(screen.getByText("Waiting for restaurant")).toBeInTheDocument();
  });

  it("shows an empty state when a customer has no orders", async () => {
    mockApi({ "POST /auth/refresh": loggedIn(customer), "GET /orders": { json: [] } });
    renderApp("/orders");
    expect(await screen.findByText(/no orders yet/i)).toBeInTheDocument();
  });

  it("lets staff in", async () => {
    mockApi({ "POST /auth/refresh": loggedIn(staff), "GET /staff/orders": { json: [] } });
    renderApp("/staff");
    expect(await screen.findByRole("heading", { name: /incoming orders/i })).toBeInTheDocument();
  });
});
