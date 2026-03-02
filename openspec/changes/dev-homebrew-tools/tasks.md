# Developer Homebrew Ingest Tools - Tasks

## 1. homebrew_preflight.py

- [x] 1.1 Create script skeleton with argparse
- [x] 1.2 Implement title hygiene detection
- [x] 1.3 Implement metadata completeness check
- [x] 1.4 Implement structure classification (room-based vs act/location)
- [x] 1.5 Implement can_auto_transform logic
- [x] 1.6 Add JSON output mode
- [x] 1.7 Add unit tests
- [x] 1.8 Verify with sample files

## 2. homebrew_transform_to_deterministic.py

- [x] 2.1 Create script skeleton with argparse
- [x] 2.2 Implement title prefix stripping
- [x] 2.3 Implement metadata block injection
- [x] 2.4 Implement ACT/LOCATION → room blocks conversion
- [x] 2.5 Implement exit inference from descriptions
- [x] 2.6 Handle encounter placeholders
- [x] 2.7 Add unit tests
- [x] 2.8 Verify with Mangrove Keep sample

## 3. homebrew_ingest_dev.py

- [x] 3.1 Create orchestrator skeleton
- [x] 3.2 Integrate preflight call
- [x] 3.3 Integrate transform (conditional)
- [x] 3.4 Integrate dry-run validation
- [x] 3.5 Integrate registry guard check
- [x] 3.6 Integrate strict ingest
- [x] 3.7 Integrate sidecar audit
- [x] 3.8 Integrate registry verification
- [x] 3.9 Add comprehensive reporting
- [x] 3.10 Add unit tests

## 4. homebrew_sidecar_audit.py

- [x] 4.1 Create script skeleton with argparse
- [x] 4.2 Implement sidecar discovery (latest for slug)
- [x] 4.3 Implement status validation
- [x] 4.4 Implement registration block verification
- [x] 4.5 Add --require-success flag
- [x] 4.6 Add unit tests

## 5. homebrew_registry_guard.py

- [x] 5.1 Create script skeleton with argparse
- [x] 5.2 Implement --check-duplicate
- [x] 5.3 Implement --verify-present
- [x] 5.4 Implement --remove (with backup)
- [x] 5.5 Add unit tests

## 6. Integration & Verification

- [x] 6.1 Run all tools against Mangrove Keep
- [x] 6.2 Verify end-to-end pipeline
- [x] 6.3 Update skill documentation
- [x] 6.4 Create example session log
- [x] 6.5 Validate OpenSpec change
