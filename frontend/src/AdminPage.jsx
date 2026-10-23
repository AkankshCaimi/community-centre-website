import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

// The admin page of docs/specs/F02.md (W1 to W11).

const API = "/api/v1/admin";
const GENERAL_MESSAGE = "Something went wrong. Please try again later.";
const SESSION_ENDED_MESSAGE = "Your session has ended. Please log in again.";
const LIVE_MESSAGE =
  "This booking is still live. Decline it first, or wait until the event is over.";

// Native lists keep their own behaviour; they only take the look of shadcn's Input
// (docs/specs/ui-theme.md, H2).
const LIST_CLASSES =
  "h-9 rounded-md border border-input bg-background px-3 text-sm shadow-xs focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";
const ALERT_CLASSES = "text-sm text-destructive";
const DIALOG_CLASSES = "my-4 space-y-3 rounded-xl border-2 border-foreground/20 bg-muted p-4 shadow-sm";

const STATE_LABELS = {
  submitted: "Submitted",
  contacted: "Contacted",
  accepted: "Accepted",
  declined: "Declined",
};

// The button that moves a booking into each state (W6).
const ACTION_LABELS = {
  submitted: "Mark submitted",
  contacted: "Mark contacted",
  accepted: "Accept",
  declined: "Decline",
};

const DEFAULT_FILTERS = { state: "", from: "", to: "", search: "", sort: "submitted_at", order: "desc" };

// Thrown when the API answers 401: the session is missing or has ended.
class NotAuthenticated extends Error {}

async function callApi(method, path, body) {
  const options = { method };
  if (body !== undefined) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(body);
  }
  const response = await fetch(API + path, options);
  if (response.status === 401 && path !== "/login") {
    throw new NotAuthenticated();
  }
  return { status: response.status, body: await response.json() };
}

function bookingsPath(filters, page) {
  const query = new URLSearchParams();
  for (const [name, value] of Object.entries(filters)) {
    if (value !== "") {
      query.set(name, value);
    }
  }
  query.set("page", String(page));
  return `/bookings?${query}`;
}

function shownTime(time) {
  return time.replace("T", " ");
}

// A booking the auto-decline job declined is labelled as such (F03 M4).
function stateLabel(booking) {
  if (booking.state === "declined" && booking.auto_declined) {
    return "Auto-declined";
  }
  return STATE_LABELS[booking.state];
}

// A booking whose client data has been deleted has no name (F04 A1).
function isErased(booking) {
  return booking.name === null;
}

function LoginForm({ notice, onLoggedIn }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState(notice);

  async function handleSubmit(event) {
    event.preventDefault();
    setMessage("");
    try {
      const { status } = await callApi("POST", "/login", { email, password });
      if (status === 200) {
        onLoggedIn();
      } else if (status === 401) {
        setMessage("The email or password is not correct.");
      } else {
        setMessage(GENERAL_MESSAGE);
      }
    } catch {
      setMessage(GENERAL_MESSAGE);
    }
  }

  return (
    <Card className="max-w-sm">
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="admin-email">Email</Label>
        <Input
          id="admin-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="admin-password">Password</Label>
        <Input
          id="admin-password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>
      {message && (
        <p role="alert" className={ALERT_CLASSES}>
          {message}
        </p>
      )}
      <Button type="submit">Log in</Button>
    </form>
    </Card>
  );
}

function Filters({ onApply }) {
  const [draft, setDraft] = useState(DEFAULT_FILTERS);

  function control(name) {
    return {
      id: `filter-${name}`,
      value: draft[name],
      onChange: (event) => setDraft((current) => ({ ...current, [name]: event.target.value })),
    };
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onApply(draft);
      }}
      className="my-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm"
    >
      <Label htmlFor="filter-state">State</Label>
      <select className={LIST_CLASSES} {...control("state")}>
        <option value="">All</option>
        {Object.entries(STATE_LABELS).map(([state, label]) => (
          <option key={state} value={state}>
            {label}
          </option>
        ))}
      </select>

      <Label htmlFor="filter-from">From</Label>
      <Input type="date" className="w-auto" {...control("from")} />

      <Label htmlFor="filter-to">To</Label>
      <Input type="date" className="w-auto" {...control("to")} />

      <Label htmlFor="filter-search">Search</Label>
      <Input type="search" maxLength={100} className="w-48" {...control("search")} />

      <Label htmlFor="filter-sort">Sort by</Label>
      <select className={LIST_CLASSES} {...control("sort")}>
        <option value="submitted_at">Submitted</option>
        <option value="starts_at">Start</option>
        <option value="name">Name</option>
      </select>

      <Label htmlFor="filter-order">Order</Label>
      <select className={LIST_CLASSES} {...control("order")}>
        <option value="desc">Newest first</option>
        <option value="asc">Oldest first</option>
      </select>

      <Button type="submit" size="sm">
        Apply
      </Button>
    </form>
  );
}

