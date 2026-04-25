# toolkit-homebrew-uploader-console-ux Specification

## Purpose
Define the default Homebrew uploader user experience as a single live console flow with clear progress and clear terminal guidance, while keeping destructive confirmation safety and advanced recovery capability boundaries intact.

## Requirements

### Requirement: Default uploader surface SHALL use one primary live console

The toolkit Homebrew uploader SHALL present one primary live console/readout window for the default user flow instead of exposing multiple operator-style status/action surfaces.

#### Scenario: Upload shows one primary live console while work is active

- **WHEN** a user uploads Homebrew markdown and the ingest/build flow starts
- **THEN** the default uploader surface SHALL show one main rolling console/readout window
- **AND** that console SHALL display meaningful live progress updates for the running job
- **AND** the active flow SHALL include a visible working indicator while the job remains in progress

#### Scenario: Successful build ends with clear next-step guidance

- **WHEN** the upload/build flow completes successfully
- **THEN** the console SHALL end with a clear success message
- **AND** that message SHALL direct the user to the MMG tab for media generation

#### Scenario: Failed build ends with clear help guidance

- **WHEN** the upload/build flow ends in failure
- **THEN** the console SHALL end with a clear failure/help message
- **AND** that message SHALL direct the user to developer support including `https://github.com/zeug-zz/NeverEndingQuest-TTRPG/issues`

### Requirement: Default uploader surface SHALL hide operator recovery controls

The normal uploader surface SHALL not expose operator-style recovery or workspace-maintenance actions as primary-user controls.

#### Scenario: Normal user does not see retry and cleanup controls

- **WHEN** a normal user views the uploader during or after an upload/build job
- **THEN** `Retry from packet`, `Retry from finishing`, and `Cleanup workspace` SHALL not appear in the default uploader surface
- **AND** overwrite confirmation for destructive rebuild SHALL remain available when required

#### Scenario: Advanced recovery capability remains available outside default surface

- **WHEN** recovery artifacts and routes are available for a job
- **THEN** the system MAY expose those actions behind an advanced or developer-oriented surface
- **BUT** the default user flow SHALL remain centered on the single-console experience
