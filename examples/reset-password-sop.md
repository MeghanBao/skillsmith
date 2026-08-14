# IT SOP: Locked-Out User Password Reset

When a user reports they are locked out of their corporate account, support
handles it as follows.

1. Confirm the request came in as a ticket in the helpdesk system. Never act on
   a request that arrives only by chat or phone — the ticket is the audit trail.
2. Verify the user's identity: match the requester's email against the ticket
   and confirm at least one secondary detail (employee ID or manager name).
3. Once verified, trigger the reset with the identity tool:
   `idm reset <user-email>`. This emails a one-time link valid for 30 minutes.
4. Tell the user to complete the reset within 30 minutes and to set a password
   that meets policy (14+ chars, not reused from the last 5).
5. Close the ticket with a note of who was verified and when.

Hard rules: never reset a password without a verified ticket; never send the
new password over chat; escalate to security if the same account is reset more
than twice in one week (possible account takeover).
