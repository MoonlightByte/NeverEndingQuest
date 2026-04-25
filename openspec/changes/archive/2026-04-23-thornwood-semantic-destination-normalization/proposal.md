# Why

`The_Thornwood_Watch` currently fails semantic publishability because the player-facing destination phrase `north tower` remains unresolved, even though the authored canonical destination `North Tower Overlook` already resolves to `RO06`. This is a real module semantic-authority data problem rather than a generic toolkit issue.

# What Changes

- Normalize Thornwood semantic authority so `north tower` resolves deterministically to `RO06`.
- Remove the resulting unresolved-destination diagnostic entry.
- Repair the low-risk `Merchant Lira` scene-authority gap by aligning visible location authority with the module’s authored `appears_in` placement.

# Capability Scope

- `modules/The_Thornwood_Watch/module_context.json`

# Non-Goals

- Broad regeneration of Thornwood module assets
- Changes to generic semantic authority runtime logic

# Impact

- Clears Thornwood’s current travel unresolved-destination blocker.
- Removes a known missing NPC authority warning that is inconsistent with existing authored module placement.

# Risks

- Over-normalizing a phrase that could be ambiguous in some other module context.

# Fallback

- Restrict the content fix to the exact authored phrase `north tower` with the already-resolved anchor `north tower overlook` -> `RO06`.
