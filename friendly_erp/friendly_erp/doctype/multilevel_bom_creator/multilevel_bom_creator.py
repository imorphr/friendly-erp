# Copyright (c) 2025, iMORPHr Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import BOMTree
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_builders import BOMCreatorTreeBuilder
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.tree_to_bom import TreeToBOMConverter
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item_node.multilevel_bom_creator_item_node import MultilevelBOMCreatorItemNode
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_operation_node.multilevel_bom_creator_operation_node import MultilevelBOMCreatorOperationNode

class MultilevelBOMCreator(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF
        from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item_node.multilevel_bom_creator_item_node import MultilevelBOMCreatorItemNode
        from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_operation_node.multilevel_bom_creator_operation_node import MultilevelBOMCreatorOperationNode

        company: DF.Link
        description: DF.LongText | None
        item_code: DF.Link
        item_nodes: DF.Table[MultilevelBOMCreatorItemNode]
        operation_nodes: DF.Table[MultilevelBOMCreatorOperationNode]
        qty: DF.Float
    # end: auto-generated types

    def validate(self) -> None:
        if not self.item_code:
            frappe.throw("Item Code is required.")
        if not self.company:
            frappe.throw("Company is required.")

    def before_save(self) -> None:
        if not self.item_nodes and self.item_code:
            self.add_root_item()

    def add_root_item(self) -> None:
        """Add the root item to the BOM creator document."""
        if self.item_nodes:
            frappe.throw("Root item already exists.")

        item: MultilevelBOMCreatorItemNode = frappe.new_doc("Multilevel BOM Creator Item Node")
        item.node_unique_id = frappe.generate_hash()
        item.parent_node_unique_id = None
        item.node_type = "SUB_ASSEMBLY"
        item.item_code = self.item_code
        item.quantity = self.qty or 1.0
        item.uom = ""
        item.sequence = 0
        self.append("item_nodes", item)

    #TODO: Cycle detection pending
    def add_item(self, parent_node_unique_id: str, item_code: str, quantity: float, uom: str) -> None:
        """Add a new item under the specified parent node."""
        #TODO: Cycle detection pending
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

        item: MultilevelBOMCreatorItemNode = frappe.new_doc("Multilevel BOM Creator Item Node")
        item.node_unique_id = frappe.generate_hash()
        item.parent_node_unique_id = parent_node_unique_id
        item.node_type = "ITEM"
        item.item_code = item_code
        item.quantity = quantity
        item.uom = uom
        item.sequence = self._get_child_item_node_sequence(parent_node_unique_id)
        self.append("item_nodes", item)

    # TODO: Add code for ispreexisting bom. And isprojected flag 
    def add_existing_sub_assembly(self, parent_node_unique_id: str, bom_name: str, quantity: float, uom: str) -> None:
        """Add a new item under the specified parent node."""
       
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

        # As child is being added, parent must be a Sub-Assembly
        if parent_item.node_type != "SUB_ASSEMBLY":
            parent_item.node_type = "SUB_ASSEMBLY"

        item: MultilevelBOMCreatorItemNode = frappe.new_doc("Multilevel BOM Creator Item Node")
        item.node_unique_id = frappe.generate_hash()
        item.parent_node_unique_id = parent_node_unique_id
        item.node_type = "SUB_ASSEMBLY"
        item.item_code = bom.item
        item.bom_no = bom_name 
        item.quantity = quantity
        item.uom = uom
        item.sequence = self._get_child_item_node_sequence(parent_node_unique_id)
        self.append("item_nodes", item)

    def add_operation(self, parent_node_unique_id: str, operation_name: str, time_in_mins: float, workstation_type: str, workstation: str) -> None:
        """Add a new operation under the specified parent node."""
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

        operation: MultilevelBOMCreatorOperationNode = frappe.new_doc("Multilevel BOM Creator Operation Node")
        operation.node_unique_id = frappe.generate_hash()
        operation.parent_node_unique_id = parent_node_unique_id
        operation.node_type = "OPERATION"
        operation.operation = operation_name
        operation.time_in_mins = time_in_mins
        operation.workstation_type = workstation_type
        operation.workstation = workstation
        operation.sequence = self._get_child_operation_node_sequence(parent_node_unique_id)
        self.append("operation_nodes", operation)

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
            return 0
        return max(nd.sequence for nd in child_item_nodes) + 1

    def _get_child_operation_node_sequence(self, parent_node_unique_id: str) -> int:
        """Get the next sequence number for a child operation under the specified parent node."""
        child_operation_nodes = [
            op_nd for op_nd in self.operation_nodes if op_nd.parent_node_unique_id == parent_node_unique_id
        ]
        if not child_operation_nodes:
            return 0
        return max(nd.sequence for nd in child_operation_nodes) + 1

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
def create_boms(multilevel_bom_creator_name: str) -> dict[str, str]:
    multilevel_bom_creator = frappe.get_doc(
        "Multilevel BOM Creator",
        multilevel_bom_creator_name
    )
    new_boms = multilevel_bom_creator.create_boms()
    # Do not send update notification through websocket, because frappe form auto refreshes on this notification which causes flicker on the tree UI
    multilevel_bom_creator.flags.notify_update = False
    multilevel_bom_creator.save()
