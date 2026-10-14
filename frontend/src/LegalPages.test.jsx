// F04 rules T1 to T5: the terms, the privacy notice, and the links to them.
// Every expected value comes from docs/specs/F04.md.

import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import App from "./App.jsx";

function openAt(path) {
  window.history.pushState({}, "", path);
  vi.stubGlobal("fetch", vi.fn());
  render(<App />);
  return document.body.textContent;
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, "", "/");
});

const CENTRE = ["Lakeside Community Centre", "12 Heronbrook Lane, Coventry CV1 9ZZ", "01632 960123", "Akanksh.Caimi@warwick.ac.uk"];

describe("T1: the two documents are separate pages", () => {
  test("/terms has the heading Terms and conditions and a last-updated date", () => {
    const text = openAt("/terms");

    expect(screen.getByRole("heading", { level: 1, name: "Terms and conditions" })).toBeInTheDocument();
    expect(text).toMatch(/Last updated: \d{1,2} [A-Z][a-z]+ \d{4}/);
    expect(screen.queryByRole("button", { name: "Send booking request" })).not.toBeInTheDocument();
  });

  test("/privacy has the heading Data and privacy notice and a last-updated date", () => {
    const text = openAt("/privacy");

    expect(
      screen.getByRole("heading", { level: 1, name: "Data and privacy notice" }),
    ).toBeInTheDocument();
    expect(text).toMatch(/Last updated: \d{1,2} [A-Z][a-z]+ \d{4}/);
    expect(screen.queryByRole("button", { name: "Send booking request" })).not.toBeInTheDocument();
  });

  test("the two documents are different", () => {
    const terms = openAt("/terms");
    document.body.innerHTML = "";
    const privacy = openAt("/privacy");

    expect(terms).not.toBe(privacy);
    expect(terms).not.toMatch(/Information Commissioner/);
    expect(privacy).not.toMatch(/lapses/);
  });
});

describe("T3: what the privacy notice states", () => {
  test.each([
    "Who we are",
    "What we collect",
    "Why, and our legal basis",
    "How long we keep it",
    "Who sees it",
    "Your rights",
    "How to ask",
    "How to complain",
  ])("has the heading %s", (heading) => {
    openAt("/privacy");

    expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
  });

  test.each([
    ["the data collected", /name, email( address)?, phone( number)?/i],
    ["the network address", /network address/i],
    ["the contract basis", /before entering (into )?a contract/i],
    ["the legitimate-interest basis", /legitimate interest/i],
    ["six months from submission", /six months from the day (the|your) request is submitted/i],
    ["automatic deletion", /deleted automatically/i],
    ["what is left afterwards", /only the date and the outcome/i],
    ["7 days for the network address", /network address[^.]*7 days|7 days[^.]*network address/i],
    ["the hosting company", /host/i],
    ["the right to a copy", /a copy of/i],
    ["the right to correction", /correct/i],
    ["the right to deletion", /delet/i],
    ["the right to restrict or object", /restrict[^.]*object|object[^.]*restrict/i],
    ["asking by phone or email", /by phone or (by )?email/i],
    ["free of charge", /free of charge/i],
    ["one month", /within one month/i],
    ["the ICO by name", /Information Commissioner's Office/],
    ["the ICO website", /ico\.org\.uk/],
    ["the ICO phone number", /0303 123 1113/],
  ])("states %s", (_what, pattern) => {
    expect(openAt("/privacy")).toMatch(pattern);
  });
});

describe("T4: what the terms state", () => {
  test.each([
    ["a request is not a booking until accepted", /not a booking until/i],
    ["price agreed by phone", /price[^.]*by phone|by phone[^.]*price/i],
    ["one event per day", /one event (per|a) day/i],
    ["at most 12 hours", /12 hours/i],
    ["at most six months ahead", /six months (ahead|in advance)/i],
    ["at most two requests at a time", /two (booking )?requests at a time/i],
    ["48 hours", /48 hours/i],
    ["the request lapses", /lapses/i],
    ["the date is released", /date is released/i],
    ["without further notice", /without further notice/i],
    ["the centre may decline", /may decline/i],
  ])("states that %s", (_what, pattern) => {
    expect(openAt("/terms")).toMatch(pattern);
  });
});

describe("T5: the centre's details", () => {
  test.each(["/terms", "/privacy"])("%s shows the centre details", (path) => {
    const text = openAt(path);

    for (const placeholder of CENTRE) {
      expect(text).toContain(placeholder);
    }
  });
});

describe("T2: the booking form links to the documents", () => {
  test.each([
    ["Read the terms and conditions", "/terms"],
    ["Read the data and privacy notice", "/privacy"],
  ])("%s opens %s in a new tab", (name, address) => {
    openAt("/");

    const link = screen.getByRole("link", { name });
    expect(link).toHaveAttribute("href", address);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  test("the tick labels are unchanged", () => {
    openAt("/");

    expect(screen.getByLabelText("I agree to the terms and conditions")).toHaveAttribute(
      "type",
      "checkbox",
    );
    expect(screen.getByLabelText("I have read the data and privacy notice")).toHaveAttribute(
      "type",
      "checkbox",
    );
  });
});
