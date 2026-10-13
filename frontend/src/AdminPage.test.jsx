// F02 admin page rules W1 to W11. Every expected value comes from
// docs/specs/F02.md; each test names the rule it checks.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import AdminPage from "./AdminPage.jsx";
import App from "./App.jsx";

const GENERAL = "Something went wrong. Please try again later.";
const SESSION_ENDED = "Your session has ended. Please log in again.";

function booking(overrides = {}) {
  return {
    id: 7,
    state: "submitted",
    name: "Alice Example",
    email: "alice@example.com",
    phone: "07700 900123",
    guest_count: 40,
    starts_at: "2026-04-01T10:00",
    ends_at: "2026-04-01T14:00",
    details: "Birthday party",
    submitted_at: "2026-03-10T09:05",
    ...overrides,
  };
}

function page(items, overrides = {}) {
  return { items, page: 1, page_size: 20, total: items.length, ...overrides };
}

function json(status, body) {
  return { status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) };
}

// A stand-in for the admin API. Each route is a function of the request that
// returns [status, body]; tests replace the routes they care about.
function startApi(routes = {}) {
  const api = {
    session: () => [200, { email: "admin@centre.example" }],
    login: () => [200, { email: "admin@centre.example" }],
    logout: () => [200, { status: "logged_out" }],
    bookings: () => [200, page([booking()])],
    state: (request) => [200, booking({ state: request.body.state })],
    ...routes,
  };
  const requests = [];

  vi.stubGlobal(
    "fetch",
    vi.fn(async (address, options = {}) => {
      const url = new URL(address, "https://centre.example");
      const request = {
        method: options.method ?? "GET",
        path: url.pathname,
        query: Object.fromEntries(url.searchParams),
        headers: options.headers ?? {},
        body: options.body === undefined ? undefined : JSON.parse(options.body),
      };
      requests.push(request);

      let route;
      if (request.path === "/api/v1/admin/session") route = api.session;
      else if (request.path === "/api/v1/admin/login") route = api.login;
      else if (request.path === "/api/v1/admin/logout") route = api.logout;
      else if (request.path === "/api/v1/admin/bookings") route = api.bookings;
      else if (/^\/api\/v1\/admin\/bookings\/\d+\/state$/.test(request.path)) route = api.state;
      else return json(404, { error: "not_found" });

      const [status, body] = route(request);
      return json(status, body);
    }),
  );

  return {
    requests,
    sent: (method, path) => requests.filter((r) => r.method === method && r.path === path),
  };
}

const LOGGED_OUT = { session: () => [401, { error: "not_authenticated" }] };

async function openBookings(routes) {
  const api = startApi(routes);
  render(<AdminPage />);
  await screen.findByRole("table");
  return api;
}

function rowOf(name) {
  return screen.getByText(name).closest("tr");
}

beforeEach(() => {
  window.history.pushState({}, "", "/admin");
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, "", "/");
});

