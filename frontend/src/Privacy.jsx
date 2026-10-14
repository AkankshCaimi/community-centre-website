import { CENTRE, LAST_UPDATED } from "./centre.js";

// The data and privacy notice (docs/specs/F04.md, T1, T3, T5).
export default function Privacy() {
  return (
    <>
      <h1>Data and privacy notice</h1>
      <p>Last updated: {LAST_UPDATED}</p>

      <h2>Who we are</h2>
      <p>
        {CENTRE.name}, {CENTRE.address}, is responsible for the information you give us through
        this website. You can reach us on {CENTRE.phone} or at {CENTRE.email}.
      </p>

      <h2>What we collect</h2>
      <p>
        When you send a booking request we collect your name, email address, phone number, the
        number of guests, the date and times of your event, and any event details you choose to
        give. We also record the network address of the device the request came from.
      </p>

      <h2>Why, and our legal basis</h2>
      <p>
        We use your details to handle your booking request and to contact you about it. The law
        allows this because these are steps taken at your request before entering a contract
        with you.
      </p>
      <p>
        We use the network address only to limit how many requests one connection can send in a
        day. The law allows this because we have a legitimate interest in protecting the form
        from abuse.
      </p>

      <h2>How long we keep it</h2>
      <p>
        We keep your details for six months from the day your request is submitted. They are
        then deleted automatically, leaving only the date and the outcome of the request, which
        do not identify you.
      </p>
      <p>We keep the network address for 7 days and then delete it.</p>

      <h2>Who sees it</h2>
      <p>
        Your details are seen by our management team and are stored by the company that hosts
        this website for us. We do not sell your details or pass them to anyone else.
      </p>

      <h2>Your rights</h2>
      <p>You have the right to:</p>
      <ul>
        <li>ask for a copy of the details we hold about you;</li>
        <li>ask us to correct details that are wrong;</li>
        <li>ask us to erase your details before the six months are up;</li>
        <li>ask us to restrict how we use your details, or object to our using them.</li>
      </ul>

      <h2>How to ask</h2>
      <p>
        Contact us by phone or email, using the details above. It is free of charge, and we will
        answer within one month.
      </p>
      <p>
        If you ask us to erase your details while your event is still to come, we decline your
        request first, because we cannot hold a date without your details.
      </p>

      <h2>How to complain</h2>
      <p>
        If you are unhappy with how we have used your details, please tell us first. You also
        have the right to complain to the Information Commissioner&apos;s Office, at ico.org.uk
        or on 0303 123 1113.
      </p>
    </>
  );
}
