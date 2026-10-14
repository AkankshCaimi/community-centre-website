import { Card } from "@/components/ui/card";

// The events the centre hosts (docs/specs/public-pages.md, V1).
export default function Events() {
  return (
    <>
      <h1>Events</h1>
      <ul className="my-6 grid list-none grid-cols-1 gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
        <li>
          <Card className="h-full font-medium">Weddings</Card>
        </li>
        <li>
          <Card className="h-full font-medium">Parties</Card>
        </li>
        <li>
          <Card className="h-full font-medium">Cultural gatherings</Card>
        </li>
      </ul>
      <p>Planning something else? Send us a request and we will call you.</p>
    </>
  );
}
