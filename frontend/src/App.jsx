import AdminPage from "./AdminPage.jsx";
import BookingForm from "./BookingForm.jsx";
import Privacy from "./Privacy.jsx";
import Terms from "./Terms.jsx";

function isAt(address) {
  const path = window.location.pathname;
  return path === address || path.startsWith(`${address}/`);
}

export default function App() {
  if (isAt("/terms")) {
    return <Terms />;
  }
  if (isAt("/privacy")) {
    return <Privacy />;
  }
  if (isAt("/admin")) {
    return (
      <main>
        <h1>Community Centre</h1>
        <h2>Bookings</h2>
        <AdminPage />
      </main>
    );
  }
  return (
    <main>
      <h1>Community Centre</h1>
      <h2>Booking request</h2>
      <BookingForm />
    </main>
  );
}
