// F04 admin page rules W1 to W4. Every expected value comes from docs/specs/F04.md.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import AdminPage from "./AdminPage.jsx";

const GENERAL = "Something went wrong. Please try again later.";
const LIVE = "This booking is still live. Decline it first, or wait until the event is over.";

function booking(overrides = {}) {
  return {
    id: 7,
    state: "declined",
    name: "Alice Example",
    email: "alice@example.com",
    phone: "07700 900123",
    guest_count: 40,
    starts_at: "2026-04-01T10:00",
    ends_at: "2026-04-01T14:00",
    details: "Birthday party",
    submitted_at: "2026-03-10T09:05",
    auto_declined: false,
    ...overrides,
  };
}

function erased(overrides = {}) {
  return booking({ name: null, email: null, phone: null, guest_count: null, details: null, ...overrides });
}

function json(status, body) {
  return { status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) };
}

// A stand-in for the admin API: logged in, with the given bookings, and an
// erase route the test can replace.
function startApi(items, eraseRoute) {
  const requests = [];
  const erase = eraseRoute ?? ((id) => [200, erased({ id })]);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (address, options = {}) => {
      const path = new URL(address, "https://centre.example").pathname;
      const request = {
        method: options.method ?? "GET",
        path,
        headers: options.headers ?? {},
        body: options.body === undefined ? undefined : JSON.parse(options.body),
      };
      requests.push(request);
      if (path === "/api/v1/admin/session") return json(200, { email: "admin@centre.example" });
      const match = path.match(/^\/api\/v1\/admin\/bookings\/(\d+)\/erase$/);
      if (match) return json(...erase(Number(match[1])));
      return json(200, { items, page: 1, page_size: 20, total: items.length });
    }),
  );
  return { erasures: () => requests.filter((r) => r.path.endsWith("/erase")) };
}

async function openWith(items, eraseRoute) {
  const api = startApi(items, eraseRoute);
  render(<AdminPage />);
  await screen.findByRole("table");
  return api;
}

function cellsOf(row) {
  // Columns in order (F02 W3): Name, Email, Phone, Guests, Start, End, State,
  // Submitted, Details, Actions.
  const cells = within(row).getAllByRole("cell");
  return { name: cells[0], email: cells[1], phone: cells[2], guests: cells[3], details: cells[8] };
}

function bookingSelect() {
  return screen.getByLabelText("Booking");
}

async function chooseAndPressDelete(user, label) {
  await user.selectOptions(bookingSelect(), label);
  await user.click(screen.getByRole("button", { name: "Delete data" }));
}

beforeEach(() => {
  window.history.pushState({}, "", "/admin");
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, "", "/");
});

describe("W1: an erased booking in the table", () => {
  test("shows Deleted for the name and nothing for the other details", async () => {
    await openWith([erased()]);

    const cells = cellsOf(screen.getAllByRole("row")[1]);
    expect(cells.name).toHaveTextContent(/^Deleted$/);
    expect(cells.email).toBeEmptyDOMElement();
    expect(cells.phone).toBeEmptyDOMElement();
    expect(cells.guests).toBeEmptyDOMElement();
    expect(cells.details).toBeEmptyDOMElement();
  });

  test("still shows its dates and state", async () => {
    await openWith([erased({ state: "accepted" })]);

    const row = within(screen.getAllByRole("row")[1]);
    expect(row.getByText("2026-04-01 10:00")).toBeInTheDocument();
    expect(row.getByText("2026-04-01 14:00")).toBeInTheDocument();
    expect(row.getByText("Accepted")).toBeInTheDocument();
  });

  test("a booking that is not erased shows its name as before", async () => {
    await openWith([booking()]);

    expect(cellsOf(screen.getAllByRole("row")[1]).name).toHaveTextContent(/^Alice Example$/);
  });
});

