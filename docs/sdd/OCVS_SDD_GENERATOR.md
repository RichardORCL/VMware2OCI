# OCVS SDD standalone generator

The Flask Move to OCVS workflow now consumes this generator through the adapter documented in `docs/sdd/OCVS_SDD_FLASK_INTEGRATION.md`. The standalone command-line workflow remains supported and unchanged.

## Purpose and phase boundary

`scripts/generate_ocvs_sdd.py` validates structured assessment data and creates an editable **Draft** OCVS Solution Definition Document from `document_templates/OCVS_SDD_template_automatable.docx`.

This Phase 2 component is deliberately independent from Flask. It does not add a route or button and does not recalculate sizing, pricing, PowerPoint, or Excel exports. Its future integration point is the saved final result of the `Move to OCVS` workflow.

## Command-line usage

```bash
python scripts/generate_ocvs_sdd.py \
  --template document_templates/OCVS_SDD_template_automatable.docx \
  --data tests/fixtures/ocvs_sdd_single_cluster.json \
  --output test_outputs/Customer_OCVS_SDD_Draft.docx
```

The command creates:

- the requested editable `.docx`;
- a sibling `<name>.validation.json` report.

The output path must differ from the template path. The template checksum is checked before and after generation, and generation never edits the master in place.

## JSON schema and validation

The machine-readable contract is `schemas/ocvs_sdd_generation.schema.json`. The generator also performs cross-field semantic validation that JSON Schema alone cannot safely express.

Top-level objects:

| Object | Purpose |
|---|---|
| `document` | Customer identity, project, assessment, author, version, dates, classification, Draft state |
| `business` | Context, drivers, requirements, scope, compliance, success criteria |
| `scope` | Selected/included VM totals and per-source-cluster rows |
| `sizing` | Frozen OCVS topology, capacity policy and overall sizing result |
| `target_clusters` | One to six final target OCVS clusters |
| `network` | OCI target, CIDRs, DNS/NTP, connectivity, HCX and network segments |
| `security` | IAM, encryption, logging, monitoring and requirements |
| `operations` | Operating model, backup, DR, HA, migration and implementation provider |
| `commercial` | Currency, price availability, discount, commitment, totals and BOM |
| `delivery` | History, people, assumptions, risks, RACI, obligations, scope and transition |
| `section_flags` | Explicit optional-module decisions |

Mandatory fields are the customer/document identity, core business narrative, selected-scope totals, final OCVS sizing/topology, target cluster rows, implementation provider, currency and pricing state. Optional missing values are rendered only as `Not provided`, `Not applicable`, or `Not available`; raw placeholders are rejected.

Semantic checks include:

- scenario must be `ocvs`;
- topology must be `single` or `multi`;
- one to six target clusters;
- single topology has one cluster;
- multi topology has exactly one unified management cluster;
- unified management minimum is three hosts;
- Dense workload minimum is three hosts;
- Standard/Optimized workload minimum is two hosts;
- GPU workload minimum is one host;
- `total_nodes = workload_nodes + spare_nodes` for every cluster;
- source-cluster totals reconcile with the selected-scope totals;
- available pricing has monthly and annual amounts;
- unavailable pricing contains no amounts;
- Oracle Lift requires an Oracle provider and explicit enablement.

Invalid data is rejected before the template is copied or populated. The generator never repairs an invalid topology silently.

## Content-control mapping

Controls are located exclusively by Word `w:tag`. Visible text, paragraph position, table number, and page number are never used as identifiers.

- scalar tags are populated from the nested JSON objects;
- structural values such as `cover_customer_name` and conditional-detail fields are populated from the same authoritative data;
- repeatable structures use their `<repeat>_item` seed content control;
- conditional structures use the `section_*` content-control tags prepared in Phase 1.

The detailed source-to-tag inventory remains in `docs/sdd/OCVS_SDD_FIELD_MAPPING.md`.

## Repeatable rows

Supported repeaters:

