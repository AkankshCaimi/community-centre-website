// F01 form rules U1 to U7. Every expected value comes from docs/specs/F01.md;
// each test names the rule it checks.

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import BookingForm from "./BookingForm.jsx";

// Stands in for the CAPTCHA widget (spec: Replaceable parts).
function FakeCaptcha({ onToken }) {
  return (
    <button type="button" onClick={() => onToken("token-from-widget")}>
      Pass CAPTCHA
    </button>
  );
}

function jsonResponse(status, body) {
  return Promise.resolve({ status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) });
}

const SUBMIT = "Send booking request";
const TERMS = "I agree to the terms and conditions";
const PRIVACY = "I have read the data and privacy notice";
const NOT_ACCEPTED = "We could not accept this booking request. Please contact the centre.";

function renderForm() {
  render(<BookingForm CaptchaWidget={FakeCaptcha} />);
}

function fill(label, value) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

function fillValidForm({ name = "Alice Example" } = {}) {
  fill("Name", name);
  fill("Email", "alice@example.com");
  fill("Phone", "07700 900123");
  fill("Number of guests", "40");
  fill("Start", "2026-04-01T10:00");
  fill("End", "2026-04-01T14:00");
  fill("Additional details", "Birthday party");
}

async function tickBothAndPassCaptcha(user) {
  await user.click(screen.getByLabelText(TERMS));
  await user.click(screen.getByLabelText(PRIVACY));
  await user.click(screen.getByRole("button", { name: "Pass CAPTCHA" }));
}

