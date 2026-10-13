import { useCallback, useEffect, useState } from "react";

// The admin page of docs/specs/F02.md (W1 to W11).

const API = "/api/v1/admin";
const GENERAL_MESSAGE = "Something went wrong. Please try again later.";
const SESSION_ENDED_MESSAGE = "Your session has ended. Please log in again.";
const LIVE_MESSAGE =
  "This booking is still live. Decline it first, or wait until the event is over.";

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
    <form onSubmit={handleSubmit} noValidate>
      <div>
        <label htmlFor="admin-email">Email</label>
        <input
          id="admin-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <div>
        <label htmlFor="admin-password">Password</label>
        <input
          id="admin-password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>
      {message && <p role="alert">{message}</p>}
      <button type="submit">Log in</button>
    </form>
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
    >
      <label htmlFor="filter-state">State</label>
      <select {...control("state")}>
        <option value="">All</option>
        {Object.entries(STATE_LABELS).map(([state, label]) => (
          <option key={state} value={state}>
            {label}
          </option>
        ))}
      </select>

      <label htmlFor="filter-from">From</label>
      <input type="date" {...control("from")} />

      <label htmlFor="filter-to">To</label>
      <input type="date" {...control("to")} />

      <label htmlFor="filter-search">Search</label>
      <input type="search" maxLength={100} {...control("search")} />

      <label htmlFor="filter-sort">Sort by</label>
      <select {...control("sort")}>
        <option value="submitted_at">Submitted</option>
        <option value="starts_at">Start</option>
        <option value="name">Name</option>
      </select>

      <label htmlFor="filter-order">Order</label>
      <select {...control("order")}>
        <option value="desc">Newest first</option>
        <option value="asc">Oldest first</option>
      </select>

      <button type="submit">Apply</button>
    </form>
  );
}

function DeclineDialog({ onConfirm, onCancel }) {
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="decline-question">
      <p id="decline-question">Decline this booking? This cannot be undone.</p>
      <button type="button" onClick={onConfirm}>
        Yes, decline
      </button>
      <button type="button" onClick={onCancel}>
        Cancel
      </button>
    </div>
  );
}

function DeleteDialog({ onConfirm, onCancel }) {
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="delete-question">
      <p id="delete-question">Delete this client&apos;s data? This cannot be undone.</p>
      <button type="button" onClick={onConfirm}>
        Yes, delete
      </button>
      <button type="button" onClick={onCancel}>
        Cancel
      </button>
    </div>
  );
}

// The "Delete client data" section below the table (F04 W2, W3).
function DeleteClientData({ bookings, onDelete }) {
  const [chosenId, setChosenId] = useState("");
  const [asking, setAsking] = useState(false);

  const withData = bookings.filter((booking) => !isErased(booking));
  // The chosen booking may have been deleted or have left the page since.
  const chosen = withData.find((booking) => String(booking.id) === chosenId);

  return (
    <section>
      <h3>Delete client data</h3>
      {withData.length === 0 ? (
        <p>No client data on this page.</p>
      ) : (
        <>
          <label htmlFor="delete-booking">Booking</label>
          <select
            id="delete-booking"
            value={chosen ? chosenId : ""}
            onChange={(event) => setChosenId(event.target.value)}
          >
            <option value="">Choose a booking</option>
            {withData.map((booking) => (
              <option key={booking.id} value={booking.id}>
                {booking.name}, {shownTime(booking.starts_at)}
              </option>
            ))}
          </select>
          <button type="button" disabled={!chosen} onClick={() => setAsking(true)}>
            Delete data
          </button>
        </>
      )}
      {asking && chosen && (
        <DeleteDialog
          onCancel={() => setAsking(false)}
          onConfirm={() => {
            setAsking(false);
            setChosenId("");
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
    <tr>
      <td>{isErased(booking) ? "Deleted" : booking.name}</td>
      <td>{booking.email}</td>
      <td>{booking.phone}</td>
      <td>{booking.guest_count}</td>
      <td>{shownTime(booking.starts_at)}</td>
      <td>{shownTime(booking.ends_at)}</td>
      <td>{stateLabel(booking)}</td>
      <td>{shownTime(booking.submitted_at)}</td>
      <td>{booking.details}</td>
      <td>
        {booking.state === "declined" ? (
          <span>Declined (final)</span>
        ) : (
          Object.keys(ACTION_LABELS)
            .filter((state) => state !== booking.state)
            .map((state) => (
              <button key={state} type="button" onClick={() => onAction(booking, state)}>
                {ACTION_LABELS[state]}
              </button>
            ))
        )}
      </td>
    </tr>
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

  function handleAction(booking, state) {
    if (state === "declined") {
      setDeclining(booking);
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
    return message ? <p role="alert">{message}</p> : <p>Loading…</p>;
  }

  const pageCount = Math.max(1, Math.ceil(list.total / list.page_size));

  return (
    <div>
      <button type="button" onClick={logOut}>
        Log out
      </button>

      <Filters
        onApply={(applied) => {
          setMessage("");
          // A new object every time, so pressing Apply always requests the list (W4).
          setFilters({ ...applied });
          setPage(1);
        }}
      />

      {message && <p role="alert">{message}</p>}

      <table>
        <thead>
          <tr>
            {["Name", "Email", "Phone", "Guests", "Start", "End", "State", "Submitted", "Details", "Actions"].map(
              (heading) => (
                <th key={heading} scope="col">
                  {heading}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {list.items.map((booking) => (
            <BookingRow key={booking.id} booking={booking} onAction={handleAction} />
          ))}
        </tbody>
      </table>
      {list.items.length === 0 && <p>No bookings found.</p>}

      <p>
        Page {list.page} of {pageCount}
      </p>
      <button type="button" disabled={list.page <= 1} onClick={() => setPage(list.page - 1)}>
        Previous
      </button>
      <button type="button" disabled={list.page >= pageCount} onClick={() => setPage(list.page + 1)}>
        Next
      </button>

      <DeleteClientData bookings={list.items} onDelete={eraseBooking} />

      {declining && (
        <DeclineDialog
          onCancel={() => setDeclining(null)}
          onConfirm={() => {
            const booking = declining;
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
