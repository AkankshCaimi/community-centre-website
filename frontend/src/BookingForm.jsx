import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import StandInCaptcha from "./StandInCaptcha.jsx";

// Messages from docs/specs/F01.md, "Messages".
const FIELD_MESSAGES = {
  required: "This field is required.",
  too_long: "This is too long.",
  invalid: "This is not valid.",
  out_of_range: "Guests must be between 1 and 250.",
  in_past: "The start must be in the future.",
  too_far_ahead: "Bookings can be made at most 6 months ahead.",
  duration_too_short: "A booking must be at least 1 hour.",
  duration_too_long: "A booking can be at most 12 hours.",
};

const GENERAL_MESSAGE = "Something went wrong. Please try again later.";

// Deliberately says nothing about whether a day is available (spec G1).
const NOT_ACCEPTED_MESSAGE = "We could not accept this booking request. Please contact the centre.";

// Every field the form can show an error next to.
const FORM_FIELDS = [
  "name",
  "email",
  "phone",
  "guest_count",
  "starts_at",
  "ends_at",
  "details",
  "terms_accepted",
  "privacy_notice_accepted",
  "captcha_token",
];

const EMPTY = {
  name: "",
  email: "",
  phone: "",
  guest_count: "",
  starts_at: "",
  ends_at: "",
  details: "",
};

function messageFor(status) {
  if (status === 409) {
    return NOT_ACCEPTED_MESSAGE;
  }
  if (status === 429) {
    return "Too many responses submitted. Try again later.";
  }
  if (status === 403) {
    return "The CAPTCHA check failed. Please try again.";
  }
  return GENERAL_MESSAGE;
}

// The field errors of a 400 response that the form has a place for.
function knownFieldErrors(fields) {
  const known = {};
  for (const name of FORM_FIELDS) {
    if (fields && Object.hasOwn(fields, name)) {
      known[name] = FIELD_MESSAGES[fields[name]] ?? GENERAL_MESSAGE;
    }
  }
  return known;
}

function FieldError({ id, message }) {
  if (!message) {
    return null;
  }
  return (
    <p id={id} role="alert" className="mt-1 text-sm text-destructive">
      {message}
    </p>
  );
}

function Field({ label, name, error, as = "input", ...inputProps }) {
  const errorId = `${name}-error`;
  const Control = as === "textarea" ? Textarea : Input;
  return (
    <div className="space-y-2">
      <Label htmlFor={name}>{label}</Label>
      <Control id={name} name={name} aria-describedby={error ? errorId : undefined} {...inputProps} />
      <FieldError id={errorId} message={error} />
    </div>
  );
}

function Tick({ label, name, checked, onChange, error, documentAddress, documentLink }) {
  const errorId = `${name}-error`;
  return (
    <div className="text-sm">
      <input
        id={name}
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        aria-describedby={error ? errorId : undefined}
        className="mr-2 size-4 align-middle accent-primary"
      />
      <label htmlFor={name}>{label}</label>{" "}
      {/* The document opens in a new tab so the half-filled form is not lost (F04 T2). */}
      <a href={documentAddress} target="_blank" rel="noopener noreferrer">
        {documentLink}
      </a>
      <FieldError id={errorId} message={error} />
    </div>
  );
}

export default function BookingForm({ CaptchaWidget = StandInCaptcha }) {
  const [values, setValues] = useState(EMPTY);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [captchaToken, setCaptchaToken] = useState("");
  const [sending, setSending] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});
  const [message, setMessage] = useState("");
  const [sentName, setSentName] = useState(null);

  const onToken = useCallback((token) => setCaptchaToken(token), []);

  function field(name) {
    return {
      name,
      value: values[name],
      onChange: (event) => setValues((current) => ({ ...current, [name]: event.target.value })),
      error: fieldErrors[name],
    };
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSending(true);
    setFieldErrors({});
    setMessage("");

    try {
      const response = await fetch("/api/v1/bookings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: values.name,
          email: values.email,
          phone: values.phone,
          guest_count: Number(values.guest_count),
          starts_at: values.starts_at,
          ends_at: values.ends_at,
          details: values.details,
          terms_accepted: termsAccepted,
          privacy_notice_accepted: privacyAccepted,
          captcha_token: captchaToken,
        }),
      });
      const body = await response.json();
      const errors = response.status === 400 ? knownFieldErrors(body.fields) : {};

      if (response.status === 201) {
        setSentName(values.name);
      } else if (Object.keys(errors).length > 0) {
        setFieldErrors(errors);
      } else {
        setMessage(messageFor(response.status));
      }
    } catch {
      setMessage(GENERAL_MESSAGE);
    } finally {
      setSending(false);
    }
  }

  if (sentName !== null) {
    return <p role="status">Thank you, {sentName}. Your booking request has been sent.</p>;
  }

  const canSubmit = termsAccepted && privacyAccepted && captchaToken !== "" && !sending;

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      <Field label="Name" type="text" maxLength={100} {...field("name")} />
      <Field label="Email" type="email" maxLength={254} {...field("email")} />
      <Field label="Phone" type="tel" maxLength={30} {...field("phone")} />
      <Field
        label="Number of guests"
        type="number"
        min={1}
        max={250}
        step={1}
        {...field("guest_count")}
      />
      <Field label="Start" type="datetime-local" {...field("starts_at")} />
      <Field label="End" type="datetime-local" {...field("ends_at")} />
      <Field label="Additional details" as="textarea" maxLength={2000} {...field("details")} />

      <Tick
        label="I agree to the terms and conditions"
        name="terms_accepted"
        checked={termsAccepted}
        onChange={setTermsAccepted}
        error={fieldErrors.terms_accepted}
        documentAddress="/terms"
        documentLink="Read the terms and conditions"
      />
      <Tick
        label="I have read the data and privacy notice"
        name="privacy_notice_accepted"
        checked={privacyAccepted}
        onChange={setPrivacyAccepted}
        error={fieldErrors.privacy_notice_accepted}
        documentAddress="/privacy"
        documentLink="Read the data and privacy notice"
      />

      <CaptchaWidget onToken={onToken} />
      <FieldError id="captcha_token-error" message={fieldErrors.captcha_token} />

      {message && (
        <p role="alert" className="text-sm text-destructive">
          {message}
        </p>
      )}

      <Button type="submit" disabled={!canSubmit}>
        Send booking request
      </Button>
    </form>
  );
}
