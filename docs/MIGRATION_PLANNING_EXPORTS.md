# Migration planning export contract

The Results & Export page exposes the selected assessment scope as vendor-neutral CSV and JSON. These files are a planning foundation; they do not call any external migration product.

## Record fields

- `vm_name`, `source_vcenter`, `source_datacenter`, `source_cluster`
- `target_platform`, `target_cluster`, `target_shape`
- `suggested_wave`, `dependency_group`, `migration_priority`, `owner`
- `readiness_status`, `validation_status`, `cutover_status`, `rollback_status`
- `planned_start`, `planned_end`, `execution_tool`
- `notes`

The JSON schema identifier is `vmware-to-oci-migration-plan/v1`. Dates are intentionally blank until a migration planner assigns them. Operational statuses start in a safe pre-execution state.

## Adapter boundary

Future RackWare, Matilda, or other third-party adapters should translate this neutral record into the vendor-supported import schema. An adapter must validate required fields and credentials, present a preview, and obtain explicit user confirmation before creating or changing external resources. The application must not infer vendor-specific fields or execute a migration when a supported API or import schema is unavailable.

An adapter should implement the same four-step boundary: `validate` the neutral records, `transform` them to the documented vendor schema, `preview` the exact payload, then `export` or `submit` only after explicit approval. RackWare and Matilda remain documented adapter targets; no live connector or credential flow is enabled in this release.

## Suggested workflow

1. Export the selected scope.
2. Complete dependency groups, waves, owners, dates, and rollback plans.
3. Validate the file against the chosen vendor adapter.
4. Preview the vendor payload.
5. Export or submit only after explicit approval.
