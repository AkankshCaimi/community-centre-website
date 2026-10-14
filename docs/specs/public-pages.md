# Public pages

Spec for the pages a visitor sees: home, facilities, gallery, events, FAQ, and the header and footer around them. Requirements FR1 to FR4, FR6, FR7 and FR14 of `docs/requirements.md`.

Each rule has a number; tests cite it.

## Content

| Rule | |
|---|---|
| N1 | **All content is our own text, written into the React application.** Nothing on these pages is supplied by a client and nothing is read from the API or the database. The escaping and log-safety rules of F01 and F02 therefore do not apply to them. |
| N2 | These pages send no request of their own. The only requests from a public page are those of the booking form (F01), where it is shown. |
| N3 | The centre's name, address, phone and email come from `frontend/src/centre.js`, as in F04 T5. They are still placeholders. |
| N4 | The booking form of F01 is not changed: same component, same fields, labels, messages and requests. |

## Addresses

| Address | Page | Heading (level 1) |
|---|---|---|
| `/` | Home, with the booking form as its last section | Community Centre |
| `/facilities` | Facilities | Facilities |
| `/gallery` | Gallery | Gallery |
| `/events` | Events | Events |
| `/faq` | FAQ | Frequently asked questions |
| `/terms` | Terms and conditions (F04) | unchanged |
| `/privacy` | Data and privacy notice (F04) | unchanged |
| `/admin` | Admin page (F02) | unchanged |

| Rule | |
|---|---|
| R1 | Each address above shows its page. Any other address shows the home page, as today. |
| R2 | The booking form stays at `/` (F02: "The public form of F01 stays at `/`"), under the level-2 heading "Booking request", in a section with the id `booking`. |
| R3 | Every link between pages is an ordinary link (`<a href>`) that loads the page. |

## Header and footer

They appear on every public page: home, facilities, gallery, events, FAQ, terms and privacy. The admin page has neither.

| Rule | |
|---|---|
| L1 | The header holds a navigation region named "Main" with these links, in this order: "Home" (`/`), "Facilities" (`/facilities`), "Gallery" (`/gallery`), "Events" (`/events`), "FAQ" (`/faq`), "Request a booking" (`/#booking`). |
| L2 | The link of the page being shown is marked `aria-current="page"`; no other link is. "Request a booking" is never marked. |
| L3 | The footer shows the centre's address, phone and email (N3), and the text "Open 24 hours" (FR14). |
| L4 | The footer has a link "Find us on the map" to `https://www.google.com/maps/search/?api=1&query=<the centre's address, URL-encoded>`, opening in a new tab with `rel="noopener noreferrer"`. |
| L5 | The footer has the links "Terms and conditions" (`/terms`) and "Data and privacy notice" (`/privacy`), opening in the same tab. |

## Pages

| Rule | |
|---|---|
| H1 | **Home.** Under the heading "About the centre": what the centre is (one hall for hire, for one event per day), that it hosts up to 250 guests, and that it is open 24 hours. The pictures `hero-exterior.jpg` and `hero-hall.jpg`, as decoration (I3), and the note of I2. Links to "See the facilities" (`/facilities`) and "See the events we host" (`/events`). Then the booking form (R2). |
| F1 | **Facilities.** A list of exactly these five: "A/V system", "On-site parking", "Catering kitchen", "Main stage", "Seating for up to 250 guests". The picture `hero-kitchen.jpg`, as decoration (I3), and the note of I2. |
| G1 | **Gallery.** The note of I2, then all six pictures in the order of the table under Images, each with its caption shown under it and its text alternative (I4). |
| V1 | **Events.** A list of exactly these three: "Weddings", "Parties", "Cultural gatherings", followed by the sentence "Planning something else? Send us a request and we will call you." No picture. |
| Q1 | **FAQ.** Each question is a level-2 heading, followed by its answer. The questions, in order: "How do I book the hall?", "How much does it cost?", "How many guests can the hall hold?", "How far ahead can I book?", "How long can an event last?", "Can two events take place on the same day?", "What happens if I do not hear back?", "When is the centre open?", "How do I have my details deleted?" |
| Q2 | Every answer states only what is already decided elsewhere: a request is not a booking until we accept it and we will phone; the price is agreed by phone and no payment is taken on the website; up to 250 guests; at most six months ahead; between 1 and 12 hours; one event per day; an unanswered request lapses after 48 hours and its date is released; open 24 hours; call us to have details deleted, with a link to the privacy notice. |

## Accessibility

