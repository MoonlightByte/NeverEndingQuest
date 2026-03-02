# Developer Homebrew Ingest Tools - Tasks

## 1. homebrew_preflight.py

- [ ] 1.1 Create script skeleton with argparse
- [ ] 1.2 Implement title hygiene detection
- [ ] 1.3 Implement metadata completeness check
- [ ] 1.4 Implement structure classification (room-based vs act/location)
- [ ] 1.5 Implement can_auto_transform logic
- [ ] 1.6 Add JSON output mode
- [ ] 1.7 Add unit tests
- [ ] 1.8 Verify with sample files

## 2. homebrew_transform_to_deterministic.py

- [ ] 2.1 Create script skeleton with argparse
- [ ] 2.2 Implement title prefix stripping
- [ ] 2.3 Implement metadata block injection
- [ ] 2.4 Implement ACT/LOCATION → room blocks conversion
- [ ] 2.5 Implement exit inference from descriptions
- [ ] 2.6 Handle encounter placeholders
- [ ] 2.7 Add unit tests
- [ ] 2.8 Verify with Mangrove Keep sample

## 3. homebrew_ingest_dev.py

- [ ] 3.1 Create orchestrator skeleton
- [ ] 3.2 Integrate preflight call
- [ ] 3.3 Integrate transform (conditional)
- [ ] 3.4 Integrate dry-run validation
- [ ] 3.5 Integrate registry guard check
- [ ] 3.6 Integrate strict ingest
- [ ] 3.7 Integrate sidecar audit
- [ ] 3.8 Integrate registry verification
- [ ] 3.9 Add comprehensive reporting
- [ ] 3.10 Add unit tests

## 4. homebrew_sidecar_audit.py

- [ ] 4.1 Create script skeleton with argparse
- [ ] 4.2 Implement sidecar discovery (latest for slug)
- [ ] 4.3 Implement status validation
- [ ] 4.4 Implement registration block verification
- [ ] 4.5 Add --require-success flag
- [ ] 4.6 Add unit tests

## 5. homebrew_registry_guard.py

- [ ] 5.1 Create script skeleton with argparse
- [ ] 5.2 Implement --check-duplicate
- [ ] 5.3 Implement --verify-present
- [ ] 5.4 Implement --remove (with backup)
- [ ] 5.5 Add unit tests

## 6. Integration & Verification

- [ ] 6.1 Run all tools against Mangrove Keep
- [ ] 6.2 Verify end-to-end pipeline
- [ ] 6.3 Update skill documentation
- [ ] 6.4 Create example session log
- [ ] 6.5 Validate OpenSpec change
