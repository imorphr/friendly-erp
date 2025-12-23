# Copyright (c) 2025, iMORPHr Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTree, 
    BOMTreeFactory
)
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_node import BOMTreeSubAssemblyNode


class MultilevelBOMCreator(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF
        from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item.multilevel_bom_creator_item import MultilevelBOMCreatorItem

        company: DF.Link
        item_code: DF.Link
        items: DF.Table[MultilevelBOMCreatorItem]
    # end: auto-generated types

    def before_save(self) -> None:
        if not self.items and self.item_code:
            node = BOMTreeSubAssemblyNode(
                node_guid=frappe.generate_hash(),
                parent_node_guid=None,
                node_type="SUB_ASSEMBLY",
                name=self.item_code,
                display_name=self.item_code,
                sequence=0,
                item_code=self.item_code,
                quantity=1,
                uom="",
            )
            self.add_root_item(node)
    
    def add_root_item(self, item: BOMTreeSubAssemblyNode) -> None:
        """Add the root item to the BOM creator document."""
        if self.items:
            frappe.throw("Root item already exists.")
        if self.item_code != item.item_code:
            frappe.throw("Root item code does not match the BOM creator's item code.")
        if item.node_type != "SUB_ASSEMBLY":
            frappe.throw("Root item must be a Sub-Assembly.")
        if item.parent_node_guid is not None:
            frappe.throw("Root item cannot have a parent node.")
        self.append("items", {
            "node_guid": item.node_guid,
            "parent_node_guid": item.parent_node_guid,
            "node_type": item.node_type,
            "item_code": item.item_code,
            "quantity": item.quantity,
            "uom": item.uom,
        })        
        # self.save()

@frappe.whitelist()
def get_tree_flat(multilevel_bom_creator_name: str) -> list[dict]:
    multilevel_bom_creator = frappe.get_doc("Multilevel BOM Creator", multilevel_bom_creator_name)
    tree: BOMTree = BOMTreeFactory(multilevel_bom_creator).create()
    return tree.to_depth_first_flat_list()


# @frappe.whitelist()
# def add_root_item(bom_creator_name: str, item: dict) -> None:
#     """Whitelisted function to add root item to BOM creator."""
#     bom_creator = frappe.get_doc("Multilevel BOM Creator", bom_creator_name)
#     item_node = BOMTreeSubAssemblyNode(**item)
#     bom_creator.add_root_item(item_node)