describe("W2: the Delete client data section", () => {
  test("has a heading, a Booking select and a Delete data button", async () => {
    await openWith([booking()]);

    expect(screen.getByRole("heading", { name: "Delete client data" })).toBeInTheDocument();
    expect(bookingSelect()).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete data" })).toBeInTheDocument();
  });

  test("lists every booking on the page that is not erased, after an empty choice", async () => {
    await openWith([
      booking(),
      booking({ id: 8, name: "Bob Jones", starts_at: "2026-04-02T18:30", state: "accepted" }),
      erased({ id: 9 }),
    ]);

    const options = within(bookingSelect())
      .getAllByRole("option")
      .map((option) => option.textContent);
    expect(options).toEqual([
      "Choose a booking",
      "Alice Example, 2026-04-01 10:00",
      "Bob Jones, 2026-04-02 18:30",
    ]);
  });

  test("the button is disabled until a booking is chosen", async () => {
    await openWith([booking()]);
    const user = userEvent.setup();

    expect(screen.getByRole("button", { name: "Delete data" })).toBeDisabled();

    await user.selectOptions(bookingSelect(), "Alice Example, 2026-04-01 10:00");
    expect(screen.getByRole("button", { name: "Delete data" })).toBeEnabled();
  });

  test.each([
    ["only erased bookings", [erased()]],
    ["no bookings", []],
  ])("with %s it says there is no client data", async (_case, items) => {
    startApi(items);
    render(<AdminPage />);

    expect(await screen.findByText("No client data on this page.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Booking")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete data" })).not.toBeInTheDocument();
  });

  test("markup in a name is shown as text in the select", async () => {
    await openWith([booking({ name: '<img src="x" onerror="alert(1)">' })]);

    expect(within(bookingSelect()).getAllByRole("option")[1].textContent).toBe(
      '<img src="x" onerror="alert(1)">, 2026-04-01 10:00',
    );
    expect(document.querySelector("select img")).toBeNull();
  });
});

describe("W3: confirming a deletion", () => {
  test("Delete data opens a dialog and sends nothing yet", async () => {
    const api = await openWith([booking()]);
    const user = userEvent.setup();

    await chooseAndPressDelete(user, "Alice Example, 2026-04-01 10:00");

    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.getByText("Delete this client's data? This cannot be undone.")).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Yes, delete" })).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(api.erasures()).toHaveLength(0);
  });

  test("Cancel closes the dialog and sends nothing", async () => {
    const api = await openWith([booking()]);
    const user = userEvent.setup();

    await chooseAndPressDelete(user, "Alice Example, 2026-04-01 10:00");
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.erasures()).toHaveLength(0);
    expect(screen.getByText("Alice Example")).toBeInTheDocument();
  });

  test("Yes, delete sends the request with the confirmation, for the chosen booking", async () => {
    const api = await openWith([booking(), booking({ id: 8, name: "Bob Jones" })]);
    const user = userEvent.setup();

    await chooseAndPressDelete(user, "Bob Jones, 2026-04-01 10:00");
    await user.click(screen.getByRole("button", { name: "Yes, delete" }));

    await waitFor(() => expect(api.erasures()).toHaveLength(1));
    const [request] = api.erasures();
    expect(request.method).toBe("POST");
    expect(request.path).toBe("/api/v1/admin/bookings/8/erase");
    expect(request.headers["Content-Type"]).toBe("application/json");
    expect(request.body).toEqual({ confirm: true });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});

describe("W4: after a deletion", () => {
  test("the row shows Deleted and the select no longer lists the booking", async () => {
    await openWith([booking(), booking({ id: 8, name: "Bob Jones" })]);
    const user = userEvent.setup();

    await chooseAndPressDelete(user, "Alice Example, 2026-04-01 10:00");
    await user.click(screen.getByRole("button", { name: "Yes, delete" }));

    await waitFor(() => expect(screen.queryByText("Alice Example")).not.toBeInTheDocument());
    expect(cellsOf(screen.getAllByRole("row")[1]).name).toHaveTextContent(/^Deleted$/);
    const options = within(bookingSelect())
      .getAllByRole("option")
      .map((option) => option.textContent);
    expect(options).toEqual(["Choose a booking", "Bob Jones, 2026-04-01 10:00"]);
    expect(screen.getByRole("button", { name: "Delete data" })).toBeDisabled();
  });

  test("deleting the last one leaves the no-client-data message", async () => {
    await openWith([booking()]);
    const user = userEvent.setup();

    await chooseAndPressDelete(user, "Alice Example, 2026-04-01 10:00");
    await user.click(screen.getByRole("button", { name: "Yes, delete" }));

    expect(await screen.findByText("No client data on this page.")).toBeInTheDocument();
  });

  test("a live booking shows the live message and stays as it was", async () => {
    await openWith([booking({ state: "accepted" })], () => [409, { error: "booking_is_live" }]);
    const user = userEvent.setup();

    await chooseAndPressDelete(user, "Alice Example, 2026-04-01 10:00");
    await user.click(screen.getByRole("button", { name: "Yes, delete" }));

    expect(await screen.findByText(LIVE)).toBeInTheDocument();
    expect(cellsOf(screen.getAllByRole("row")[1]).name).toHaveTextContent(/^Alice Example$/);
  });

  test.each([
    [404, { error: "not_found" }],
    [500, { error: "internal_server_error" }],
    [400, { error: "validation_failed", fields: { confirm: "required" } }],
  ])("a %i shows the general message", async (status, body) => {
    await openWith([booking()], () => [status, body]);
    const user = userEvent.setup();

    await chooseAndPressDelete(user, "Alice Example, 2026-04-01 10:00");
    await user.click(screen.getByRole("button", { name: "Yes, delete" }));

    expect(await screen.findByText(GENERAL)).toBeInTheDocument();
    expect(screen.getByText("Alice Example")).toBeInTheDocument();
  });

  test("a 401 returns to the login form", async () => {
    await openWith([booking()], () => [401, { error: "not_authenticated" }]);
    const user = userEvent.setup();

    await chooseAndPressDelete(user, "Alice Example, 2026-04-01 10:00");
    await user.click(screen.getByRole("button", { name: "Yes, delete" }));

    expect(
      await screen.findByText("Your session has ended. Please log in again."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
  });
});