| Rule | |
|---|---|
| A1 | Every page has exactly one level-1 heading, and no heading level is skipped. |
| A2 | Every image has an `alt` attribute. In the gallery it is the text alternative of I4: never empty, never the same for two pictures, and never a repeat of the caption beside it. Everywhere else the picture is decoration and the attribute is empty (I3), so a screen reader passes over it. |
| A3 | The page content is in the one `main` region of the page, the navigation in a `nav` region, the footer in a `footer` region. |
| A4 | Everything a visitor can use is a link, a button or a form field, reachable with the Tab key in the order it is read. No element has a `tabindex` above 0. |
| A5 | The first link on every public page is "Skip to main content", which goes to the `main` region. |
| A6 | The browser title is "<level-1 heading> – Community Centre"; on the home page it is "Community Centre". |

## Images

Six pictures supplied by the author on 2026-10-14, kept in `frontend/src/images/`. **They are stand-ins: illustrations of the kind of place the centre is, not photographs of the centre.**

| Rule | |
|---|---|
| I1 | No caption, text alternative or sentence says or suggests that a picture shows the centre itself. |
| I2 | Every page that shows a picture carries this sentence, as ordinary text: "The pictures on this site are illustrations and do not show our centre." |
| I3 | On the home and facilities pages the pictures are decoration: they add nothing the text does not say, so each has an empty text alternative (`alt=""`) and no caption. |
| I4 | In the gallery the pictures are the content. Each has the caption and the text alternative below. The text alternative describes what is in the picture and does not repeat the caption, so a screen reader does not read the same words twice. |

| File | Caption (gallery) | Text alternative (gallery) |
|---|---|---|
| `hero-exterior.jpg` | A centre from outside | A red-brick building with a glass entrance canopy and a lawn in front |
| `hero-hall.jpg` | A hall laid out for a seated event | Round tables with white cloths and chairs fill a large room, with a curtained platform at the far end |
| `hero-kitchen.jpg` | A catering kitchen | Stainless-steel worktops, gas hobs and large cooking pots |
| `gallery-dining.jpg` | A table laid for dinner | White linen, wine glasses, folded napkins and a centrepiece of white roses |
| `gallery-foyer.jpg` | A foyer | A reception desk, armchairs and potted plants in a bright room with tall windows |
| `gallery-stage.jpg` | A stage | Closed curtains, a wooden floor, a microphone stand and loudspeakers |

Two further pictures, `hero-celebration.jpg` and `hero-gathering.jpg`, showed people. The author removed them on 2026-10-14; no picture on the site shows a person.

## Tests

In `frontend/src/PublicPages.test.jsx`. Small: each page renders with its heading (addresses table, R1), the navigation and footer are on every public page and not on the admin page (L1 to L5), the booking link is on every public page (L1), the links have the addresses above, and the checks of A1, A2, A5 and A6. No mutation run: there is no logic here beyond choosing a page by its address.

## Known limits

- **The centre's details are placeholders** and must be replaced before the site goes live. With a placeholder address, the map link leads nowhere useful.
- **The pictures are stand-ins.** FR1 and FR3 ask for images of the centre; until real photographs replace these, the site shows illustrations and says so (I2).
- **The pictures are used as supplied.** They are 100 to 230 KB each at 1536 by 864 and are not resized for small screens.
- **Nobody but a developer can change the content**; a change of text or picture is a change to the code.
- **Opening a page other than `/` directly** needs the host to serve the application for every address. Hosting is not built yet.
- **The map link sends the visitor to Google Maps.** Nothing is sent until they follow it.
- **An unknown address shows the home page**, not a "not found" page.
- **Keyboard use is checked by structure** (links, buttons, order), not by a person tabbing through a browser.

## Where this differs

| Earlier document | Now |
|---|---|
| FR7: the footer shows "opening times" | It shows "Open 24 hours" (FR14, decision 7 of `docs/reviews/R1.md`). |
| FR5: a "booking request page" | The form is the last section of the home page, at `/#booking`; it has no page of its own. |
| F04 T1: `/terms` and `/privacy` are pages of their own | They are, and now also carry the header and footer. |

## Confirmed by the author

On 2026-10-14: the home page at `/` with the booking form as its last section (R2); "Open 24 hours" in the footer (L3); the pictures, that they are stand-ins to be described as illustrations, and the removal of the two that showed people, leaving six.

## Proposed by the implementer

Not yet confirmed by the author:

- The addresses, link names, headings and browser titles.
- The header and footer on the terms and privacy pages, and not on the admin page.
- The map link going to Google Maps, built from the address.
- Phone and email in the footer as plain text, not `tel:` and `mailto:` links, while they are placeholders.
- Which picture goes on which page, and every caption and text alternative (I4).
- The sentence of I2, and showing it on every page that has a picture.
- Treating the pictures outside the gallery as decoration with an empty text alternative (I3). The author asked that a picture which only repeats its caption gets a minimal or empty one; outside the gallery a stand-in adds nothing to the text beside it, and inside the gallery the text alternatives were rewritten so none repeats its caption.
- The nine FAQ questions (Q1) and the limit of their answers to decided facts (Q2).
- The skip link (A5) and the browser titles (A6).
- An unknown address still showing the home page.