async function submitValidForm(options) {
  const user = userEvent.setup();
  renderForm();
  fillValidForm(options);
  await tickBothAndPassCaptcha(user);
  await user.click(screen.getByRole("button", { name: SUBMIT }));
  return user;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("U1: what the form contains", () => {
  test.each(["Name", "Email", "Phone", "Number of guests", "Start", "End", "Additional details"])(
    "has an input labelled %s",
    (label) => {
      renderForm();
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    },
  );

  test("has two separate ticks, both unticked", () => {
    renderForm();
    const terms = screen.getByLabelText(TERMS);
    const privacy = screen.getByLabelText(PRIVACY);
    expect(terms).not.toBe(privacy);
    expect(terms).toHaveAttribute("type", "checkbox");
    expect(privacy).toHaveAttribute("type", "checkbox");
    expect(terms).not.toBeChecked();
    expect(privacy).not.toBeChecked();
  });

  test("shows the CAPTCHA widget and the submit button", () => {
    renderForm();
    expect(screen.getByRole("button", { name: "Pass CAPTCHA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: SUBMIT })).toBeInTheDocument();
  });

  test("Start and End are date-and-time inputs", () => {
    renderForm();
    expect(screen.getByLabelText("Start")).toHaveAttribute("type", "datetime-local");
    expect(screen.getByLabelText("End")).toHaveAttribute("type", "datetime-local");
  });
});

describe("U2: inputs carry the limits", () => {
  test.each([
    ["Name", "100"],
    ["Email", "254"],
    ["Phone", "30"],
    ["Additional details", "2000"],
  ])("%s has a maximum length of %s", (label, limit) => {
    renderForm();
    expect(screen.getByLabelText(label)).toHaveAttribute("maxlength", limit);
  });

  test("Number of guests runs from 1 to 250 in steps of 1", () => {
    renderForm();
    const guests = screen.getByLabelText("Number of guests");
    expect(guests).toHaveAttribute("type", "number");
    expect(guests).toHaveAttribute("min", "1");
    expect(guests).toHaveAttribute("max", "250");
    expect(guests).toHaveAttribute("step", "1");
  });
});

describe("U3: when the submit button is enabled", () => {
  test("disabled at first", () => {
    renderForm();
    expect(screen.getByRole("button", { name: SUBMIT })).toBeDisabled();
  });

  test("disabled with both ticks but no CAPTCHA token", async () => {
    const user = userEvent.setup();
    renderForm();
    await user.click(screen.getByLabelText(TERMS));
    await user.click(screen.getByLabelText(PRIVACY));
    expect(screen.getByRole("button", { name: SUBMIT })).toBeDisabled();
  });

  test.each([
    ["terms", PRIVACY],
    ["privacy", TERMS],
  ])("disabled with a CAPTCHA token but no %s tick", async (_missing, ticked) => {
    const user = userEvent.setup();
    renderForm();
    await user.click(screen.getByLabelText(ticked));
    await user.click(screen.getByRole("button", { name: "Pass CAPTCHA" }));
    expect(screen.getByRole("button", { name: SUBMIT })).toBeDisabled();
  });

  test("enabled with both ticks and a CAPTCHA token", async () => {
    const user = userEvent.setup();
    renderForm();
    await tickBothAndPassCaptcha(user);
    expect(screen.getByRole("button", { name: SUBMIT })).toBeEnabled();
  });

  test("disabled again when a tick is removed", async () => {
    const user = userEvent.setup();
    renderForm();
    await tickBothAndPassCaptcha(user);
    await user.click(screen.getByLabelText(TERMS));
    expect(screen.getByRole("button", { name: SUBMIT })).toBeDisabled();
  });
});

describe("U4: what submitting sends", () => {
  test("one POST to /api/v1/bookings with the request fields as JSON", async () => {
    fetch.mockReturnValue(jsonResponse(201, { id: 1, state: "submitted" }));

    await submitValidForm();

    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe("/api/v1/bookings");
    expect(options.method).toBe("POST");
    expect(options.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(options.body)).toEqual({
      name: "Alice Example",
      email: "alice@example.com",
      phone: "07700 900123",
      guest_count: 40,
      starts_at: "2026-04-01T10:00",
      ends_at: "2026-04-01T14:00",
      details: "Birthday party",
      terms_accepted: true,
      privacy_notice_accepted: true,
      captcha_token: "token-from-widget",
    });
  });

  test("the button is disabled while the request is in flight", async () => {
    fetch.mockReturnValue(new Promise(() => {}));

    await submitValidForm();

    expect(screen.getByRole("button", { name: SUBMIT })).toBeDisabled();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});

describe("U5: confirmation after 201", () => {
  test("the form is replaced by the confirmation", async () => {
    fetch.mockReturnValue(jsonResponse(201, { id: 1, state: "submitted" }));

    await submitValidForm();

    expect(
      await screen.findByText("Thank you, Alice Example. Your booking request has been sent."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: SUBMIT })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
  });

  test("markup in the name is shown as text, not interpreted", async () => {
    fetch.mockReturnValue(jsonResponse(201, { id: 1, state: "submitted" }));
    const name = '<img src="x" onerror="alert(1)"><b>Bob</b>';

    await submitValidForm({ name });

    expect(
      await screen.findByText(`Thank you, ${name}. Your booking request has been sent.`),
    ).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
    expect(document.querySelector("b")).toBeNull();
  });
});

describe("U6: messages for other responses", () => {
  test.each([
    ["required", "This field is required."],
    ["too_long", "This is too long."],
    ["invalid", "This is not valid."],
    ["out_of_range", "Guests must be between 1 and 250."],
    ["in_past", "The start must be in the future."],
    ["too_far_ahead", "Bookings can be made at most 6 months ahead."],
    ["duration_too_short", "A booking must be at least 1 hour."],
    ["duration_too_long", "A booking can be at most 12 hours."],
  ])("400 with code %s shows its message", async (code, message) => {
    fetch.mockReturnValue(
      jsonResponse(400, { error: "validation_failed", fields: { name: code } }),
    );

    await submitValidForm();

    expect(await screen.findByText(message)).toBeInTheDocument();
  });

  test("400 shows each message next to its own field", async () => {
    fetch.mockReturnValue(
      jsonResponse(400, {
        error: "validation_failed",
        fields: { email: "invalid", guest_count: "out_of_range" },
      }),
    );

    await submitValidForm();

    await screen.findByText("This is not valid.");
    expect(screen.getByLabelText("Email")).toHaveAccessibleDescription("This is not valid.");
    expect(screen.getByLabelText("Number of guests")).toHaveAccessibleDescription(
      "Guests must be between 1 and 250.",
    );
    expect(screen.getByLabelText("Name")).not.toHaveAccessibleDescription();
  });

  test.each([
    [
      409,
      { error: "not_accepted" },
      "We could not accept this booking request. Please contact the centre.",
    ],
    [
      429,
      { error: "rate_limited", message: "Too many responses submitted. Try again later." },
      "Too many responses submitted. Try again later.",
    ],
    [403, { error: "captcha_failed" }, "The CAPTCHA check failed. Please try again."],
    [400, { error: "invalid_request" }, "Something went wrong. Please try again later."],
    [413, { error: "request_entity_too_large" }, "Something went wrong. Please try again later."],
    [415, { error: "unsupported_media_type" }, "Something went wrong. Please try again later."],
    [500, { error: "internal_server_error" }, "Something went wrong. Please try again later."],
  ])("%i %o shows its message", async (status, body, message) => {
    fetch.mockReturnValue(jsonResponse(status, body));

    await submitValidForm();

    expect(await screen.findByText(message)).toBeInTheDocument();
  });

  test("no response at all shows the general message", async () => {
    fetch.mockRejectedValue(new TypeError("Failed to fetch"));

    await submitValidForm();

    expect(
      await screen.findByText("Something went wrong. Please try again later."),
    ).toBeInTheDocument();
  });

  test("a response that is not JSON shows the general message", async () => {
    fetch.mockReturnValue(
      Promise.resolve({ status: 502, ok: false, json: () => Promise.reject(new SyntaxError("x")) }),
    );

    await submitValidForm();

    expect(
      await screen.findByText("Something went wrong. Please try again later."),
    ).toBeInTheDocument();
  });

  test("the form stays filled in and can be sent again", async () => {
    fetch.mockReturnValue(jsonResponse(409, { error: "not_accepted" }));

    await submitValidForm();
    await screen.findByText(NOT_ACCEPTED);

    expect(screen.getByLabelText("Name")).toHaveValue("Alice Example");
    expect(screen.getByLabelText("Email")).toHaveValue("alice@example.com");
    expect(screen.getByLabelText("Phone")).toHaveValue("07700 900123");
    expect(screen.getByLabelText("Number of guests")).toHaveValue(40);
    expect(screen.getByLabelText("Start")).toHaveValue("2026-04-01T10:00");
    expect(screen.getByLabelText("End")).toHaveValue("2026-04-01T14:00");
    expect(screen.getByLabelText("Additional details")).toHaveValue("Birthday party");
    await waitFor(() => expect(screen.getByRole("button", { name: SUBMIT })).toBeEnabled());
  });

  test("an earlier message is cleared when the next attempt succeeds", async () => {
    fetch.mockReturnValueOnce(jsonResponse(409, { error: "not_accepted" }));
    fetch.mockReturnValueOnce(jsonResponse(201, { id: 1, state: "submitted" }));

    const user = await submitValidForm();
    await screen.findByText(NOT_ACCEPTED);
    await waitFor(() => expect(screen.getByRole("button", { name: SUBMIT })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: SUBMIT }));

    await screen.findByText("Thank you, Alice Example. Your booking request has been sent.");
    expect(screen.queryByText(NOT_ACCEPTED)).not.toBeInTheDocument();
  });
});

describe("G1: no message says whether a day is available", () => {
  test("a 409 says nothing about days or existing bookings", async () => {
    fetch.mockReturnValue(jsonResponse(409, { error: "not_accepted" }));

    await submitValidForm();
    const alert = await screen.findByText(NOT_ACCEPTED);

    expect(alert.textContent).not.toMatch(/day|date|taken|available|already/i);
  });
});

describe("U7: the stand-in CAPTCHA widget", () => {
  const ROBOT = "I am not a robot";

  test("is a tick that is unticked at first", () => {
    render(<BookingForm />);
    const robot = screen.getByLabelText(ROBOT);
    expect(robot).toHaveAttribute("type", "checkbox");
    expect(robot).not.toBeChecked();
  });

  test("ticking it produces a token, so the form can be sent", async () => {
    const user = userEvent.setup();
    render(<BookingForm />);
    await user.click(screen.getByLabelText(TERMS));
    await user.click(screen.getByLabelText(PRIVACY));
    expect(screen.getByRole("button", { name: SUBMIT })).toBeDisabled();

    await user.click(screen.getByLabelText(ROBOT));

    expect(screen.getByRole("button", { name: SUBMIT })).toBeEnabled();
  });

  test("the token it sends is stand-in-token", async () => {
    fetch.mockReturnValue(jsonResponse(201, { id: 1, state: "submitted" }));
    const user = userEvent.setup();
    render(<BookingForm />);
    fillValidForm();
    await user.click(screen.getByLabelText(TERMS));
    await user.click(screen.getByLabelText(PRIVACY));
    await user.click(screen.getByLabelText(ROBOT));
    await user.click(screen.getByRole("button", { name: SUBMIT }));

    expect(JSON.parse(fetch.mock.calls[0][1].body).captcha_token).toBe("stand-in-token");
  });

  test("unticking it takes the token away again", async () => {
    const user = userEvent.setup();
    render(<BookingForm />);
    await user.click(screen.getByLabelText(TERMS));
    await user.click(screen.getByLabelText(PRIVACY));
    await user.click(screen.getByLabelText(ROBOT));
    await user.click(screen.getByLabelText(ROBOT));

    expect(screen.getByRole("button", { name: SUBMIT })).toBeDisabled();
  });
});

describe("U6: 400 messages for the ticks, the CAPTCHA and unknown fields", () => {
  test.each([
    ["terms_accepted", TERMS],
    ["privacy_notice_accepted", PRIVACY],
  ])("an error for %s is shown next to that tick", async (field, label) => {
    fetch.mockReturnValue(
      jsonResponse(400, { error: "validation_failed", fields: { [field]: "required" } }),
    );

    await submitValidForm();

    await screen.findByText("This field is required.");
    expect(screen.getByLabelText(label)).toHaveAccessibleDescription("This field is required.");
  });

  test("an error for captcha_token is shown", async () => {
    fetch.mockReturnValue(
      jsonResponse(400, { error: "validation_failed", fields: { captcha_token: "too_long" } }),
    );

    await submitValidForm();

    expect(await screen.findByText("This is too long.")).toBeInTheDocument();
  });

  test.each([
    ["no fields at all", {}],
    ["a field the form does not have", { mystery: "invalid" }],
  ])("400 naming %s shows the general message", async (_case, fields) => {
    fetch.mockReturnValue(jsonResponse(400, { error: "validation_failed", fields }));

    await submitValidForm();

    expect(
      await screen.findByText("Something went wrong. Please try again later."),
    ).toBeInTheDocument();
  });

  test("a known field alongside an unknown one shows only the field message", async () => {
    fetch.mockReturnValue(
      jsonResponse(400, {
        error: "validation_failed",
        fields: { name: "required", mystery: "invalid" },
      }),
    );

    await submitValidForm();

    await screen.findByText("This field is required.");
    expect(
      screen.queryByText("Something went wrong. Please try again later."),
    ).not.toBeInTheDocument();
  });
});

