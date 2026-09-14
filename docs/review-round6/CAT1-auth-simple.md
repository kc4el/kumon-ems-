# Category 1: Login, accounts & who-can-see-what (8 issues, plain words)

1. Resigning doesn't really log them out — if the delete fails, old password/token still works. Fix: block resigned accounts everywhere.
2. Resign looks up the account by email, not by link — renamed emails slip through. Fix: use the employee→user link.
3. Turned-off employees can still log in — nobody checks "is_active" at login. Fix: check it.
4. Login tokens last forever, and logout only kills one device. Fix: add expiry + kill-all on logout.
5. Anyone can create records for anyone else — just send another employee's ID. Fix: force "my own ID" for normal staff.
6. Some pages show anyone's data — balances, conflicts, clock-out, messages, payroll lists. Fix: add "mine or staff" check.
7. You can promote yourself — edit your own role/active/department by PATCH. Fix: staff-only fields.
8. Signup rules only apply to logged-out users — logged-in staff can grant roles; no-password signup makes orphan rows. Fix: same rules for everyone + require password.

Reply with numbers to fix (e.g. "fix 1, 5, 7").
