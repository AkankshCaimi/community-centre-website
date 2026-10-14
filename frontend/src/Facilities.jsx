import Decoration from "./Decoration.jsx";
import { KITCHEN, NOTE } from "./pictures.js";

// The facilities of the centre (docs/specs/public-pages.md, F1).
export default function Facilities() {
  return (
    <>
      <h1>Facilities</h1>
      <ul>
        <li>A/V system</li>
        <li>On-site parking</li>
        <li>Catering kitchen</li>
        <li>Main stage</li>
        <li>Seating for up to 250 guests</li>
      </ul>
      <Decoration picture={KITCHEN} />
      <p>{NOTE}</p>
    </>
  );
}
