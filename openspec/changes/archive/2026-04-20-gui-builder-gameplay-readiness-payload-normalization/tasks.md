# Tasks: GUI Builder Gameplay Readiness Payload Normalization

## 1. Payload Normalization Contract
- [x] 1.1 Identify all readiness call sites that currently read gameplay payload fields from the wrong shape.
- [x] 1.2 Define the bounded normalization path for gameplay findings access.

## 2. Readiness / Publishability Implementation
- [x] 2.1 Normalize gameplay payload access in `scripts/audit_module_readiness.py`.
- [x] 2.2 Ensure structural media debt counts and slugs propagate correctly into toolkit media policy output.
- [x] 2.3 Preserve accurate publishability passthrough in `scripts/audit_module_publishability.py`.

## 3. Regression Coverage
- [x] 3.1 Add targeted tests for nested `target` gameplay findings consumption.
- [x] 3.2 Add targeted tests for correct `toolkit_media_policy.structural_media_debt_count` and slug propagation.
- [x] 3.3 Add targeted tests for publishability receiving corrected toolkit media policy metadata.

## 4. Verification
- [x] 4.1 Run `python3 -m py_compile scripts/audit_module_readiness.py scripts/audit_module_publishability.py`.
- [x] 4.2 Run targeted readiness/publishability tests.
- [x] 4.3 Capture a concrete before/after example showing the contradiction is eliminated.
