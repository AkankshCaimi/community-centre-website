// The centre's details on the demonstration site (F04 T5, public pages N3, L3, L4)
// and the sentence about backups in the privacy notice (F04 T3).
// Every expected value comes from docs/specs/F04.md.

import { render, screen, within } from "@testing-library/react";
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

const NAME = "Lakeside Community Centre";
const ADDRESS = "12 Heronbrook Lane, Coventry CV1 9ZZ";
const PHONE = "01632 960123";
const EMAIL = "Akanksh.Caimi@warwick.ac.uk";

const PUBLIC = ["/", "/facilities", "/gallery", "/events", "/faq", "/terms", "/privacy"];

describe("T5: the centre's details are the fictional ones", () => {
  test.each(["/terms", "/privacy"])("%s shows the name, address, phone and email", (path) => {
    const text = openAt(path);

    for (const detail of [NAME, ADDRESS, PHONE, EMAIL]) {
      expect(text).toContain(detail);
    }
  });

  test.each(PUBLIC)("%s: the footer shows the address, phone and email", (path) => {
    openAt(path);

    const footer = screen.getByRole("contentinfo");
    for (const detail of [ADDRESS, PHONE, EMAIL]) {
      expect(footer).toHaveTextContent(detail);
    }
  });

  test.each(PUBLIC)("%s: the map link is built from the address", (path) => {
    openAt(path);

    expect(
      within(screen.getByRole("contentinfo")).getByRole("link", { name: "Find us on the map" }),
    ).toHaveAttribute(
      "href",
      "https://www.google.com/maps/search/?api=1&query=12%20Heronbrook%20Lane%2C%20Coventry%20CV1%209ZZ",
    );
  });

  test.each([...PUBLIC, "/admin"])("%s: no placeholder of the form [Centre …] remains", (path) => {
    openAt(path);

    expect(document.body.innerHTML).not.toMatch(/\[Centre|%5BCentre/);
  });

  test("the phone number is in the range reserved for fiction", () => {
    const text = openAt("/privacy");

    const numbers = text.match(/01632 ?\d{6}/g);
    expect(numbers).not.toBeNull();
    for (const number of numbers) {
      expect(number).toMatch(/^01632 960\d{3}$/);
    }
  });
});

describe("F04 T3: backups, in the privacy notice", () => {
  test("the sentence is under How long we keep it", () => {
    openAt("/privacy");

    const heading = screen.getByRole("heading", { level: 2, name: "How long we keep it" });
    let text = "";
    for (
      let element = heading.nextElementSibling;
      element && element.tagName !== "H2";
      element = element.nextElementSibling
    ) {
      text += ` ${element.textContent}`;
    }
    expect(text.replace(/\s+/g, " ")).toContain(
      "Deleted records may persist in secure backups for up to 7 days.",
    );
  });
});
