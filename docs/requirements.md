**Functional Requirements:**

1. Landing page displaying general details and images of the centre.
2. List of all facilities provided by the centre, such as an A/V system, on-site parking, catering kitchen, main stage, and seating for up to 250 guests at a time.
3. Dedicated gallery page showing all images of the centre.
4. List of all events that can be hosted, such as weddings, parties, cultural gatherings, etc.
5. Booking request page with a form collecting basic client details such as name, phone number, email, date of booking, start and end times, number of expected guests, additional event details, and client agreement to terms and conditions before submission.
6. FAQ page containing common questions that clients often have.
7. A footer containing the address, location, opening times, and contact details of the centre.
8. An admin page for the management team to view all booking details, along with options to edit or cancel booking requests.
9. Admin page features for filtering, sorting, and searching booking requests.
10. Only 1 event can run at a time due to constraint of one hall only.
11. The booking form states would be submitted -> contacted -> accepted/declined. These can only be changed by the admin.

**Non-Functional Requirements:**

1. The admin page will be secured by an authentication system.
2. Sessions expire after 30 minutes of inactivity.
3. Booking form rate-limited using CAPTCHA.
4. Full compliance with UK GDPR.
5. Log files to monitor activity and performance only, not personal data.
6. Scalability to expand to multiple centres.