# Copyright (c) 2025, iMORPHr Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTree,
    BOMTreeFactory
)
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.tree_to_bom import TreeToBOMConverter
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item.multilevel_bom_creator_item import MultilevelBOMCreatorItem

class MultilevelBOMCreator(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF
        from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item.multilevel_bom_creator_item import MultilevelBOMCreatorItem

        company: DF.Link
        description: DF.LongText | None
        item_code: DF.Link
        items: DF.Table[MultilevelBOMCreatorItem]
        qty: DF.Float
    # end: auto-generated types

    def validate(self) -> None:
        if not self.item_code:
            frappe.throw("Item Code is required.")
        if not self.company:
            frappe.throw("Company is required.")

    def before_save(self) -> None:
        if not self.items and self.item_code:
            self.add_root_item()

    def add_root_item(self) -> None:
        """Add the root item to the BOM creator document."""
        if self.items:
            frappe.throw("Root item already exists.")

        item = frappe.new_doc("Multilevel BOM Creator Item")
        item.node_unique_id = frappe.generate_hash()
        item.parent_node_unique_id = None
        item.node_type = "SUB_ASSEMBLY"
        item.item_code = self.item_code
        item.quantity = self.qty or 1.0
        item.uom = ""
        item.sequence = 0
        self.append("items", item)

    def add_item(self, parent_node_unique_id: str, item_code: str, quantity: float, uom: str) -> None:
        """Add a new item under the specified parent node."""
        #TODO: Cycle detection pending
        tree: BOMTree = BOMTreeFactory(self).create()
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
            item for item in self.items if item.node_unique_id == parent_node_unique_id
        ), None)

        # As child is being added, parent must be a Sub-Assembly
        if parent_item.node_type != "SUB_ASSEMBLY":
            parent_item.node_type = "SUB_ASSEMBLY"

        item: MultilevelBOMCreatorItem = frappe.new_doc("Multilevel BOM Creator Item")
        item.node_unique_id = frappe.generate_hash()
        item.parent_node_unique_id = parent_node_unique_id
        item.node_type = "ITEM"
        item.item_code = item_code
        item.quantity = quantity
        item.uom = uom
        item.sequence = self._get_child_sequence(parent_node_unique_id)
        self.append("items", item)

    def add_operation(self, parent_node_unique_id: str, operation_name: str, time_in_mins: float, workstation_type: str, workstation: str) -> None:
        """Add a new operation under the specified parent node."""
        tree: BOMTree = BOMTreeFactory(self).create()
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
            item for item in self.items if item.node_unique_id == parent_node_unique_id
        ), None)

        # As child is being added, parent must be a Sub-Assembly
        if parent_item.node_type != "SUB_ASSEMBLY":
            parent_item.node_type = "SUB_ASSEMBLY"

        operation: MultilevelBOMCreatorItem = frappe.new_doc("Multilevel BOM Creator Item")
        operation.node_unique_id = frappe.generate_hash()
        operation.parent_node_unique_id = parent_node_unique_id
        operation.node_type = "OPERATION"
        operation.operation = operation_name
        operation.time_in_mins = time_in_mins
        operation.workstation_type = workstation_type
        operation.workstation = workstation
        operation.sequence = self._get_child_sequence(parent_node_unique_id)
        self.append("items", operation)

    def create_boms(self) -> dict[str, str]:
        """
        Create ERPNext BOMs from the multilevel BOM tree and
        persist bom_no back to creator items.
        Returns: {node_unique_id: bom_no}
        """

        # 1. Build tree
        tree: BOMTree = BOMTreeFactory(self).create()

        # 2. Convert tree → BOMs
        converter = TreeToBOMConverter(tree, self.company)
        converter.convert()

        # 3. Persist bom_no back to child table
        node_id_to_bom = converter.newly_created_boms or {}

        for row in self.items:
            bom_no = node_id_to_bom.get(row.node_unique_id)
            if bom_no:
                row.bom_no = bom_no

        return node_id_to_bom


    def _get_child_sequence(self, parent_node_unique_id: str) -> int:
        """Get the next sequence number for a child item under the specified parent node."""
        child_items = [
            item for item in self.items if item.parent_node_unique_id == parent_node_unique_id
        ]
        if not child_items:
            return 0
        return max(item.sequence for item in child_items) + 1


@frappe.whitelist()
def get_tree_flat(multilevel_bom_creator_name: str) -> list[dict]:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    tree: BOMTree = BOMTreeFactory(multilevel_bom_creator).create()
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
def add_operation(multilevel_bom_creator_name: str, parent_node_unique_id: str, operation_name: str, time_in_mins: float, workstation_type: str = None, workstation: str = None) -> None:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator", multilevel_bom_creator_name)
    multilevel_bom_creator.add_operation(
        parent_node_unique_id, operation_name, time_in_mins, workstation_type, workstation)
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()

@frappe.whitelist()
def create_boms(multilevel_bom_creator_name: str) -> dict[str, str]:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator",
        multilevel_bom_creator_name
    )
    new_boms = multilevel_bom_creator.create_boms()
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification which causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()