- document history, reviewers, approvers and project team;
- environments and source-cluster rows;
- target OCVS cluster rows and BOM rows;
- RACI, risks, assumptions and customer obligations;
- implementation scope, transition milestones and network segments.

For each input row, the generator deep-clones the Word repeating-section item and populates its child controls. This preserves the template's formatting and native editability. The seed item is removed first, so no sample row survives. If an optional list is empty, its repeatable wrapper is removed rather than leaving an unexplained empty sample row.

## Conditional sections

Included modules are unwrapped from their structural control while preserving their content. Excluded modules are removed from the document XML, not merely hidden with white text or hidden formatting.

The generator handles:

- single versus multi-cluster;
- vSAN/DenseIO versus Block Volume/Standard or Optimized;
- FastConnect and IPSec VPN;
- HCX, HA, DR, backup, security/compliance and pricing;
- customer, partner or Oracle implementation ownership;
- Oracle Lift, RACI, risks and transition.

Oracle Lift is always excluded unless `implementation_provider` is `oracle` and `include_oracle_lift` is explicitly true. Included and excluded module names are recorded in the validation report. No `section_*` markers remain in the generated document.

## Formatting and customer safety

- storage is rendered in TB with no trailing `.0`;
- RAM is rendered in GB;
- percentages include one `%`;
- numbers use readable separators;
- money uses the supplied ISO currency code;
- dates use a consistent customer-facing form;
- unavailable commercial data displays `Not available` and is never fabricated;
- all outputs retain `DRAFT — NOT FOR CUSTOMER DELIVERY`;
- the default version is `0.1`;
- known sample values and raw placeholders are rejected;
- Word's TOC update setting is enabled in `word/settings.xml`.

The generator preserves the DOCX package's styles, headers, footers, diagrams, bookmarks, numbering, hyperlinks, and media. Content controls remain present and editable after population.

## Validation report

Every successful run writes a JSON report containing:

- generation status;
- template, input-data and generated-document SHA-256 checksums;
- populated control tags;
- missing mandatory and omitted optional fields;
- enabled and excluded conditional sections;
- repeated-row counts;
- warnings requiring specialist review.

The report is an audit aid, not a customer approval. All Phase 2 output remains Draft.

## Tests and QA fixtures

- `tests/fixtures/ocvs_sdd_single_cluster.json` covers a fictional single Optimized/Block Volume design, unavailable pricing and customer-managed implementation.
- `tests/fixtures/ocvs_sdd_multi_cluster.json` covers a fictional unified management cluster, two workload clusters, multiple source clusters, FastConnect, HCX, partner delivery and explicitly fictional QA prices.
- `tests/test_ocvs_sdd_generation.py` checks package validity, template immutability, mandatory data, scalar and repeat population, section selection, provider selection, Draft safety, editability, checksums and invalid host minima.

Run:

```bash
python -m unittest tests.test_ocvs_sdd_generation -v
```

Both QA documents must also be rendered with `render_docx.py` and every page inspected before delivery.

## Known limitations and specialist validation

- Word fields are configured to update when opened; cross-platform renderers may not refresh the TOC exactly as desktop Word does.
- The generator does not calculate sizing or pricing. It trusts only validated, frozen input values.
- Narrative line wrapping depends on the lengths of customer-provided text; exceptionally long inputs require visual review.
- The generator does not certify CIDR overlap, HCX feasibility, security architecture, pricing authority, migration waves, RPO/RTO, or customer obligations.
- BOM part numbers must remain `Not available` unless supplied by an authoritative source.
- Network, security, operations, delivery assumptions, risks and customer-facing narratives require specialist approval.

## Future Flask integration

The future `Move to OCVS` export workflow should build this JSON payload from a frozen final-sizing snapshot and persisted SDD configuration. It must not recalculate during generation. If selected scope, topology, cluster assignments, capacity policy, pricing, or the source snapshot changes, prior validation and specialist approvals must be invalidated before the user can generate another customer-ready document.
