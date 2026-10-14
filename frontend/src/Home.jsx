import BookingForm from "./BookingForm.jsx";
import Decoration from "./Decoration.jsx";
import { EXTERIOR, HALL, NOTE } from "./pictures.js";

// The home page, with the booking form as its last section
// (docs/specs/public-pages.md, H1 and R2).
export default function Home() {
  return (
    <>
      <h1>Community Centre</h1>

      <section>
        <h2>About the centre</h2>
        <p>{NOTE}</p>
        <Decoration picture={EXTERIOR} />
        <p>
          We have one hall for hire, for one event per day. It hosts up to 250 guests, and the
          centre is open 24 hours.
        </p>
        <Decoration picture={HALL} />
        <p>
          <a href="/facilities">See the facilities</a>
        </p>
        <p>
          <a href="/events">See the events we host</a>
        </p>
      </section>

      <section id="booking" className="mt-12 scroll-mt-4 rounded-xl border bg-card p-6 shadow-sm [&>h2:first-child]:mt-0">
        <h2>Booking request</h2>
        <BookingForm />
      </section>
    </>
  );
}
