import { Card } from "@/components/ui/card";

import Decoration from "./Decoration.jsx";
import { KITCHEN, NOTE } from "./pictures.js";

// The facilities of the centre (docs/specs/public-pages.md, F1).
export default function Facilities() {
  return (
    <>
      <h1>Facilities</h1>
      <ul className="my-6 grid list-none grid-cols-1 gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
        <li>
          <Card className="h-full font-medium">A/V system</Card>
        </li>
        <li>
          <Card className="h-full font-medium">On-site parking</Card>
        </li>
        <li>
          <Card className="h-full font-medium">Catering kitchen</Card>
        </li>
        <li>
          <Card className="h-full font-medium">Main stage</Card>
        </li>
        <li>
          <Card className="h-full font-medium">Seating for up to 250 guests</Card>
        </li>
      </ul>
      <p>{NOTE}</p>
      <Decoration picture={KITCHEN} />
    </>
  );
}
