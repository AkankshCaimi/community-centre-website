import { useEffect } from "react";

import { CENTRE } from "./centre.js";

const SITE = "Community Centre";

// The navigation of every public page (docs/specs/public-pages.md, L1).
const NAVIGATION = [
  ["Home", "/"],
  ["Facilities", "/facilities"],
  ["Gallery", "/gallery"],
  ["Events", "/events"],
  ["FAQ", "/faq"],
];

const MAP = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(CENTRE.address)}`;

// Header, main region and footer around a public page (L1 to L5, A3, A5, A6).
// `current` is the address of the page being shown, if it is in the navigation.
export default function Layout({ title, current, children }) {
  useEffect(() => {
    document.title = title === SITE ? SITE : `${title} – ${SITE}`;
  }, [title]);

  return (
    <>
      <a
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:shadow-md"
        href="#main"
      >
        Skip to main content
      </a>
      <header className="border-b bg-background/95">
        <nav aria-label="Main" className="mx-auto max-w-5xl px-4 py-4">
          <ul className="flex flex-wrap items-center gap-x-6 gap-y-2">
            {NAVIGATION.map(([name, address]) => (
              <li key={address}>
                <a
                  href={address}
                  aria-current={address === current ? "page" : undefined}
                  className="text-foreground no-underline hover:text-primary hover:underline aria-[current=page]:font-semibold aria-[current=page]:text-primary aria-[current=page]:underline"
                >
                  {name}
                </a>
              </li>
            ))}
            <li>
              <a
                href="/#booking"
                className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground no-underline hover:bg-primary/90"
              >
                Request a booking
              </a>
            </li>
          </ul>
        </nav>
      </header>
      <main id="main" className="mx-auto max-w-5xl px-4 py-8">
        {children}
      </main>
      <footer className="border-t bg-muted text-sm text-muted-foreground">
        <div className="mx-auto max-w-5xl space-y-1 px-4 py-8">
        <p>{CENTRE.address}</p>
        <p>
          <a href={MAP} target="_blank" rel="noopener noreferrer">
            Find us on the map
          </a>
        </p>
        <p>Phone: {CENTRE.phone}</p>
        <p>Email: {CENTRE.email}</p>
        <p>Open 24 hours</p>
        <p>
          <a href="/terms">Terms and conditions</a> ·{" "}
          <a href="/privacy">Data and privacy notice</a>
        </p>
        </div>
      </footer>
    </>
  );
}
