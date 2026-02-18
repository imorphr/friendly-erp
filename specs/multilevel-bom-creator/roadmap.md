# Multilevel BOM Creator Roadmap

## Scope
This file tracks planned enhancements not yet implemented in the current codebase.

## Audience
- Developers (primary).

## Planned Features

### 1. Scrap Material Support

#### Current Gap
`Multilevel BOM Creator` does not model scrap/by-product rows while authoring the tree, and `TreeToBOMConverter` does not populate BOM scrap item data.

#### Goal
Allow users to define scrap material as part of multilevel BOM authoring and persist it into generated ERPNext BOM documents.

### 2. Source Warehouse Support

#### Current Gap
Source warehouse is currently not supported in BOM creation flow (`tree_to_bom.py` assigns `source_warehouse = None`).

#### Goal
Allow users to select and persist source warehouse on BOM item rows generated from multilevel BOM creator nodes.

### 3. Support for BOM Item attributes which are not covered in first release

#### Current Gap
BOM Item attributes like project, item operation, include item in manufacturing, quality inspection and inspection template are not exposed through multilevel BOM creator.

#### Goal
Allow users to specify these attributes and they should be reflected on created BOM(s).
