// Follow-up to the first review of the public pages: addresses (R1), pictures
// (I1, I2), the FAQ answers (Q2) and the privacy notice (F04 T3).
// Every expected value comes from docs/specs/public-pages.md and docs/specs/F04.md.

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

function topHeading() {
  return screen.getByRole("heading", { level: 1 }).textContent;
}

describe("R1: an address shows its page only when written exactly", () => {
  test.each([
    "/facilities/x",
    "/gallery/anything",
    "/events/1",
    "/faq/1",
    "/terms/old",
    "/privacy/2025",
    "/facilities/x/",
    "/facilitiesx",
  ])("%s shows the home page", (path) => {
    openAt(path);

    expect(topHeading()).toBe("Community Centre");
    expect(screen.getByRole("button", { name: "Send booking request" })).toBeInTheDocument();
    expect(document.title).toBe("Community Centre");
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("aria-current", "page");
  });

  test("/admin/x shows the home page, not the admin page", () => {
    openAt("/admin/x");

    expect(screen.getByRole("button", { name: "Send booking request" })).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "Bookings" })).not.toBeInTheDocument();
  });

  test.each([
    ["/facilities/", "Facilities"],
    ["/gallery/", "Gallery"],
    ["/events/", "Events"],
    ["/faq/", "Frequently asked questions"],
    ["/terms/", "Terms and conditions"],
    ["/privacy/", "Data and privacy notice"],
  ])("%s, with one / at its end, still shows its page", (path, heading) => {
    openAt(path);

    expect(topHeading()).toBe(heading);
  });

  test("/admin/ still shows the admin page", () => {
    openAt("/admin/");

    expect(screen.getByRole("heading", { level: 2, name: "Bookings" })).toBeInTheDocument();
    expect(screen.queryByRole("contentinfo")).not.toBeInTheDocument();
  });
});

const NOTE = "The pictures on this site are illustrations and do not show our centre.";
const WITH_PICTURES = ["/", "/facilities", "/gallery"];

describe("I1, I2: nothing suggests a picture shows the centre", () => {
  test.each(WITH_PICTURES)("%s: the note comes before the first picture", (path) => {
    openAt(path);

    const note = screen.getByText(NOTE);
    const first = document.querySelector("img");
    expect(note.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  test.each(WITH_PICTURES)("%s: no other text mentions a picture", (path) => {
    openAt(path);

    const main = screen.getByRole("main").cloneNode(true);
    for (const element of main.querySelectorAll("p")) {
      if (element.textContent === NOTE) {
        element.remove();
      }
    }
    expect(main.textContent).not.toMatch(/pictur|photo|image|illustrat/i);
  });

  test("every caption begins with A", () => {
    openAt("/gallery");

    const captions = screen.getAllByRole("figure").map((figure) => figure.textContent);
    expect(captions).toHaveLength(6);
    for (const caption of captions) {
      expect(caption).toMatch(/^A /);
    }
  });

  test.each(WITH_PICTURES)("%s: no caption or text alternative says the centre, our, we or us", (path) => {
    openAt(path);

    const texts = [
      ...[...document.querySelectorAll("img")].map((picture) => picture.getAttribute("alt")),
      ...screen.queryAllByRole("figure").map((figure) => figure.textContent),
    ];
    for (const text of texts) {
      expect(text).not.toMatch(/\bthe centre\b|\b(our|we|us)\b/i);
    }
  });
});

// Q2: question, exact answer.
const ANSWERS = [
  [
    "How do I book the hall?",
    "Send us a booking request. A request is not a booking until we accept it. We will contact you to discuss your event.",
  ],
  [
    "How much does it cost?",
    "The price depends on the length of the event, the number of guests and the facilities you need. We agree it with you by phone. No payment is taken on this website.",
  ],
  ["How many guests can the hall hold?", "The hall hosts up to 250 guests."],
  ["How far ahead can I book?", "You can send a request at most six months ahead of your event."],
  ["How long can an event last?", "An event can last between 1 and 12 hours."],
  [
    "Can two events take place on the same day?",
    "No. The hall hosts one event per day. An event that runs past midnight takes both days.",
  ],
  [
    "What happens if I do not hear back?",
    "If we have not answered a request within 48 hours, it lapses and its date is released, without further notice to you. You are welcome to send a new request.",
  ],
  ["When is the centre open?", "The centre is open 24 hours."],
  [
    "How do I have my details deleted?",
    "Ask us by phone or email, using the details at the foot of this page. If your event is still to come, we decline your request first, because we cannot hold a date without your details. Our data and privacy notice says more.",
  ],
];

function answerTo(question) {
  return screen.getByRole("heading", { level: 2, name: question }).nextElementSibling;
}

describe("Q2: every FAQ answer has exactly the text of the spec", () => {
  test.each(ANSWERS)("%s", (question, answer) => {
    openAt("/faq");

    const paragraph = answerTo(question);
    expect(paragraph.tagName).toBe("P");
    expect(paragraph.textContent.replace(/\s+/g, " ").trim()).toBe(answer);
  });

  test("each answer is one paragraph: the next element is the next question", () => {
    openAt("/faq");

    ANSWERS.forEach(([question], index) => {
      const after = answerTo(question).nextElementSibling;
      if (index < ANSWERS.length - 1) {
        expect(after.tagName).toBe("H2");
        expect(after.textContent).toBe(ANSWERS[index + 1][0]);
      } else {
        expect(after).toBeNull();
      }
    });
  });

  test("the links in the first and last answers", () => {
    openAt("/faq");

    expect(
      within(answerTo("How do I book the hall?")).getByRole("link", { name: "booking request" }),
    ).toHaveAttribute("href", "/#booking");
    expect(
      within(answerTo("How do I have my details deleted?")).getByRole("link", {
        name: "data and privacy notice",
      }),
    ).toHaveAttribute("href", "/privacy");
    expect(within(screen.getByRole("main")).getAllByRole("link")).toHaveLength(2);
  });
});

describe("F04 T3: how to ask, in the privacy notice", () => {
  test("says what happens when the event is still to come, under How to ask", () => {
    openAt("/privacy");

    const heading = screen.getByRole("heading", { level: 2, name: "How to ask" });
    let text = "";
    for (
      let element = heading.nextElementSibling;
      element && element.tagName !== "H2";
      element = element.nextElementSibling
    ) {
      text += ` ${element.textContent}`;
    }
    text = text.replace(/\s+/g, " ");
    expect(text).toContain(
      "If you ask us to erase your details while your event is still to come, we decline your request first, because we cannot hold a date without your details.",
    );
    expect(text).toMatch(/by phone or email/);
  });
});
