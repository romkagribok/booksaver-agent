# Disclaimer

BookSaver Agent is an open-source, personal-use tool. It is **not affiliated with, endorsed by, or
sponsored by Booking.com** or Booking Holdings Inc. "Booking.com" is a trademark of its respective
owner, referenced here only to describe interoperability.

BookSaver automates browsing Booking.com (search, page navigation, and price reading) on your
behalf, using your own account/session or logged-out public pages. **Automated access to a
website may violate that website's Terms of Service.** Whether and how you run this tool — on
your laptop or on a VPS you operate — is entirely **your responsibility**. This project provides
no warranty, takes no responsibility for account restrictions, IP blocks, or other consequences
that may result from running it, and offers no guidance on how to avoid detection.

By design, BookSaver has **no public/multi-tenant bot mode**: Telegram access is restricted to an
`owner` and an explicit `invite` list (see `memory-bank/intents/003-telegram-interface/requirements.md`).
Anyone else who wants to use it self-hosts their own copy of this repository under their own
Booking.com session and their own acceptance of the above.
