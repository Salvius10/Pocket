# Validation report

Window: 2025-11-01 to 2026-11-19 (IST). Generated deterministically from fixed seeds.

## Demo personas

| Persona | Txns | Per month (min–max) | UPI share of debits | Median UPI debit | Negative balances | Dropped (insufficient funds) | Top-ups |
| --- | --- | --- | --- | --- | --- | --- | --- |
| student (Karthik) | 850 | 63–79 | 96% | ₹86 | 0 | 3 | 3 |
| first_job (Ananya) | 1260 | 88–110 | 77% | ₹264 | 0 | 0 | 0 |
| family (Lakshmi) | 995 | 69–90 | 74% | ₹427 | 0 | 0 | 3 |
| gig (Rahul) | 1653 | 122–139 | 91% | ₹150 | 0 | 4 | 8 |
| shop (Sunita) | 1242 | 91–107 | 71% | ₹530 | 0 | 0 | 0 |
| investor (Vikram) | 1379 | 101–120 | 45% | ₹662 | 0 | 5 | 5 |

## 200 evaluation users

- Transactions: 228,584; per user per full month: min 34, median 90, max 137
- Users with any negative savings/current balance: 0
- UPI share of debits (median user): 76%
- Share of UPI debits under ₹500: 75%
- Dropped spends for insufficient funds: 2,402; top-ups injected: 1,230

## Planted answer key

| Pattern | Planted (demo + eval) | Signal present in planted users | Accidental signals in non-planted users |
| --- | --- | --- | --- |
| forgotten_subscription | 88 | 88 | 0 |
| price_hike | 84 | 84 | 0 |
| category_creep | 98 | 98 | 0 |
| duplicate_charge | 80 | 80 | 0 |
| idle_cash | 79 | 79 | 0 |
| expensive_card_balance | 91 | 91 | 0 |

Food-delivery creep measured on planted users: median +36% (min +26%, max +56%).

## Bank SMS

- SMS: 237,565 (199,974 debit, 31,027 credit, 6,564 to ignore: OTPs, promos, statement notices)
- Held-out template variants (for parser evaluation): 30,175
- By bank: AXIS 53,509, ICICI 43,827, SBI 41,174, HDFC 35,235, BOB 25,532, CANARA 21,571, KOTAK 16,717

## Collab groups

- Groups: 36 (12 family, 12 flatmates, 12 trip)
- Expenses: 2,643; settlements: 476
- Every expense's shares sum exactly to its amount: yes
- Guest UPI IDs use the non-routable handle @pocketdemo

## Integrity checks

| Check | Result |
| --- | --- |
| Duplicate txn_id / sms_id / account_id | 0 / 0 / 0 |
| Running-balance breaks when rows are read in time order | 0 of 235,963 |
| Accounts whose last balance_after ≠ current_balance | 0 of 568 |
| SMS pointing at a missing transaction / txns pointing at a missing SMS | 0 / 0 |
| Broken transfer pairs (missing, one-sided, amount or direction mismatch) | 0 |
| Reversals not matching a reversed original / refunds larger than the original | 0 / 0 |
| Group expenses linked to a missing or different-amount transaction | 0 |
| Cards whose statement finance charges don't reconcile with posted charges | 0 of 170 |
| Transactions re-timed to keep an account's statement in time order | 0 |
