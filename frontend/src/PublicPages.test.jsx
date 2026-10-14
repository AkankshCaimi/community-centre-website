// The public pages: home, facilities, gallery, events, FAQ, header and footer.
// Every expected value comes from docs/specs/public-pages.md.

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
  document.title = "";
});

// Address, level-1 heading, navigation link marked as current, browser title.
const PAGES = [
  ["/", "Community Centre", "Home", "Community Centre"],
  ["/facilities", "Facilities", "Facilities", "Facilities – Community Centre"],
  ["/gallery", "Gallery", "Gallery", "Gallery – Community Centre"],
  ["/events", "Events", "Events", "Events – Community Centre"],
  ["/faq", "Frequently asked questions", "FAQ", "Frequently asked questions – Community Centre"],
  ["/terms", "Terms and conditions", null, "Terms and conditions – Community Centre"],
  ["/privacy", "Data and privacy notice", null, "Data and privacy notice – Community Centre"],
];

const NAVIGATION = [
  ["Home", "/"],
  ["Facilities", "/facilities"],
  ["Gallery", "/gallery"],
  ["Events", "/events"],
  ["FAQ", "/faq"],
  ["Request a booking", "/#booking"],
];

const NOTE = "The pictures on this site are illustrations and do not show our centre.";

// Caption and text alternative in the gallery (I4), in the order of the table.
const GALLERY = {
  "hero-exterior": [
    "A centre from outside",
    "A red-brick building with a glass entrance canopy and a lawn in front",
  ],
  "hero-hall": [
    "A hall laid out for a seated event",
    "Round tables with white cloths and chairs fill a large room, with a curtained platform at the far end",
  ],
  "hero-kitchen": [
    "A catering kitchen",
    "Stainless-steel worktops, gas hobs and large cooking pots",
  ],
  "gallery-dining": [
    "A table laid for dinner",
    "White linen, wine glasses, folded napkins and a centrepiece of white roses",
  ],
  "gallery-foyer": [
    "A foyer",
    "A reception desk, armchairs and potted plants in a bright room with tall windows",
  ],
  "gallery-stage": [
    "A stage",
    "Closed curtains, a wooden floor, a microphone stand and loudspeakers",
  ],
};

function pictures() {
  return [...document.querySelectorAll("img")];
}

// The file each picture on the page comes from, without folder or ending.
function files() {
  return pictures().map((picture) => picture.getAttribute("src").match(/([a-z-]+)[^/]*\.jpg/)[1]);
}

// A2, I3: pictures outside the gallery are decoration with an empty text alternative.
function expectDecoration(names) {
  expect(files()).toEqual(names);
  for (const picture of pictures()) {
    expect(picture).toHaveAttribute("alt", "");
  }
  expect(screen.queryAllByRole("figure")).toEqual([]);
  expect(screen.getByRole("main")).toHaveTextContent(NOTE);
}

