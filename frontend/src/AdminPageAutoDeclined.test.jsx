// F03 rule M4: how the admin page shows an auto-declined booking.
// Every expected value comes from docs/specs/F03.md.

import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import AdminPage from "./AdminPage.jsx";

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

// A stand-in for the admin API: logged in, with the given bookings in the list.
function startApi(items) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (address) => {
      const path = new URL(address, "https://centre.example").pathname;
      const body =
        path === "/api/v1/admin/session"
          ? { email: "admin@centre.example" }
          : { items, page: 1, page_size: 20, total: items.length };
      return { status: 200, ok: true, json: () => Promise.resolve(body) };
    }),
  );
}

async function openWith(items) {
  startApi(items);
  render(<AdminPage />);
  await screen.findByRole("table");
}

function cellsOf(name) {
  // Columns in order (F02 W3): Name, Email, Phone, Guests, Start, End, State,
  // Submitted, Details, Actions.
  const cells = within(screen.getByText(name).closest("tr")).getAllByRole("cell");
  return { state: cells[6], actions: cells[9] };
}

beforeEach(() => {
  window.history.pushState({}, "", "/admin");
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, "", "/");
});

describe("M4: an auto-declined booking on the admin page", () => {
  test("shows Auto-declined in the State column", async () => {
    await openWith([booking({ auto_declined: true })]);

    expect(cellsOf("Alice Example").state).toHaveTextContent(/^Auto-declined$/);
  });

  test("is final: no buttons, and Declined (final) under Actions", async () => {
    await openWith([booking({ auto_declined: true })]);

    const { actions } = cellsOf("Alice Example");
    expect(actions).toHaveTextContent(/^Declined \(final\)$/);
    expect(within(actions).queryAllByRole("button")).toHaveLength(0);
  });

  test("a booking declined by an admin still shows Declined", async () => {
    await openWith([booking({ auto_declined: false })]);

    const { state, actions } = cellsOf("Alice Example");
    expect(state).toHaveTextContent(/^Declined$/);
    expect(actions).toHaveTextContent(/^Declined \(final\)$/);
  });

  test("the two kinds are told apart in one list", async () => {
    await openWith([
      booking({ id: 1, name: "Auto Person", auto_declined: true }),
      booking({ id: 2, name: "Manual Person", auto_declined: false }),
      booking({ id: 3, name: "Open Person", state: "submitted", auto_declined: false }),
    ]);

    expect(cellsOf("Auto Person").state).toHaveTextContent(/^Auto-declined$/);
    expect(cellsOf("Manual Person").state).toHaveTextContent(/^Declined$/);
    expect(cellsOf("Open Person").state).toHaveTextContent(/^Submitted$/);
  });

  test("the mark does not relabel a booking in another state", async () => {
    // The API never sends this (F03 M1), but a stray true must not hide the real state.
    await openWith([booking({ state: "accepted", auto_declined: true })]);

    expect(cellsOf("Alice Example").state).toHaveTextContent(/^Accepted$/);
  });
});
