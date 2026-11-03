---
id: ADR-060
status: accepted
created: 2026-11-03T21:24:43Z
bolt: 097-jev-reservation-facts
amends: ADR-058
---

# ADR-060: Code proves reservation facts; Jev only chooses between proven answers

## Context

The code-owned confirmation reader accepts only exact layouts, so each new Booking.com layout leaves
a booked total or refund terms unknown and the reservation unmonitored. ADR-058 and ADR-059 trust
only code-read facts, because model output must not set money or refund facts.

## Decision

When the code reader leaves the total or refund terms unknown, code tries every candidate line or
sentence from the page with its own proof: arithmetic for the total, explicit wording and a parsed
date for refund terms. If the page proves exactly one answer, that is the fact. If it proves more
than one different refund term, Jev chooses among the proven sentences only; two proven totals stay
unknown. A proven fact is page-verified, the same as a code-read one. Only proven refund sentences
are sent to TypeSafe. Jev spend counts toward the existing daily cap.

## Consequences

- New layouts are covered without a new code shape, as long as the page proves its own answer.
- A model cannot introduce a value or a fact the page does not prove; it only breaks a tie.
- On the pages seen so far no tie occurred, so Jev was not called; it is there for pages that
  state two different refund terms.
- Reservation-page lines (amounts and refund sentences, no names) now reach TypeSafe; the owner
  approved this on 2026-11-03.

## Alternatives

- New code shapes per layout: always one layout behind.
- Model-read facts with a lower trust label: needs a second trust tier and alert caveats.
