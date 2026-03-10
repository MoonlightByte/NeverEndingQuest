## Summary

- What changed?
- Why was it needed?
- What user or developer outcome does this improve?

## Scope

- [ ] Runtime/gameplay behavior
- [ ] Web UI
- [ ] Toolkit/ingest pipeline
- [ ] OpenSpec/spec/docs only
- [ ] Tests only

## Verification

List exact commands run and outcomes.

```bash
# Example
python3 -m py_compile <files>
python3 scripts/<relevant_test>.py
```

## OpenSpec and documentation

- Active change (if any): `openspec/changes/<change-id>/`
- Specs updated (if needed): `openspec/specs/<capability>/spec.md`
- Docs updated:
  - [ ] `README.md`
  - [ ] `AGENTS.md`
  - [ ] `CONTRIBUTING.md`
  - [ ] `DEV_SETUP.md`

## Merge safety and compatibility

- [ ] Required host-file hooks are marked with `# TABLETOP MODE:`
- [ ] Single-player compatibility preserved
- [ ] Multiplayer behavior verified for touched paths

## Risk and rollback

- Risks:
- Rollback approach:

## Checklist

- [ ] No secrets committed (`config.py`, credentials, env files)
- [ ] Tests or validation added/updated for changed behavior
- [ ] ASCII-safe Python user/log output where applicable
- [ ] Related stale OpenSpec changes archived when appropriate
