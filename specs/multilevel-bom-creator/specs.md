# Multilevel BOM Creator Functional Specs

## Primary Frappe/ERPNext Document Type Name
Multilevel BOM Creator

## Functional Summary
The user builds a root product BOM tree with:
- Item nodes (leaf components).
- Sub-assembly nodes:
  - New BOM to be created.
  - Existing BOM reference (with recursive child items and operations projected from existing BOM).
- Operation nodes (with recursive sub-operations projected from Operation master).

System continuously computes:
- Required quantities.
- Required operation time.
- Cost/rate/amount totals in document currency and company currency.

On submit, system creates missing BOMs from deepest sub-assembly to root and stores created BOM references back on nodes.

## Data and Naming Rules
- Root node is auto-added on first save if no item nodes exist.
- Exactly one root item node is required when building tree.
- Node IDs:
  - Creator-owned nodes use short hash (`length=10`).
  - Projected nodes use longer hash for collision reduction.
- Name format: `MLBOMC-<item_code>-NNN`, with truncation fallback for 140-char limit.

## Tree Action Rules
- Projected nodes are read-only and non-deletable.
- Nodes under an ancestor existing-BOM sub-assembly are protected from edit/delete.
- Existing BOM sub-assembly supports `Duplicate BOM` action if eligible.
- Duplicate BOM behavior:
  - Allowed only for pre-existing non-root sub-assembly.
  - Copies projected descendants into creator-owned nodes.
  - Switches parent sub-assembly from existing BOM reference to editable new BOM mode.

## Submission and BOM Creation
- Before submit, creator must have at least one child node beyond root.
- BOM conversion order: deepest pending sub-assembly to root.
- For each pending sub-assembly:
  - Create BOM doc with company/currency/rate settings from creator.
  - Append item and operation rows.
  - Insert and submit BOM.
- Created BOM numbers are persisted back to matching creator nodes.

## UI/UX Behavior
- UI philosophy:
  - UI contains minimum business logic.
  - UI acts as a thin interaction layer over backend APIs.
  - Any create/update/delete action from UI must trigger backend API call.
  - After every successful mutation API call, UI must reload BOM tree from backend.
- On new form open, modal prompts for initial fields and inserts doc.
- Tree is fetched as flattened depth-first list from server and shown in `frappe.DataTable` tree view.
- Row action menu is dynamic by node action flags.
- After add/edit, UI reloads and scrolls/highlights affected node.
- Mutations are blocked if document has unsaved changes.
- For websocket flicker prevention, server save uses `flags.notify_update = False` for mutation APIs.
