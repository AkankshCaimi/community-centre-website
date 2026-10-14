**Functional Requirements:**

1. Landing page displaying general details and images of the centre.
2. List of all facilities provided by the centre, such as an A/V system, on-site parking, catering kitchen, main stage, and seating for up to 250 guests at a time.
3. Dedicated gallery page showing all images of the centre.
4. List of all events that can be hosted, such as weddings, parties, cultural gatherings, etc.
5. Booking request page with a form collecting basic client details such as name, phone number, email, date of booking, start and end times, number of expected guests, and additional event details. Before submission the client must tick two separate boxes: one agreeing to the terms and conditions, and one for the data and privacy notice. The privacy notice states that a client can have their data deleted by contacting the management team by phone or email.
6. FAQ page containing common questions that clients often have.
7. A footer containing the address, location, opening times, and contact details of the centre.
8. An admin page for the management team to view all booking details, along with options to edit or cancel booking requests.
9. Admin page features for filtering, sorting, and searching booking requests.
10. Only 1 event can run per calendar day due to constraint of one hall only. A booking request locks its whole calendar day from the moment it is submitted. An event that runs past midnight locks both days. The lock is released when the request is declined.
11. The booking request states are submitted, contacted, accepted and declined. These can only be changed by the admin, apart from the automatic decline in FR12. A request can move from submitted to contacted, accepted or declined; from contacted to accepted, declined or back to submitted; and from accepted to declined or back to contacted. Declined is final: a declined request can never change state. The admin is asked to confirm before a request is declined. Declined requests stay visible on the admin page for reference.
12. A request with no decision after 48 hours is declined automatically and its day is freed. The 48 hours run through all days, including weekends.
13. Events can be requested at most 6 months in advance. No past date or time can be selected. The end time must be after the start time, the minimum booking length is 1 hour, and the maximum booking length is 12 hours.
14. The centre is assumed to be open 24 hours.
15. A person can hold at most 2 slots at a time. A request counts towards this limit if its phone number or its email matches an earlier request.
16. The booking form enforces hard lower and upper bounds on the guest count, a maximum character length on every field, and validity and data-type checks on every field. The bound and length values are not yet decided.
17. The management team is notified by email when a new request is submitted. The client receives a confirmation email when the request is submitted and when it is accepted. The client is not told when a request is declined or automatically declined.
18. The admin can delete a client's data from the admin page. Deletion erases the personal details from the database; only the date and state of the request remain. The data of a request can be deleted once the request is declined or its event is over; to delete the data of an upcoming event, the admin declines the request first.

**Non-Functional Requirements:**

1. The admin page will be secured by an authentication system. For now there is one admin account, linked to an email address and used by one person. Password reset is by email. No action is taken after repeated wrong password attempts.
2. Sessions expire after 30 minutes of inactivity.
3. Booking form protected by CAPTCHA and limited to 5 requests per day per network address. People sharing a network address share that allowance. Over the limit, submitting shows an error that too many responses were submitted and to try again later.
4. Full compliance with UK GDPR.
5. Log files to monitor activity and performance only, not personal data.
6. Scalability to expand to multiple centres.
7. Booking request data is kept for 6 months from the day of submission and is then removed automatically. Notification emails held in the management team's mailbox are out of scope for this limit.
8. No backups are required for now.