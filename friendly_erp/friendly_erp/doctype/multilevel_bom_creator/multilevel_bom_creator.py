# Copyright (c) 2025, iMORPHr Ltd. and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _
from frappe.model.document import Document

from frappe.utils import cint
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTree,
    BOMTreeSubAssemblyNode
)
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_builders import BOMCreatorTreeBuilder
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_node_factories import BOMTreeNodeToCreatorItemConverter
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.tree_to_bom import TreeToBOMConverter
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item_node.multilevel_bom_creator_item_node import MultilevelBOMCreatorItemNode
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_operation_node.multilevel_bom_creator_operation_node import MultilevelBOMCreatorOperationNode

# TODO: Cycle detection pending in BOM Tree


class MultilevelBOMCreator(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF
        from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item_node.multilevel_bom_creator_item_node import MultilevelBOMCreatorItemNode
        from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_operation_node.multilevel_bom_creator_operation_node import MultilevelBOMCreatorOperationNode

        amended_from: DF.Link | None
        company: DF.Link
        description: DF.LongText | None
        item_code: DF.Link
        item_nodes: DF.Table[MultilevelBOMCreatorItemNode]
        operation_nodes: DF.Table[MultilevelBOMCreatorOperationNode]
        qty: DF.Float
    # end: auto-generated types

    def autoname(self):
        # ignore amended documents while calculating current index
        prefix = "MLBOMC"
        search_key = f"MLBOMC-{self.item_code}%"
        existing_creators = frappe.get_all(
            "Multilevel BOM Creator", filters={"name": search_key, "amended_from": ["is", "not set"]}, pluck="name"
        )

        index = self.get_index_for_bom(existing_creators)

        
        suffix = "%.3i" % index  # convert index to string (1 -> "001")
        creator_name = f"{prefix}-{self.item_code}-{suffix}"

        if len(creator_name) <= 140:
            name = creator_name
        else:
            # since max characters for name is 140, remove enough characters from the
            # item name to fit the prefix, suffix and the separators
            truncated_length = 140 - (len(prefix) + len(suffix) + 2)
            truncated_item_name = self.item_code[:truncated_length]
            # if a partial word is found after truncate, remove the extra characters
            truncated_item_name = truncated_item_name.rsplit(" ", 1)[0]
            name = f"{prefix}-{truncated_item_name}-{suffix}"

        if frappe.db.exists("Multilevel BOM Creator", name):
            existing_creators = frappe.get_all(
                "Multilevel BOM Creator", filters={"name": ("like", search_key), "amended_from": ["is", "not set"]}, pluck="name"
            )

            index = self.get_index_for_bom(existing_creators)
            suffix = "%.3i" % index
            name = f"{prefix}-{self.item_code}-{suffix}"

        self.name = name

    def get_index_for_bom(self, existing_creators):
        index = 1
        if existing_creators:
            index = self.get_next_version_index(existing_creators)

        return index

    @staticmethod
    def get_next_version_index(existing_creators: list[str]) -> int:
        # split by "/" and "-"
        delimiters = ["/", "-"]
        pattern = "|".join(map(re.escape, delimiters))
        creator_parts = [re.split(pattern, creator_name)
                       for creator_name in existing_creators]

        # filter out BOMs that do not follow the following formats: BOM/ITEM/001, BOM-ITEM-001
        valid_creator_parts = list(
            filter(lambda x: len(x) > 1 and x[-1], creator_parts))

        # extract the current index from the BOM parts
        if valid_creator_parts:
            # handle cancelled and submitted documents
            indexes = [cint(part[-1]) for part in valid_creator_parts]
            index = max(indexes) + 1
        else:
            index = 1

        return index

    def validate(self) -> None:
        if not self.item_code:
            frappe.throw("Item Code is required.")
        if not self.company:
            frappe.throw("Company is required.")

    def before_save(self) -> None:
        if not self.item_nodes and self.item_code:
            self.add_root_item()

    def before_submit(self) -> None:
        total_count = len(self.item_nodes or []) + len(self.operation_nodes or [])
        if total_count < 2:
            frappe.throw("No child items or operations found.")
        self.create_boms()

    def add_root_item(self) -> None:
        """Add the root item to the BOM creator document."""
        self.ensure_draft_status()
        if self.item_nodes:
            frappe.throw("Root item already exists.")

        item: MultilevelBOMCreatorItemNode = frappe.new_doc(
            "Multilevel BOM Creator Item Node")
        item.node_unique_id = frappe.generate_hash()
        item.parent_node_unique_id = None
        item.node_type = "SUB_ASSEMBLY"
        item.item_code = self.item_code
        item.quantity = self.qty or 1.0
        item.uom = ""
        item.sequence = 1
        self.append("item_nodes", item)

    # TODO: Cycle detection pending
    def add_item(self, parent_node_unique_id: str, item_code: str, quantity: float, uom: str) -> None:
        """Add a new item under the specified parent node."""
        # TODO: Cycle detection pending
        self.ensure_draft_status()
        tree: BOMTree = BOMCreatorTreeBuilder(self).create()
        parent_node = tree.find_node_by_unique_id(parent_node_unique_id)
        if not parent_node:
            frappe.throw(
                f"Parent node with ID {parent_node_unique_id} not found.")

        if not parent_node.can_add_child_item:
            frappe.throw(
                f"Cannot add item under node '{parent_node.display_name}'. "
                f"Adding child items is not allowed for this node."
            )

        parent_item = next((
            item for item in self.item_nodes if item.node_unique_id == parent_node_unique_id
        ), None)

        # As child is being added, parent must be a Sub-Assembly
        if parent_item.node_type != "SUB_ASSEMBLY":
            parent_item.node_type = "SUB_ASSEMBLY"
        # As child item is added make do_not_explode false for parent
        parent_item.do_not_explode = False

        has_bom = self._has_active_bom(item_code)

        item: MultilevelBOMCreatorItemNode = frappe.new_doc(
            "Multilevel BOM Creator Item Node")
        item.node_unique_id = frappe.generate_hash()
        item.parent_node_unique_id = parent_node_unique_id
        item.node_type = "ITEM"
        item.item_code = item_code
        item.do_not_explode = True if has_bom else False
        item.quantity = quantity
        item.uom = uom
        item.sequence = self._get_child_item_node_sequence(
            parent_node_unique_id)
        self.append("item_nodes", item)

    def add_existing_sub_assembly(self, parent_node_unique_id: str, bom_name: str, quantity: float, uom: str) -> None:
        """Add a new item under the specified parent node."""
        self.ensure_draft_status()
        tree: BOMTree = BOMCreatorTreeBuilder(self).create()
        parent_node = tree.find_node_by_unique_id(parent_node_unique_id)
        if not parent_node:
            frappe.throw(
                f"Parent node with ID {parent_node_unique_id} not found.")

        if not parent_node.can_add_child_item:
            frappe.throw(
                f"Cannot add sub-assembly under node '{parent_node.display_name}'. "
                f"Adding child sub-assembly is not allowed for this node."
            )

        parent_item = next((
            item for item in self.item_nodes if item.node_unique_id == parent_node_unique_id
        ), None)

        bom = frappe.get_doc("BOM", bom_name)
        if not bom:
            frappe.throw(f"Could not find bom {bom.name}")
        if bom.docstatus != 1:
            frappe.throw(_("Selected BOM must be submitted"))
        if not bom.is_active:
            frappe.throw(_("Selected BOM is not active"))
        if bom.company != self.company:
            frappe.throw(_("Selected BOM belongs to a different company"))

        # As child is being added, parent must be a Sub-Assembly
        if parent_item.node_type != "SUB_ASSEMBLY":
            parent_item.node_type = "SUB_ASSEMBLY"
        # As child item is added make do_not_explode false for parent
        parent_item.do_not_explode = False

        item: MultilevelBOMCreatorItemNode = frappe.new_doc(
            "Multilevel BOM Creator Item Node")
        item.node_unique_id = frappe.generate_hash()
        item.parent_node_unique_id = parent_node_unique_id
        item.node_type = "SUB_ASSEMBLY"
        item.item_code = bom.item
        item.bom_no = bom_name
        item.is_preexisting_bom = True
        item.do_not_explode = False
        item.quantity = quantity
        item.uom = uom
        item.sequence = self._get_child_item_node_sequence(
            parent_node_unique_id)
        self.append("item_nodes", item)

    def add_operation(self, parent_node_unique_id: str, operation_name: str, time_in_mins: float, workstation_type: str, workstation: str) -> None:
        """Add a new operation under the specified parent node."""
        self.ensure_draft_status()
        if not workstation and not workstation_type:
            frappe.throw(
                "Provide atleast one of Workstation Type and Workstation")
        tree: BOMTree = BOMCreatorTreeBuilder(self).create()
        parent_node = tree.find_node_by_unique_id(parent_node_unique_id)
        if not parent_node:
            frappe.throw(
                f"Parent node with ID {parent_node_unique_id} not found.")

        if not parent_node.can_add_child_operation:
            frappe.throw(
                f"Cannot add operation under node '{parent_node.display_name}'. "
                f"Adding child operations is not allowed for this node."
            )

        parent_item = next((
            item for item in self.item_nodes if item.node_unique_id == parent_node_unique_id
        ), None)

        # As child is being added, parent must be a Sub-Assembly
        if parent_item.node_type != "SUB_ASSEMBLY":
            parent_item.node_type = "SUB_ASSEMBLY"
        # As child item is added make do_not_explode false for parent
        parent_item.do_not_explode = False

        operation: MultilevelBOMCreatorOperationNode = frappe.new_doc(
            "Multilevel BOM Creator Operation Node")
        operation.node_unique_id = frappe.generate_hash()
        operation.parent_node_unique_id = parent_node_unique_id
        operation.node_type = "OPERATION"
        operation.operation = operation_name
        operation.time_in_mins = time_in_mins
        operation.workstation_type = workstation_type
        operation.workstation = workstation
        operation.sequence = self._get_child_operation_node_sequence(
            parent_node_unique_id)
        self.append("operation_nodes", operation)

    def duplicate_bom_structure(self, node_unique_id: str) -> None:
        self.ensure_draft_status()
        tree: BOMTree = BOMCreatorTreeBuilder(self).create()
        node: BOMTreeSubAssemblyNode = tree.find_node_by_unique_id(
            node_unique_id)
        if not node:
            frappe.throw(_("Invalid node. Node does not exist in BOM tree."))
        if node.node_type != "SUB_ASSEMBLY":
            frappe.throw(
                _("BOM structure can only be duplicated for Sub-Assembly nodes.")
            )
        if not node.parent_node_ref:
            frappe.throw(
                _("Root node can not be duplicated.")
            )
        if node.is_projected:
            frappe.throw(
                _("Projected nodes cannot be expanded or duplicated.")
            )
        if not node.is_preexisting_bom:
            frappe.throw(
                _("Only pre-existing BOMs can be duplicated.")
            )
        if not node.bom_no:
            frappe.throw(
                _("BOM is not present for the node")
            )

        # All existing children (if any) must be projected nodes
        for child in node.children or []:
            if not child.is_projected:
                frappe.throw(
                    _(
                        "BOM structure cannot be duplicated because this Sub-Assembly "
                        "already contains non-projected child nodes."
                    )
                )
            if child.node_type == "ITEM":
                item = BOMTreeNodeToCreatorItemConverter.convert_item_node(
                    child)
                self.append("item_nodes", item)
            elif child.node_type == "SUB_ASSEMBLY":
                sub_assembly = BOMTreeNodeToCreatorItemConverter.convert_sub_assembly_node(
                    child)
                self.append("item_nodes", sub_assembly)
            elif child.node_type == "OPERATION":
                operation = BOMTreeNodeToCreatorItemConverter.convert_operation_node(
                    child)
                self.append("operation_nodes", operation)

        # change parent item as now it has actual children
        parent_creator_item = next(
            (
                row for row in self.item_nodes
                if row.node_unique_id == node_unique_id
            ),
            None
        )

        if not parent_creator_item:
            frappe.throw(
                _("Internal error: Sub-Assembly item not found in creator document.")
            )

        parent_creator_item.bom_no = None
        parent_creator_item.is_preexisting_bom = False
        parent_creator_item.do_not_explode = False

    def delete_item_or_operation(self, node_unique_id: str) -> None:
        self.ensure_draft_status()
        if not node_unique_id:
            frappe.throw("Node unique id is required")

        tree: BOMTree = BOMCreatorTreeBuilder(self).create()
        node = tree.find_node_by_unique_id(node_unique_id)
        if not node:
            frappe.throw(f"Node '{node_unique_id}' not found")
        if not node.can_delete:
            frappe.throw(f"Node '{node.display_name}' cannot be deleted")
        node_ids_to_delete = tree.get_descendant_node_ids(node_unique_id)
        # Delete operation nodes
        self.operation_nodes = [
            row for row in (self.operation_nodes or [])
            if row.node_unique_id not in node_ids_to_delete
        ]
        # Delete item nodes
        self.item_nodes = [
            row for row in (self.item_nodes or [])
            if row.node_unique_id not in node_ids_to_delete
        ]

    def create_boms(self) -> dict[str, str]:
        """
        Create ERPNext BOMs from the multilevel BOM tree and
        persist bom_no back to creator items.
        Returns: {node_unique_id: bom_no}
        """

        # 1. Build tree
        tree: BOMTree = BOMCreatorTreeBuilder(self).create()

        # 2. Convert tree → BOMs
        converter = TreeToBOMConverter(tree, self.company)
        converter.convert()

        # 3. Persist bom_no back to child table
        node_id_to_bom = converter.newly_created_boms or {}

        for row in self.item_nodes:
            bom_no = node_id_to_bom.get(row.node_unique_id)
            if bom_no:
                row.bom_no = bom_no

        return node_id_to_bom

    def _get_child_item_node_sequence(self, parent_node_unique_id: str) -> int:
        """Get the next sequence number for a child item under the specified parent node."""
        child_item_nodes = [
            item_nd for item_nd in self.item_nodes if item_nd.parent_node_unique_id == parent_node_unique_id
        ]
        if not child_item_nodes:
            return 1
        return max(nd.sequence for nd in child_item_nodes) + 1

    def _get_child_operation_node_sequence(self, parent_node_unique_id: str) -> int:
        """Get the next sequence number for a child operation under the specified parent node."""
        child_operation_nodes = [
            op_nd for op_nd in self.operation_nodes if op_nd.parent_node_unique_id == parent_node_unique_id
        ]
        if not child_operation_nodes:
            return 1
        return max(nd.sequence for nd in child_operation_nodes) + 1

    def _has_active_bom(self, item_code: str) -> bool:
        return frappe.db.exists(
            "BOM",
            {
                "item": item_code,
                "company": self.company,
                "is_active": 1,
                "docstatus": 1
            }
        )

    def ensure_draft_status(self):
        if self.docstatus != 0:
            frappe.throw("Can not change submitted document.")


@frappe.whitelist()
def get_tree_flat(multilevel_bom_creator_name: str) -> list[dict]:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    tree: BOMTree = BOMCreatorTreeBuilder(multilevel_bom_creator).create()
    return tree.to_depth_first_flat_list()


@frappe.whitelist()
def add_item(multilevel_bom_creator_name: str, parent_node_unique_id: str, item_code: str, quantity: float, uom: str) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.add_item(
        parent_node_unique_id, item_code, quantity, uom)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification which causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


@frappe.whitelist()
def add_existing_sub_assembly(multilevel_bom_creator_name: str, parent_node_unique_id: str, bom_name: str, quantity: float, uom: str) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.add_existing_sub_assembly(
        parent_node_unique_id, bom_name, quantity, uom)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification which causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


@frappe.whitelist()
def add_operation(multilevel_bom_creator_name: str, parent_node_unique_id: str, operation_name: str, time_in_mins: float, workstation_type: str = None, workstation: str = None) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.add_operation(
        parent_node_unique_id, operation_name, time_in_mins, workstation_type, workstation)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


@frappe.whitelist()
def duplicate_bom_structure(
    multilevel_bom_creator_name: str,
    node_unique_id: str
) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.duplicate_bom_structure(node_unique_id)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


@frappe.whitelist()
def delete_item_or_operation(multilevel_bom_creator_name: str, node_unique_id: str) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.delete_item_or_operation(node_unique_id)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()


# @frappe.whitelist()
# def create_boms(multilevel_bom_creator_name: str) -> dict[str, str]:
#     multilevel_bom_creator = frappe.get_doc(
#         "Multilevel BOM Creator",
#         multilevel_bom_creator_name
#     )
#     new_boms = multilevel_bom_creator.create_boms()
#     # Do not send update notification through websocket, because frappe form auto refreshes on this notification which causes flicker on the tree UI
#     multilevel_bom_creator.flags.notify_update = False
#     multilevel_bom_creator.save()
