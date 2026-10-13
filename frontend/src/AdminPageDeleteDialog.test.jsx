// F04 rules W3 and W4, the parts added after the branch review: the dialog
// names the booking, closes if the booking leaves the page, and a refused
// booking stays chosen. Every expected value comes from docs/specs/F04.md.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import AdminPage from "./AdminPage.jsx";

const ALICE = "Alice Example, 2026-04-01 10:00";
const BOB = "Bob Jones, 2026-04-02 18:30";

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
    details: null,
    submitted_at: "2026-03-10T09:05",
    auto_declined: false,
    ...overrides,
  };
}

const bob = () => booking({ id: 8, name: "Bob Jones", starts_at: "2026-04-02T18:30" });

function json(status, body) {
  return { status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) };
}

// A stand-in for the admin API. `pages` gives the list returned by each
// successive list request (the last one repeats); `erase` answers a deletion.
function startApi(pages, erase) {
  let listCalls = 0;
  const erasures = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (address) => {
      const path = new URL(address, "https://centre.example").pathname;
      if (path === "/api/v1/admin/session") return json(200, { email: "admin@centre.example" });
      if (path.endsWith("/erase")) {
        erasures.push(path);
        return json(...erase());
      }
      const items = pages[Math.min(listCalls, pages.length - 1)];
      listCalls += 1;
      return json(200, { items, page: 1, page_size: 20, total: items.length });
    }),
  );
  return erasures;
}

async function open(pages, erase = () => [200, booking({ name: null })]) {
  const erasures = startApi(pages, erase);
  render(<AdminPage />);
  await screen.findByRole("table");
  return erasures;
}

beforeEach(() => {
  window.history.pushState({}, "", "/admin");
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, "", "/");
});

describe("W3: the dialog names the booking", () => {
  test.each([
    [ALICE, BOB],
    [BOB, ALICE],
  ])("choosing %s shows that booking and not the other", async (chosen, other) => {
    await open([[booking(), bob()]]);
    const user = userEvent.setup();

    await user.selectOptions(screen.getByLabelText("Booking"), chosen);
    await user.click(screen.getByRole("button", { name: "Delete data" }));

    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.getByText(chosen)).toBeInTheDocument();
    expect(dialog.queryByText(other)).not.toBeInTheDocument();
    expect(dialog.getByText("Delete this client's data? This cannot be undone.")).toBeInTheDocument();
  });
});

describe("W3: the dialog closes if the booking leaves the page", () => {
  test("after Apply brings a page without it, nothing is asked and nothing is sent", async () => {
    const erasures = await open([[booking(), bob()], [bob()]]);
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Booking"), ALICE);
    await user.click(screen.getByRole("button", { name: "Delete data" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(erasures).toHaveLength(0);
  });

  test("choosing another booking afterwards does not reopen the dialog by itself", async () => {
    await open([[booking(), bob()], [bob()]]);
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Booking"), ALICE);
    await user.click(screen.getByRole("button", { name: "Delete data" }));
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    await user.selectOptions(screen.getByLabelText("Booking"), BOB);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("W4: after a refusal the booking stays chosen", () => {
  test.each([
    [409, { error: "booking_is_live" }],
    [500, { error: "internal_server_error" }],
  ])("after a %i the select still shows the booking", async (status, body) => {
    await open([[booking({ state: "accepted" }), bob()]], () => [status, body]);
    const user = userEvent.setup();

    await user.selectOptions(screen.getByLabelText("Booking"), ALICE);
    await user.click(screen.getByRole("button", { name: "Delete data" }));
    await user.click(screen.getByRole("button", { name: "Yes, delete" }));

    await screen.findByRole("alert");
    expect(screen.getByLabelText("Booking")).toHaveDisplayValue(ALICE);
    expect(screen.getByRole("button", { name: "Delete data" })).toBeEnabled();
  });

  test("after a success the select goes back to the empty choice", async () => {
    await open([[booking(), bob()]]);
    const user = userEvent.setup();

    await user.selectOptions(screen.getByLabelText("Booking"), ALICE);
    await user.click(screen.getByRole("button", { name: "Delete data" }));
    await user.click(screen.getByRole("button", { name: "Yes, delete" }));

    await waitFor(() => expect(screen.queryByText("Alice Example")).not.toBeInTheDocument());
    expect(screen.getByLabelText("Booking")).toHaveDisplayValue("Choose a booking");
  });
});