// Drawn over the page and holding the focus while open (W12). The position is
// set inline so the dialog stays in view even without the stylesheet.
function DeclineDialog({ onConfirm, onCancel }) {
  const yesRef = useRef(null);
  const cancelRef = useRef(null);

  useEffect(() => {
    cancelRef.current.focus();
  }, []);

  function handleKeyDown(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
    } else if (event.key === "Tab") {
      // Two buttons: Tab and Shift+Tab both move to the one without the focus.
      event.preventDefault();
      const next = document.activeElement === yesRef.current ? cancelRef : yesRef;
      next.current.focus();
    }
  }

  return (
    <div
      style={{ position: "fixed", inset: 0, zIndex: 50 }}
      className="flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="decline-question"
        className={`${DIALOG_CLASSES} w-full max-w-md`}
        onKeyDown={handleKeyDown}
      >
        <p id="decline-question" className="font-medium">
          Decline this booking? This cannot be undone.
        </p>
        <Button ref={yesRef} type="button" variant="destructive" className="mr-2" onClick={onConfirm}>
          Yes, decline
        </Button>
        <Button ref={cancelRef} type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function optionText(booking) {
  return `${booking.name}, ${shownTime(booking.starts_at)}`;
}

function DeleteDialog({ booking, onConfirm, onCancel }) {
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="delete-question" className={DIALOG_CLASSES}>
      <p id="delete-question" className="font-medium">
        Delete this client&apos;s data? This cannot be undone.
      </p>
      <p>{optionText(booking)}</p>
      <Button type="button" variant="destructive" className="mr-2" onClick={onConfirm}>
        Yes, delete
      </Button>
      <Button type="button" variant="outline" onClick={onCancel}>
        Cancel
      </Button>
    </div>
  );
}

// The "Delete client data" section below the table (F04 W2, W3).
function DeleteClientData({ bookings, onDelete }) {
  const [chosenId, setChosenId] = useState("");
  // The ID the dialog is open for. Tied to one booking, so the dialog closes
  // by itself if that booking leaves the page and cannot reopen for another.
  const [askingId, setAskingId] = useState(null);

  const withData = bookings.filter((booking) => !isErased(booking));
  // The chosen booking may have been deleted or have left the page since.
  const chosen = withData.find((booking) => String(booking.id) === chosenId);

  return (
    <section className="mt-10 space-y-3 rounded-xl border bg-card p-6 shadow-sm">
      <h3 className="text-lg font-semibold">Delete client data</h3>
      {withData.length === 0 ? (
        <p>No client data on this page.</p>
      ) : (
        <>
          <Label htmlFor="delete-booking" className="mr-3">
            Booking
          </Label>
          <select
            id="delete-booking"
            className={`${LIST_CLASSES} mr-3`}
            value={chosen ? chosenId : ""}
            onChange={(event) => {
              setChosenId(event.target.value);
              setAskingId(null);
            }}
          >
            <option value="">Choose a booking</option>
            {withData.map((booking) => (
              <option key={booking.id} value={booking.id}>
                {optionText(booking)}
              </option>
            ))}
          </select>
          <Button type="button" variant="destructive" disabled={!chosen} onClick={() => setAskingId(chosenId)}>
            Delete data
          </Button>
        </>
      )}
      {chosen && askingId === chosenId && (
        <DeleteDialog
          booking={chosen}
          onCancel={() => setAskingId(null)}
          onConfirm={() => {
            // The booking stays chosen: after a refusal the admin need not find it again.
            setAskingId(null);
            onDelete(chosen);
          }}
        />
      )}
    </section>
  );
}

function BookingRow({ booking, onAction }) {
  // React renders every value below as text, so markup typed by a client is
  // shown, never interpreted (W11).
  return (
    <TableRow>
      <TableCell>{isErased(booking) ? "Deleted" : booking.name}</TableCell>
      <TableCell>{booking.email}</TableCell>
      <TableCell>{booking.phone}</TableCell>
      <TableCell>{booking.guest_count}</TableCell>
      <TableCell>{shownTime(booking.starts_at)}</TableCell>
      <TableCell>{shownTime(booking.ends_at)}</TableCell>
      <TableCell>{stateLabel(booking)}</TableCell>
      <TableCell>{shownTime(booking.submitted_at)}</TableCell>
      <TableCell>{booking.details}</TableCell>
      <TableCell>
        {booking.state === "declined" ? (
          <span className="text-muted-foreground">Declined (final)</span>
        ) : (
          Object.keys(ACTION_LABELS)
            .filter((state) => state !== booking.state)
            .map((state) => (
              <Button
                key={state}
                type="button"
                variant="outline"
                size="sm"
                className="mr-1 mb-1"
                onClick={(event) => onAction(booking, state, event.currentTarget)}
              >
                {ACTION_LABELS[state]}
              </Button>
            ))
        )}
      </TableCell>
    </TableRow>
  );
}

