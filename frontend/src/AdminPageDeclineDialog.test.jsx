// F02 rule W12: the decline dialog is drawn over the page, fixed to the
// window, and holds the focus while it is open. Every expected value comes
// from docs/specs/F02.md.

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import AdminPage from "./AdminPage.jsx";

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
    details: null,
    submitted_at: "2026-03-10T09:05",
    auto_declined: false,
    ...overrides,
  };
}

function json(status, body) {
  return { status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) };
}

// A stand-in for the admin API that records every state change it is sent.
function startApi(items) {
  const changes = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (address, options = {}) => {
      const path = new URL(address, "https://centre.example").pathname;
      if (path === "/api/v1/admin/session") return json(200, { email: "admin@centre.example" });
      if (path.endsWith("/state")) {
        const body = JSON.parse(options.body);
        changes.push({ path, body });
        const id = Number(path.split("/").at(-2));
        return json(200, booking({ ...items.find((item) => item.id === id), state: body.state }));
      }
      return json(200, { items, page: 1, page_size: 20, total: items.length });
    }),
  );
  return changes;
}

async function open(items = [booking(), booking({ id: 8, name: "Bob Jones" })]) {
  const changes = startApi(items);
  render(<AdminPage />);
  await screen.findByRole("table");
  return changes;
}

function rowOf(name) {
  return screen.getByRole("cell", { name }).closest("tr");
}

function declineButtonOf(name) {
  return within(rowOf(name)).getByRole("button", { name: "Decline" });
}

beforeEach(() => {
  window.history.pushState({}, "", "/admin");
});

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, "", "/");
});

describe("W12: the decline dialog is drawn over the page", () => {
  test("it is fixed to the window, not added to the end of the page", async () => {
    await open();
    const user = userEvent.setup();

    await user.click(declineButtonOf("Alice Example"));

    const dialog = screen.getByRole("dialog");
    const positions = [];
    for (let element = dialog; element; element = element.parentElement) {
      positions.push(getComputedStyle(element).position);
    }
    expect(positions).toContain("fixed");
  });
});

describe("W12: focus while the dialog is open", () => {
  test("focus moves to Cancel when it opens", async () => {
    await open();
    const user = userEvent.setup();

    await user.click(declineButtonOf("Alice Example"));

    const dialog = within(screen.getByRole("dialog"));
    expect(dialog.getByRole("button", { name: "Cancel" })).toHaveFocus();
  });

  test("Tab moves only between its two buttons", async () => {
    await open();
    const user = userEvent.setup();
    await user.click(declineButtonOf("Alice Example"));
    const dialog = within(screen.getByRole("dialog"));
    const yes = dialog.getByRole("button", { name: "Yes, decline" });
    const cancel = dialog.getByRole("button", { name: "Cancel" });

    await user.tab();
    expect(yes).toHaveFocus();
    await user.tab();
    expect(cancel).toHaveFocus();
    await user.tab();
    expect(yes).toHaveFocus();
  });

  test("Shift+Tab moves only between its two buttons", async () => {
    await open();
    const user = userEvent.setup();
    await user.click(declineButtonOf("Alice Example"));
    const dialog = within(screen.getByRole("dialog"));
    const yes = dialog.getByRole("button", { name: "Yes, decline" });
    const cancel = dialog.getByRole("button", { name: "Cancel" });

    await user.tab({ shift: true });
    expect(yes).toHaveFocus();
    await user.tab({ shift: true });
    expect(cancel).toHaveFocus();
  });
});

describe("W12: closing the dialog", () => {
  test("Escape closes it and sends nothing", async () => {
    const changes = await open();
    const user = userEvent.setup();

    await user.click(declineButtonOf("Alice Example"));
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(changes).toHaveLength(0);
    expect(within(rowOf("Alice Example")).getByText("Submitted")).toBeInTheDocument();
  });

  test.each([
    ["Cancel", async (user) => user.click(screen.getByRole("button", { name: "Cancel" }))],
    ["Escape", async (user) => user.keyboard("{Escape}")],
  ])("after %s, focus returns to the row's Decline button", async (_how, close) => {
    await open();
    const user = userEvent.setup();

    await user.click(declineButtonOf("Bob Jones"));
    expect(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" })).toHaveFocus();
    await close(user);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(declineButtonOf("Bob Jones")).toHaveFocus();
  });

  test("Yes, decline still sends the decline with the confirmation (W7)", async () => {
    const changes = await open();
    const user = userEvent.setup();

    await user.click(declineButtonOf("Bob Jones"));
    await user.click(screen.getByRole("button", { name: "Yes, decline" }));

    await waitFor(() => expect(changes).toHaveLength(1));
    expect(changes[0]).toEqual({
      path: "/api/v1/admin/bookings/8/state",
      body: { state: "declined", confirm: true },
    });
  });
});
