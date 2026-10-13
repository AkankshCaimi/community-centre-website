import AdminPage from "./AdminPage.jsx";
import BookingForm from "./BookingForm.jsx";

function isAdminAddress() {
  const path = window.location.pathname;
  return path === "/admin" || path.startsWith("/admin/");
}

export default function App() {
  if (isAdminAddress()) {
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