function Bookings({ onSessionEnded, onLoggedOut }) {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [page, setPage] = useState(1);
  const [list, setList] = useState(null);
  const [message, setMessage] = useState("");
  const [declining, setDeclining] = useState(null);

  // Runs a request; a 401 sends the admin back to the login form (W10).
  const guarded = useCallback(
    async (request) => {
      try {
        return await request();
      } catch (error) {
        if (error instanceof NotAuthenticated) {
          onSessionEnded();
        } else {
          setMessage(GENERAL_MESSAGE);
        }
        return null;
      }
    },
    [onSessionEnded],
  );

  const load = useCallback(
    async (wantedFilters, wantedPage) => {
      const result = await guarded(() => callApi("GET", bookingsPath(wantedFilters, wantedPage)));
      if (result === null) {
        return;
      }
      if (result.status === 200) {
        setList(result.body);
      } else {
        setMessage(GENERAL_MESSAGE);
      }
    },
    [guarded],
  );

  useEffect(() => {
    load(filters, page);
  }, [load, filters, page]);

  async function changeState(booking, state) {
    setMessage("");
    const body = state === "declined" ? { state, confirm: true } : { state };
    const result = await guarded(() => callApi("PATCH", `/bookings/${booking.id}/state`, body));
    if (result === null) {
      return;
    }
    if (result.status === 200) {
      setList((current) => ({
        ...current,
        items: current.items.map((item) => (item.id === booking.id ? result.body : item)),
      }));
    } else if (result.status === 409) {
      setMessage("This booking is declined and cannot be changed.");
      load(filters, page);
    } else {
      setMessage(GENERAL_MESSAGE);
    }
  }

  async function eraseBooking(booking) {
    setMessage("");
    const result = await guarded(() =>
      callApi("POST", `/bookings/${booking.id}/erase`, { confirm: true }),
    );
    if (result === null) {
      return;
    }
    if (result.status === 200) {
      setList((current) => ({
        ...current,
        items: current.items.map((item) => (item.id === booking.id ? result.body : item)),
      }));
    } else if (result.status === 409) {
      setMessage(LIVE_MESSAGE);
    } else {
      setMessage(GENERAL_MESSAGE);
    }
  }

  // `opener` is the button pressed: focus goes back to it if the decline is cancelled (W12).
  function handleAction(booking, state, opener) {
    if (state === "declined") {
      setDeclining({ booking, opener });
    } else {
      changeState(booking, state);
    }
  }

  async function logOut() {
    const result = await guarded(() => callApi("POST", "/logout", {}));
    if (result !== null) {
      onLoggedOut();
    }
  }

  if (list === null) {
    return message ? (
      <p role="alert" className={ALERT_CLASSES}>
        {message}
      </p>
    ) : (
      <p>Loading…</p>
    );
  }

  const pageCount = Math.max(1, Math.ceil(list.total / list.page_size));

  return (
    <div>
      <Button type="button" variant="outline" size="sm" onClick={logOut}>
        Log out
      </Button>

      <Filters
        onApply={(applied) => {
          setMessage("");
          // A new object every time, so pressing Apply always requests the list (W4).
          setFilters({ ...applied });
          setPage(1);
        }}
      />

      {message && (
        <p role="alert" className={ALERT_CLASSES}>
          {message}
        </p>
      )}

      <Table>
        <TableHeader>
          <TableRow>
            {["Name", "Email", "Phone", "Guests", "Start", "End", "State", "Submitted", "Details", "Actions"].map(
              (heading) => (
                <TableHead key={heading} scope="col">
                  {heading}
                </TableHead>
              ),
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {list.items.map((booking) => (
            <BookingRow key={booking.id} booking={booking} onAction={handleAction} />
          ))}
        </TableBody>
      </Table>
      {list.items.length === 0 && <p>No bookings found.</p>}

      <p>
        Page {list.page} of {pageCount}
      </p>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="mr-2"
        disabled={list.page <= 1}
        onClick={() => setPage(list.page - 1)}
      >
        Previous
      </Button>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={list.page >= pageCount}
        onClick={() => setPage(list.page + 1)}
      >
        Next
      </Button>

      <DeleteClientData bookings={list.items} onDelete={eraseBooking} />

      {declining && (
        <DeclineDialog
          onCancel={() => {
            const { opener } = declining;
            setDeclining(null);
            opener.focus();
          }}
          onConfirm={() => {
            const { booking } = declining;
            setDeclining(null);
            changeState(booking, "declined");
          }}
        />
      )}
    </div>
  );
}

export default function AdminPage() {
  // "checking" until GET /session has answered (W1).
  const [view, setView] = useState("checking");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let cancelled = false;
    callApi("GET", "/session")
      .then(({ status }) => {
        if (!cancelled) {
          setView(status === 200 ? "bookings" : "login");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setView("login");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSessionEnded = useCallback(() => {
    setNotice(SESSION_ENDED_MESSAGE);
    setView("login");
  }, []);

  if (view === "checking") {
    return <p>Loading…</p>;
  }
  if (view === "login") {
    return (
      <LoginForm
        key={notice}
        notice={notice}
        onLoggedIn={() => {
          setNotice("");
          setView("bookings");
        }}
      />
    );
  }
  return (
    <Bookings
      onSessionEnded={handleSessionEnded}
      onLoggedOut={() => {
        setNotice("");
        setView("login");
      }}
    />
  );
}