describe("W1: what the page shows on opening", () => {
  test("asks who is logged in", async () => {
    const api = startApi();
    render(<AdminPage />);

    await screen.findByRole("table");
    expect(api.sent("GET", "/api/v1/admin/session")).toHaveLength(1);
  });

  test("with a session it shows the bookings", async () => {
    await openBookings();

    expect(screen.getByText("Alice Example")).toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
  });

  test("without a session it shows the login form", async () => {
    const api = startApi(LOGGED_OUT);
    render(<AdminPage />);

    expect(await screen.findByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(api.sent("GET", "/api/v1/admin/bookings")).toHaveLength(0);
  });

  test("without a session on opening there is no session-ended message", async () => {
    startApi(LOGGED_OUT);
    render(<AdminPage />);

    await screen.findByLabelText("Email");
    expect(screen.queryByText(SESSION_ENDED)).not.toBeInTheDocument();
  });
});

describe("the address /admin", () => {
  test("the app shows the admin page at /admin", async () => {
    startApi(LOGGED_OUT);
    render(<App />);

    expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send booking request" })).not.toBeInTheDocument();
  });

  test("the app still shows the public form at /", () => {
    window.history.pushState({}, "", "/");
    startApi(LOGGED_OUT);
    render(<App />);

    expect(screen.getByRole("button", { name: "Send booking request" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Log in" })).not.toBeInTheDocument();
  });
});

describe("W2: logging in", () => {
  async function logIn(routes) {
    const api = startApi({ ...LOGGED_OUT, ...routes });
    const user = userEvent.setup();
    render(<AdminPage />);
    await user.type(await screen.findByLabelText("Email"), "admin@centre.example");
    await user.type(screen.getByLabelText("Password"), "correct horse battery");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    return api;
  }

  test("the password is a password input", async () => {
    startApi(LOGGED_OUT);
    render(<AdminPage />);

    expect(await screen.findByLabelText("Password")).toHaveAttribute("type", "password");
  });

  test("sends the email and password as JSON", async () => {
    const api = await logIn();

    await screen.findByRole("table");
    const [request] = api.sent("POST", "/api/v1/admin/login");
    expect(request.headers["Content-Type"]).toBe("application/json");
    expect(request.body).toEqual({
      email: "admin@centre.example",
      password: "correct horse battery",
    });
  });

  test("on success shows the bookings", async () => {
    await logIn();

    expect(await screen.findByText("Alice Example")).toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
  });

  test("wrong email or password shows one message", async () => {
    await logIn({ login: () => [401, { error: "invalid_credentials" }] });

    expect(await screen.findByText("The email or password is not correct.")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  test.each([
    [400, { error: "validation_failed", fields: { email: "required" } }],
    [500, { error: "internal_server_error" }],
  ])("a %i shows the general message", async (status, body) => {
    await logIn({ login: () => [status, body] });

    expect(await screen.findByText(GENERAL)).toBeInTheDocument();
  });

  test("no response shows the general message", async () => {
    startApi(LOGGED_OUT);
    const user = userEvent.setup();
    render(<AdminPage />);
    await user.type(await screen.findByLabelText("Email"), "admin@centre.example");
    await user.type(screen.getByLabelText("Password"), "correct horse battery");
    fetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByText(GENERAL)).toBeInTheDocument();
  });
});

describe("W3: the table", () => {
  test("has the ten columns in order", async () => {
    await openBookings();

    const headers = screen.getAllByRole("columnheader").map((header) => header.textContent);
    expect(headers).toEqual([
      "Name",
      "Email",
      "Phone",
      "Guests",
      "Start",
      "End",
      "State",
      "Submitted",
      "Details",
      "Actions",
    ]);
  });

  test("shows one row per booking with its values", async () => {
    await openBookings({
      bookings: () => [
        200,
        page([booking(), booking({ id: 8, name: "Bob Jones", state: "accepted", details: null })]),
      ],
    });

    expect(screen.getAllByRole("row")).toHaveLength(3); // header and two bookings
    const row = within(rowOf("Alice Example"));
    expect(row.getByText("alice@example.com")).toBeInTheDocument();
    expect(row.getByText("07700 900123")).toBeInTheDocument();
    expect(row.getByText("40")).toBeInTheDocument();
    expect(row.getByText("Birthday party")).toBeInTheDocument();
  });

  test("shows times as YYYY-MM-DD HH:MM", async () => {
    await openBookings();

    const row = within(rowOf("Alice Example"));
    expect(row.getByText("2026-04-01 10:00")).toBeInTheDocument();
    expect(row.getByText("2026-04-01 14:00")).toBeInTheDocument();
    expect(row.getByText("2026-03-10 09:05")).toBeInTheDocument();
  });

  test.each([
    ["submitted", "Submitted"],
    ["contacted", "Contacted"],
    ["accepted", "Accepted"],
    ["declined", "Declined"],
  ])("shows the state %s as %s", async (state, shown) => {
    await openBookings({ bookings: () => [200, page([booking({ state })])] });

    expect(within(rowOf("Alice Example")).getByText(shown)).toBeInTheDocument();
  });

  test("with no bookings it says so", async () => {
    startApi({ bookings: () => [200, page([])] });
    render(<AdminPage />);

    expect(await screen.findByText("No bookings found.")).toBeInTheDocument();
  });
});

describe("W4: filters, search and sort", () => {
  test("has the controls", async () => {
    await openBookings();

    expect(
      within(screen.getByLabelText("State"))
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["All", "Submitted", "Contacted", "Accepted", "Declined"]);
    expect(screen.getByLabelText("From")).toHaveAttribute("type", "date");
    expect(screen.getByLabelText("To")).toHaveAttribute("type", "date");
    expect(screen.getByLabelText("Search")).toBeInTheDocument();
    expect(
      within(screen.getByLabelText("Sort by"))
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["Submitted", "Start", "Name"]);
    expect(
      within(screen.getByLabelText("Order"))
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["Newest first", "Oldest first"]);
    expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument();
  });

  test("Apply sends every chosen value as a query parameter", async () => {
    const api = await openBookings();
    const user = userEvent.setup();

    await user.selectOptions(screen.getByLabelText("State"), "Accepted");
    await user.type(screen.getByLabelText("From"), "2026-04-01");
    await user.type(screen.getByLabelText("To"), "2026-04-30");
    await user.type(screen.getByLabelText("Search"), "smith & co");
    await user.selectOptions(screen.getByLabelText("Sort by"), "Start");
    await user.selectOptions(screen.getByLabelText("Order"), "Oldest first");
    await user.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() => expect(api.sent("GET", "/api/v1/admin/bookings")).toHaveLength(2));
    expect(api.sent("GET", "/api/v1/admin/bookings")[1].query).toEqual({
      state: "accepted",
      from: "2026-04-01",
      to: "2026-04-30",
      search: "smith & co",
      sort: "starts_at",
      order: "asc",
      page: "1",
    });
  });

  test("Apply leaves out the empty values", async () => {
    const api = await openBookings();
    const user = userEvent.setup();

    await user.selectOptions(screen.getByLabelText("Sort by"), "Name");
    await user.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() => expect(api.sent("GET", "/api/v1/admin/bookings")).toHaveLength(2));
    expect(api.sent("GET", "/api/v1/admin/bookings")[1].query).toEqual({
      sort: "name",
      order: "desc",
      page: "1",
    });
  });

  test("nothing is requested until Apply is pressed", async () => {
    const api = await openBookings();
    const user = userEvent.setup();

    await user.selectOptions(screen.getByLabelText("State"), "Declined");
    await user.type(screen.getByLabelText("Search"), "smith");

    expect(api.sent("GET", "/api/v1/admin/bookings")).toHaveLength(1);
  });

  test("Apply goes back to page 1", async () => {
    const api = await openBookings({
      bookings: (request) => [
        200,
        page([booking()], { total: 45, page: Number(request.query.page ?? 1) }),
      ],
    });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("Page 2 of 3");
    await user.click(screen.getByRole("button", { name: "Apply" }));

    await screen.findByText("Page 1 of 3");
    expect(api.sent("GET", "/api/v1/admin/bookings").at(-1).query.page).toBe("1");
  });
});

describe("W5: pages", () => {
  const paged = {
    bookings: (request) => [
      200,
      page([booking()], { total: 45, page: Number(request.query.page ?? 1) }),
    ],
  };

  test("shows the page and the number of pages", async () => {
    await openBookings(paged);

    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
  });

  test("Previous is disabled on the first page and Next on the last", async () => {
    await openBookings(paged);
    const user = userEvent.setup();

    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("Page 2 of 3");
    expect(screen.getByRole("button", { name: "Previous" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("Page 3 of 3");
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  test("Next and Previous keep the filters", async () => {
    const api = await openBookings(paged);
    const user = userEvent.setup();

    await user.selectOptions(screen.getByLabelText("State"), "Accepted");
    await user.type(screen.getByLabelText("Search"), "smith");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(api.sent("GET", "/api/v1/admin/bookings")).toHaveLength(2));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByText("Page 2 of 3");

    expect(api.sent("GET", "/api/v1/admin/bookings").at(-1).query).toEqual({
      state: "accepted",
      search: "smith",
      sort: "submitted_at",
      order: "desc",
      page: "2",
    });

    await user.click(screen.getByRole("button", { name: "Previous" }));
    await screen.findByText("Page 1 of 3");
    expect(api.sent("GET", "/api/v1/admin/bookings").at(-1).query.page).toBe("1");
  });

  test("an empty list is page 1 of 1 with both buttons disabled", async () => {
    startApi({ bookings: () => [200, page([])] });
    render(<AdminPage />);

    expect(await screen.findByText("Page 1 of 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  test("exactly one full page is page 1 of 1", async () => {
    await openBookings({ bookings: () => [200, page([booking()], { total: 20 })] });

    expect(screen.getByText("Page 1 of 1")).toBeInTheDocument();
  });
});

describe("W6: the action buttons", () => {
  test.each([
    ["submitted", ["Mark contacted", "Accept", "Decline"]],
    ["contacted", ["Mark submitted", "Accept", "Decline"]],
    ["accepted", ["Mark submitted", "Mark contacted", "Decline"]],
  ])("a %s row has a button for every other state", async (state, expected) => {
    await openBookings({ bookings: () => [200, page([booking({ state })])] });

    const buttons = within(rowOf("Alice Example"))
      .getAllByRole("button")
      .map((button) => button.textContent);
    expect(buttons).toEqual(expected);
  });

  test("a declined row has no buttons and says it is final", async () => {
    await openBookings({ bookings: () => [200, page([booking({ state: "declined" })])] });

    const row = within(rowOf("Alice Example"));
    expect(row.queryAllByRole("button")).toHaveLength(0);
    expect(row.getByText("Declined (final)")).toBeInTheDocument();
  });
});

describe("W7: changing a state", () => {
  test.each([
    ["Mark contacted", "submitted", "contacted"],
    ["Accept", "submitted", "accepted"],
    ["Mark submitted", "accepted", "submitted"],
  ])("%s sends the change at once", async (label, from, to) => {
    const api = await openBookings({ bookings: () => [200, page([booking({ state: from })])] });
    const user = userEvent.setup();

    await user.click(within(rowOf("Alice Example")).getByRole("button", { name: label }));

    await waitFor(() => expect(api.sent("PATCH", "/api/v1/admin/bookings/7/state")).toHaveLength(1));
    const [request] = api.sent("PATCH", "/api/v1/admin/bookings/7/state");
    expect(request.headers["Content-Type"]).toBe("application/json");
    expect(request.body).toEqual({ state: to });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  test("Decline opens a dialog and sends nothing yet", async () => {
    const api = await openBookings();
    const user = userEvent.setup();

    await user.click(within(rowOf("Alice Example")).getByRole("button", { name: "Decline" }));

    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.getByText("Decline this booking? This cannot be undone.")).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Yes, decline" })).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(api.sent("PATCH", "/api/v1/admin/bookings/7/state")).toHaveLength(0);
  });

  test("Cancel closes the dialog and sends nothing", async () => {
    const api = await openBookings();
    const user = userEvent.setup();

    await user.click(within(rowOf("Alice Example")).getByRole("button", { name: "Decline" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.sent("PATCH", "/api/v1/admin/bookings/7/state")).toHaveLength(0);
    expect(within(rowOf("Alice Example")).getByText("Submitted")).toBeInTheDocument();
  });

  test("Yes, decline sends the change with the confirmation", async () => {
    const api = await openBookings();
    const user = userEvent.setup();

    await user.click(within(rowOf("Alice Example")).getByRole("button", { name: "Decline" }));
    await user.click(screen.getByRole("button", { name: "Yes, decline" }));

    await waitFor(() => expect(api.sent("PATCH", "/api/v1/admin/bookings/7/state")).toHaveLength(1));
    expect(api.sent("PATCH", "/api/v1/admin/bookings/7/state")[0].body).toEqual({
      state: "declined",
      confirm: true,
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  test("the change is sent for the row that was clicked", async () => {
    const api = await openBookings({
      bookings: () => [200, page([booking(), booking({ id: 8, name: "Bob Jones" })])],
    });
    const user = userEvent.setup();

    await user.click(within(rowOf("Bob Jones")).getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(api.sent("PATCH", "/api/v1/admin/bookings/8/state")).toHaveLength(1));
    expect(api.sent("PATCH", "/api/v1/admin/bookings/7/state")).toHaveLength(0);
  });
});

describe("W8: after a change", () => {
  test("the row shows the new state and its new buttons", async () => {
    await openBookings();
    const user = userEvent.setup();

    await user.click(within(rowOf("Alice Example")).getByRole("button", { name: "Accept" }));

    await within(rowOf("Alice Example")).findByText("Accepted");
    const buttons = within(rowOf("Alice Example"))
      .getAllByRole("button")
      .map((button) => button.textContent);
    expect(buttons).toEqual(["Mark submitted", "Mark contacted", "Decline"]);
  });

  test("a declined row becomes final", async () => {
    await openBookings();
    const user = userEvent.setup();

    await user.click(within(rowOf("Alice Example")).getByRole("button", { name: "Decline" }));
    await user.click(screen.getByRole("button", { name: "Yes, decline" }));

    await within(rowOf("Alice Example")).findByText("Declined (final)");
    expect(within(rowOf("Alice Example")).queryAllByRole("button")).toHaveLength(0);
  });

  test("a booking that turns out to be declined shows a message and reloads the list", async () => {
    const api = await openBookings({ state: () => [409, { error: "declined_is_final" }] });
    const user = userEvent.setup();

    await user.click(within(rowOf("Alice Example")).getByRole("button", { name: "Accept" }));

    expect(
      await screen.findByText("This booking is declined and cannot be changed."),
    ).toBeInTheDocument();
    await waitFor(() => expect(api.sent("GET", "/api/v1/admin/bookings")).toHaveLength(2));
  });

  test.each([
    [500, { error: "internal_server_error" }],
    [404, { error: "not_found" }],
    [400, { error: "validation_failed", fields: { state: "invalid" } }],
  ])("a %i shows the general message and leaves the row as it was", async (status, body) => {
    await openBookings({ state: () => [status, body] });
    const user = userEvent.setup();

    await user.click(within(rowOf("Alice Example")).getByRole("button", { name: "Accept" }));

    expect(await screen.findByText(GENERAL)).toBeInTheDocument();
    expect(within(rowOf("Alice Example")).getByText("Submitted")).toBeInTheDocument();
  });
});

describe("W9: logging out", () => {
  test("sends the logout and returns to the login form", async () => {
    const api = await openBookings();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Log out" }));

    expect(await screen.findByRole("button", { name: "Log in" })).toBeInTheDocument();
    const [request] = api.sent("POST", "/api/v1/admin/logout");
    expect(request.headers["Content-Type"]).toBe("application/json");
    expect(request.body).toEqual({});
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText(SESSION_ENDED)).not.toBeInTheDocument();
  });
});

describe("W10: when the session has ended", () => {
  const ended = () => [401, { error: "not_authenticated" }];

  test("a list request that is refused returns to the login form", async () => {
    let calls = 0;
    await openBookings({
      bookings: () => (++calls === 1 ? [200, page([booking()])] : ended()),
    });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Apply" }));

    expect(await screen.findByText(SESSION_ENDED)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  test("a state change that is refused returns to the login form", async () => {
    await openBookings({ state: ended });
    const user = userEvent.setup();

    await user.click(within(rowOf("Alice Example")).getByRole("button", { name: "Accept" }));

    expect(await screen.findByText(SESSION_ENDED)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
  });

  test("the first list request being refused also returns to the login form", async () => {
    startApi({ bookings: ended });
    render(<AdminPage />);

    expect(await screen.findByText(SESSION_ENDED)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
  });
});

describe("W11: client text is shown as text", () => {
  test("markup in name, email, phone and details is not interpreted", async () => {
    const name = '<img src="x" onerror="alert(1)">Mallory';
    const details = "<script>alert(2)</script><b>bold</b>";
    await openBookings({
      bookings: () => [
        200,
        page([booking({ name, details, email: "<i>a@b.example</i>", phone: "<u>07700</u>" })]),
      ],
    });

    expect(screen.getByText(name)).toBeInTheDocument();
    expect(screen.getByText(details)).toBeInTheDocument();
    expect(screen.getByText("<i>a@b.example</i>")).toBeInTheDocument();
    expect(screen.getByText("<u>07700</u>")).toBeInTheDocument();
    for (const tag of ["img", "script", "b", "i", "u"]) {
      expect(document.querySelector(`table ${tag}`)).toBeNull();
    }
  });
});
