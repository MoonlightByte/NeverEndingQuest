# homebrew_media_extract.py

## ADDED Requirements

### Requirement: Warn-only Media Extraction
The tool SHALL extract media references without blocking module ingest on failures.

#### Scenario: Reachable image URL
Given a markdown source containing `https://i.imgur.com/t50VrIo.jpg`
When media extraction runs
Then the tool SHALL attempt to download/copy the asset
And write it to module media storage
And record extraction success in JSON output

#### Scenario: Unreachable image URL
Given a markdown source containing an unreachable image URL
When media extraction runs
Then the tool SHALL record a warning
And continue processing remaining assets
And return success/degraded status without raising a hard ingest failure

### Requirement: Map and Title Classification
The tool SHALL classify extracted image references for future consumers.

#### Scenario: Title image classification
Given an early-page hero image near the document title
When extraction runs
Then the image SHALL be classified as `title_image`

#### Scenario: Map image classification
Given image references under map-oriented headings (for example "The Map" or "DM Maps")
When extraction runs
Then those images SHALL be classified as `map_image`

### Requirement: Deterministic Output Report
The tool SHALL return structured JSON result data.

#### Scenario: JSON mode
Given `--json` flag
When tool completes
Then JSON SHALL include:
- status (`success|degraded|failed`)
- detected_urls
- extracted_count
- warning_count
- warnings[]

## ADDED Interface

### CLI
```bash
python scripts/homebrew_media_extract.py \
  --source <path> \
  --module-slug <slug> \
  [--timeout-seconds 10] \
  [--json]
```
