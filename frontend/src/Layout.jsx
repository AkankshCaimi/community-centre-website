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
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <header>
        <nav aria-label="Main">
          <ul>
            {NAVIGATION.map(([name, address]) => (
              <li key={address}>
                <a href={address} aria-current={address === current ? "page" : undefined}>
                  {name}
                </a>
              </li>
            ))}
            <li>
              <a href="/#booking">Request a booking</a>
            </li>
          </ul>
        </nav>
      </header>
      <main id="main">{children}</main>
      <footer>
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
      </footer>
    </>
  );
}