describe.each(PAGES)("every public page: %s", (path, heading, current, title) => {
  test("R1, A1: shows its page under exactly one level-1 heading", () => {
    openAt(path);

    const top = screen.getAllByRole("heading", { level: 1 });
    expect(top.map((element) => element.textContent)).toEqual([heading]);
  });

  test("A1: no heading level is skipped", () => {
    openAt(path);

    const levels = screen.getAllByRole("heading").map((element) => Number(element.tagName[1]));
    expect(levels[0]).toBe(1);
    levels.forEach((level, index) => {
      if (index > 0) {
        expect(level - levels[index - 1]).toBeLessThanOrEqual(1);
      }
    });
  });

  test("L1: the navigation named Main has the six links, in order", () => {
    openAt(path);

    const links = within(screen.getByRole("navigation", { name: "Main" })).getAllByRole("link");
    expect(links.map((link) => [link.textContent, link.getAttribute("href")])).toEqual(NAVIGATION);
  });

  test("L1: the booking link is on the page", () => {
    openAt(path);

    expect(screen.getByRole("link", { name: "Request a booking" })).toHaveAttribute(
      "href",
      "/#booking",
    );
  });

  test("L2: only the link of this page is marked as current", () => {
    openAt(path);

    const marked = within(screen.getByRole("navigation", { name: "Main" }))
      .getAllByRole("link")
      .filter((link) => link.getAttribute("aria-current") === "page")
      .map((link) => link.textContent);
    expect(marked).toEqual(current === null ? [] : [current]);
  });

  test("L3: the footer shows the centre's details and Open 24 hours", () => {
    openAt(path);

    const footer = screen.getByRole("contentinfo");
    for (const text of ["12 Heronbrook Lane, Coventry CV1 9ZZ", "01632 960123", "Akanksh.Caimi@warwick.ac.uk", "Open 24 hours"]) {
      expect(footer).toHaveTextContent(text);
    }
  });

  test("L4: the footer links to the map in a new tab", () => {
    openAt(path);

    const link = within(screen.getByRole("contentinfo")).getByRole("link", {
      name: "Find us on the map",
    });
    expect(link).toHaveAttribute(
      "href",
      "https://www.google.com/maps/search/?api=1&query=12%20Heronbrook%20Lane%2C%20Coventry%20CV1%209ZZ",
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  test("L5: the footer links to the terms and the privacy notice in the same tab", () => {
    openAt(path);

    const footer = within(screen.getByRole("contentinfo"));
    const terms = footer.getByRole("link", { name: "Terms and conditions" });
    const privacy = footer.getByRole("link", { name: "Data and privacy notice" });
    expect(terms).toHaveAttribute("href", "/terms");
    expect(privacy).toHaveAttribute("href", "/privacy");
    expect(terms).not.toHaveAttribute("target");
    expect(privacy).not.toHaveAttribute("target");
  });

  test("A2: every image has an alt attribute", () => {
    openAt(path);

    for (const picture of pictures()) {
      expect(picture).toHaveAttribute("alt");
    }
  });

  test("I1: nothing says a picture shows the centre itself", () => {
    openAt(path);

    for (const picture of pictures()) {
      expect(picture.getAttribute("alt")).not.toMatch(/\b(the|our) (centre|hall)\b/i);
    }
    for (const figure of screen.queryAllByRole("figure")) {
      expect(figure.textContent).not.toMatch(/\b(the|our) (centre|hall)\b/i);
    }
  });

  test("A3: one main region, holding the level-1 heading; footer outside it", () => {
    openAt(path);

    const main = screen.getByRole("main");
    expect(within(main).getByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(main).not.toContainElement(screen.getByRole("contentinfo"));
    expect(main).not.toContainElement(screen.getByRole("navigation", { name: "Main" }));
  });

  test("A4: no element has a tabindex above 0", () => {
    openAt(path);

    for (const element of document.querySelectorAll("[tabindex]")) {
      expect(Number(element.getAttribute("tabindex"))).toBeLessThanOrEqual(0);
    }
  });

  test("A5: the first link is Skip to main content, and goes to the main region", () => {
    openAt(path);

    const first = screen.getAllByRole("link")[0];
    expect(first).toHaveTextContent("Skip to main content");
    expect(first.getAttribute("href")).toBe(`#${screen.getByRole("main").id}`);
    expect(screen.getByRole("main").id).not.toBe("");
  });

  test("A6: the browser title", () => {
    openAt(path);

    expect(document.title).toBe(title);
  });

  test("N2: the page sends no request when it opens", () => {
    openAt(path);

    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("the admin page", () => {
  test("has no public navigation and no footer", () => {
    openAt("/admin");

    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
    expect(screen.queryByRole("contentinfo")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Skip to main content" })).not.toBeInTheDocument();
  });
});

describe("the home page", () => {
  test("H1: says what the centre is, 250 guests, open 24 hours", () => {
    openAt("/");

    expect(screen.getByRole("heading", { level: 2, name: "About the centre" })).toBeInTheDocument();
    const main = screen.getByRole("main");
    expect(main).toHaveTextContent(/one event per day/);
    expect(main).toHaveTextContent(/up to 250 guests/);
    expect(main).toHaveTextContent(/open 24 hours/i);
  });

  test("H1, I2, I3: shows two pictures as decoration, with the note", () => {
    openAt("/");

    expectDecoration(["hero-exterior", "hero-hall"]);
  });

  test("H1: links to the facilities and the events", () => {
    openAt("/");

    expect(screen.getByRole("link", { name: "See the facilities" })).toHaveAttribute(
      "href",
      "/facilities",
    );
    expect(screen.getByRole("link", { name: "See the events we host" })).toHaveAttribute(
      "href",
      "/events",
    );
  });

  test("R2, N4: the booking form is in the section with the id booking, under Booking request", () => {
    openAt("/");

    const section = document.getElementById("booking");
    expect(
      within(section).getByRole("heading", { level: 2, name: "Booking request" }),
    ).toBeInTheDocument();
    expect(within(section).getByRole("button", { name: "Send booking request" })).toBeInTheDocument();
  });

  test("R1: an unknown address shows the home page", () => {
    openAt("/no-such-page");

    expect(screen.getByRole("heading", { level: 1, name: "Community Centre" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send booking request" })).toBeInTheDocument();
  });
});

describe("the other pages", () => {
  test.each(["/facilities", "/gallery", "/events", "/faq"])("%s does not show the booking form", (path) => {
    openAt(path);

    expect(screen.queryByRole("button", { name: "Send booking request" })).not.toBeInTheDocument();
  });

  test("F1: facilities lists exactly the five", () => {
    openAt("/facilities");

    const items = within(screen.getByRole("main")).getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual([
      "A/V system",
      "On-site parking",
      "Catering kitchen",
      "Main stage",
      "Seating for up to 250 guests",
    ]);
  });

  test("F1, I2, I3: facilities shows the kitchen picture as decoration, with the note", () => {
    openAt("/facilities");

    expectDecoration(["hero-kitchen"]);
  });

  test.each(["/events", "/faq", "/terms", "/privacy"])("%s shows no picture and no note", (path) => {
    const text = openAt(path);

    expect(pictures()).toEqual([]);
    expect(text).not.toContain(NOTE);
  });

  test("G1, I2: the gallery shows the note and all six pictures, in the order of the table", () => {
    openAt("/gallery");

    expect(screen.getByRole("main")).toHaveTextContent(NOTE);
    expect(files()).toEqual([
      "hero-exterior",
      "hero-hall",
      "hero-kitchen",
      "gallery-dining",
      "gallery-foyer",
      "gallery-stage",
    ]);
    expect(screen.getAllByRole("figure")).toHaveLength(6);
  });

  test.each(Object.entries(GALLERY))("G1, I4: %s has its caption and text alternative", (file, [caption, alternative]) => {
    openAt("/gallery");

    const figure = screen.getAllByRole("figure")[files().indexOf(file)];
    expect(figure).toHaveTextContent(caption);
    expect(within(figure).getByRole("img")).toHaveAttribute("alt", alternative);
  });

  test("A2, I4: gallery text alternatives are never empty, never shared, never the caption again", () => {
    openAt("/gallery");

    const alternatives = pictures().map((picture) => picture.getAttribute("alt"));
    expect(new Set(alternatives).size).toBe(6);
    for (const figure of screen.getAllByRole("figure")) {
      const alternative = within(figure).getByRole("img").getAttribute("alt");
      expect(alternative.trim()).not.toBe("");
      expect(alternative.toLowerCase()).not.toContain(figure.textContent.trim().toLowerCase());
    }
  });

  test("V1: events lists exactly the three, and the sentence", () => {
    openAt("/events");

    const main = screen.getByRole("main");
    expect(within(main).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Weddings",
      "Parties",
      "Cultural gatherings",
    ]);
    expect(main).toHaveTextContent("Planning something else? Send us a request and we will call you.");
  });

  test("Q1: the FAQ has the nine questions as level-2 headings, in order", () => {
    openAt("/faq");

    const questions = within(screen.getByRole("main")).getAllByRole("heading", { level: 2 });
    expect(questions.map((question) => question.textContent)).toEqual([
      "How do I book the hall?",
      "How much does it cost?",
      "How many guests can the hall hold?",
      "How far ahead can I book?",
      "How long can an event last?",
      "Can two events take place on the same day?",
      "What happens if I do not hear back?",
      "When is the centre open?",
      "How do I have my details deleted?",
    ]);
  });

  test("Q2: the answers state the decided facts and link to the privacy notice", () => {
    openAt("/faq");

    const main = screen.getByRole("main");
    for (const fact of [
      /not a booking until we accept it/,
      /No payment is taken (through|on) this website/,
      /up to 250 guests/,
      /six months/,
      /12 hours/,
      /one event per day/,
      /48 hours/,
      /open 24 hours/i,
    ]) {
      expect(main).toHaveTextContent(fact);
    }
    expect(within(main).getByRole("link", { name: /privacy notice/ })).toHaveAttribute(
      "href",
      "/privacy",
    );
  });
});
