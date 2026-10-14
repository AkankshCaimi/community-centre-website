import AdminPage from "./AdminPage.jsx";
import Events from "./Events.jsx";
import Facilities from "./Facilities.jsx";
import Faq from "./Faq.jsx";
import Gallery from "./Gallery.jsx";
import Home from "./Home.jsx";
import Layout from "./Layout.jsx";
import Privacy from "./Privacy.jsx";
import Terms from "./Terms.jsx";

// The public pages: address, browser title, page (docs/specs/public-pages.md, Addresses).
const PAGES = [
  ["/facilities", "Facilities", Facilities],
  ["/gallery", "Gallery", Gallery],
  ["/events", "Events", Events],
  ["/faq", "Frequently asked questions", Faq],
  ["/terms", "Terms and conditions", Terms],
  ["/privacy", "Data and privacy notice", Privacy],
];

// An address matches when written exactly, or with one "/" at its end (R1).
function isAt(address) {
  const path = window.location.pathname;
  return path === address || path === `${address}/`;
}

export default function App() {
  if (isAt("/admin")) {
    return (
      <main>
        <h1>Community Centre</h1>
        <h2>Bookings</h2>
        <AdminPage />
      </main>
    );
  }
  // Any other address shows the home page (R1).
  const [address, title, Page] = PAGES.find(([address]) => isAt(address)) ?? [
    "/",
    "Community Centre",
    Home,
  ];
  return (
    <Layout title={title} current={address}>
      <Page />
    </Layout>
  );
}
