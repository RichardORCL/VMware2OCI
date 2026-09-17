# OCVS SDD Phase 6 — Customer Delivery and Document Governance

Phase 6 extends the Move to OCVS SDD workflow from technical approval into a controlled customer-delivery lifecycle.

## Lifecycle

`Draft → In Review → Changes Requested → Approved → Finalized → Delivered → Superseded`

- **Finalized**: the approved DOCX and PDF are generated once and stored as immutable artifacts.
- **Delivered**: a user confirms who delivered the document, when it was delivered, and optional recipient metadata.
- **Superseded**: an older delivered version is explicitly replaced by a newer delivered version. Its files and history remain available.

Changing the workload, sizing, pricing, topology, or SDD configuration after finalization does not change an existing artifact. The UI reports unpublished changes and requires a new governed revision.

## Artifact storage

- Artifact metadata is stored in the assessment JSON under `sdd_configuration.delivery_governance`.
- Binary artifacts are stored separately under `downloads/app_state/sdd_artifacts/<opaque-artifact-id>/`.
- The JSON contains filenames, sizes, SHA-256 checksums, version metadata, and audit events. It never contains absolute host paths.
- Each artifact directory is private and created with an opaque identifier.
- Existing version files are never overwritten.
- Every download and customer package verifies file type and SHA-256 integrity first.

If an assessment is opened on another host without its binary artifact store, the version history remains visible and explicitly reports the files as unavailable. The application does not silently regenerate a supposedly immutable final version.

## Delivery package

The ZIP package contains exactly:

1. Final DOCX
2. Final PDF
3. `delivery-manifest.json`
4. `delivery-manifest.md`

The manifest identifies the customer, project, assessment, SDD version, approval/finalization/delivery metadata, document checksums, source sizing timestamp, selected workload summary, OCVS topology, target cluster count, node count, and commitment term.

## Revision model

Starting a revision from delivered `v1.0` creates draft `v1.1` and records `based_on_version = 1.0`. Reviewers and approvers return to pending, review comments are cleared for the new cycle, and the revision reason is required. The previous artifact record and files are unchanged. When the new version is finalized, its record links back to the version it replaces.

## UI entry points

- **Technical Review**: submit, comment, request changes, approve, and finalize.
- **Customer Delivery**: download historical DOCX/PDF artifacts, build the ZIP package, mark a finalized version as delivered, start a revision, supersede an older delivered version, and inspect the audit trail.
- **Results & Export**: shows working/finalized/delivered version summaries, artifact integrity, unpublished changes, and direct governed downloads.

## Validation coverage

Automated tests cover backward-compatible normalization, immutable storage, duplicate prevention, safe filenames, checksum validation, tamper detection, path traversal protection, ZIP contents, manifest traceability, delivery confirmation, invalid metadata, unavailable artifacts, revision creation, review reset, replacement links, superseding, portability, and append-only audit events.
