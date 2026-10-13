import { CENTRE, LAST_UPDATED } from "./centre.js";

// The terms and conditions (docs/specs/F04.md, T1, T4, T5).
export default function Terms() {
  return (
    <main>
      <h1>Terms and conditions</h1>
      <p>Last updated: {LAST_UPDATED}</p>

      <p>
        These terms apply to booking requests made through this website to {CENTRE.name},{" "}
        {CENTRE.address}. You can reach us on {CENTRE.phone} or at {CENTRE.email}.
      </p>

      <h2>A request is not a booking</h2>
      <p>
        Sending the form makes a booking request. It is not a booking until we accept it. We
        will contact you to discuss your event, and we may decline a request.
      </p>

      <h2>Price and details</h2>
      <p>
        The price depends on the length of the event, the number of guests and the facilities
        you need. The price and the final details are agreed with you by phone before we accept
        a request. No payment is taken through this website.
      </p>

      <h2>What can be requested</h2>
      <ul>
        <li>The hall hosts one event per day.</li>
        <li>An event can last at most 12 hours.</li>
        <li>A request can be made at most six months ahead of the event.</li>
        <li>You can have at most two requests at a time.</li>
      </ul>

      <h2>If you do not hear from us</h2>
      <p>
        A request holds its date from the moment it is sent. If we have not answered a request
        within 48 hours, it lapses and its date is released, without further notice to you. You
        are welcome to send a new request.
      </p>

      <h2>Your information</h2>
      <p>
        How we use the details you give us is set out in our data and privacy notice, which is a
        separate document.
      </p>
    </main>
  );
}
