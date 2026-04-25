## 1. Destination normalization

- [x] 1.1 Update Thornwood semantic authority so `north tower` resolves to `RO06`.
- [x] 1.2 Remove the corresponding unresolved-destination diagnostic entry and update summary counts.

## 2. NPC authority cleanup

- [x] 2.1 Update `Merchant Lira` scene authority to reflect her authored visible location at `TW06`.
- [x] 2.2 Remove the corresponding missing-NPC-authority diagnostic entry and update summary counts.

## 3. Verification

- [x] 3.1 Run targeted Thornwood semantic authority and publishability audits.
- [x] 3.2 Confirm the sidebar-facing failure now reflects the remaining live blocker state only.

## Guidance

Keep the fix narrowly scoped to Thornwood’s current semantic payload. Do not broaden generic normalization rules here.
