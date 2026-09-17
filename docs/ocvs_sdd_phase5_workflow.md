# OCVS SDD Phase 5 workflow

Phase 5 adds a controlled technical-review and customer-delivery lifecycle to the dedicated **Move to OCVS** scenario.

## Workflow

`Draft → In Review → Changes Requested → In Review → Approved → Finalized`

- **Draft:** the configuration remains editable and downloaded documents retain the `DRAFT — NOT FOR CUSTOMER DELIVERY` watermark.
- **In Review:** the submitted sizing and SDD content are frozen by a content hash. Reviewers can add categorized comments and complete their review.
- **Changes Requested:** comments and history are retained. Resubmission increments the draft revision (`0.1`, `0.2`, …).
- **Approved:** all mandatory reviews are complete, blocking comments are resolved, one configured approver has approved, and the source remains current. The first approved version is `1.0`; later approved versions increment the minor version.
- **Finalized:** the approved and current version is regenerated as customer-ready DOCX and PDF. The final outputs do not contain the Draft watermark.

## Safety and audit

- Any change to selected workload, sizing, pricing, topology, or relevant SDD configuration invalidates the review and returns it to **Changes Requested**.
- Portable assessments preserve assignments, comments, history, versions, and hashes, but never embed generated files or temporary paths.
- Audit logs contain event names, assessment identifiers, status, and output format only. Narratives, e-mails, network CIDRs, pricing values, file contents, and temporary paths are not logged.
- Final files are created in private temporary directories and regenerated on download. The protected master template is never modified.

## Finalization checks

Finalization is blocked unless Phase 4 remains ready and current, mandatory reviewers are complete, an approver has approved, blocking comments are resolved, required customer fields are present, and sample customer data has been removed.

## Routes

- `/step4/sdd/configure` — guided Phase 4 configuration.
- `/step4/sdd/review` — assignments, comments, review completion, approval, history, and finalization.
- `/step4/sdd/final/docx` — current finalized DOCX.
- `/step4/sdd/final/pdf` — current finalized PDF.

