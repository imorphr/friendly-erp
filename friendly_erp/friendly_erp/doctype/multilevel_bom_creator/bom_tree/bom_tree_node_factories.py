import frappe
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTreeNode, 
    BOMTreeItemNode, 
    BOMTreeOperationNode, 
    BOMTreeSubAssemblyNode
)
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item_node.multilevel_bom_creator_item_node import MultilevelBOMCreatorItemNode
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_operation_node.multilevel_bom_creator_operation_node import MultilevelBOMCreatorOperationNode

class BOMCreatorTreeNodeFactory:
    @staticmethod
    def create_from_multilevel_bom_creator_item(item: MultilevelBOMCreatorItemNode, tree_ref) -> BOMTreeNode:
        node = None
        if item.node_type == "ITEM":
            node = BOMCreatorTreeNodeFactory._create_item_node(item)
        elif item.node_type == "SUB_ASSEMBLY":
            node = BOMCreatorTreeNodeFactory._create_sub_assembly_node(item)
        else:
            frappe.throw(f"Unknown node type: {item.node_type}")

        node.node_unique_id = item.node_unique_id
        node.sequence = item.sequence
        node.tree_ref = tree_ref
        return node
    
    @staticmethod
    def create_from_multilevel_bom_creator_operation(item: MultilevelBOMCreatorOperationNode, tree_ref) -> BOMTreeNode:
        node = None
        if item.node_type == "OPERATION":
            node = BOMCreatorTreeNodeFactory._create_operation_node(item)
        else:
            frappe.throw(f"Unknown node type: {item.node_type}")

        node.node_unique_id = item.node_unique_id
        node.sequence = item.sequence
        node.tree_ref = tree_ref
        return node

    @staticmethod
    def _create_item_node(item: MultilevelBOMCreatorItemNode) -> BOMTreeItemNode:
        return BOMTreeItemNode(
            node_type="ITEM",
            item_code=item.item_code,
            internal_name=item.item_code,
            display_name=item.item_code,    # TODO: should we use item_name here?
            quantity=item.quantity,
            uom=item.uom,
        )

    @staticmethod
    def _create_sub_assembly_node(item: MultilevelBOMCreatorItemNode) -> BOMTreeSubAssemblyNode:
        return BOMTreeSubAssemblyNode(
            node_type="SUB_ASSEMBLY",
            item_code=item.item_code,
            bom_no=item.bom_no,
            internal_name=item.item_code,
            display_name=item.item_code,
            quantity=item.quantity,
            uom=item.uom,
        )

    @staticmethod
    def _create_operation_node(item: MultilevelBOMCreatorOperationNode) -> BOMTreeOperationNode:
        ws = item.workstation or item.workstation_type
        workstation_display_text = f" [{ws}]" if ws else ""
        return BOMTreeOperationNode(
            node_type="OPERATION",
            operation=item.operation,
            internal_name=item.operation,
            display_name=f"{item.sequence}: {item.operation}{workstation_display_text}",
            time_in_mins=item.time_in_mins,
            workstation_type=item.workstation_type,
            workstation=item.workstation,
        )


class ExistingBOMTreeNodeFactory:
    @staticmethod
    def create_from_bom(bom, sequence: int, tree_ref) -> BOMTreeSubAssemblyNode:
        return BOMTreeSubAssemblyNode(
            node_type="SUB_ASSEMBLY",
            tree_ref=tree_ref,
            node_unique_id=frappe.generate_hash(),
            sequence=sequence,
            item_code=bom.item,
            bom_no=bom.name,
            internal_name=bom.item,
            display_name=bom.item,
            quantity=bom.quantity,
            uom=bom.uom,
        )

    @staticmethod
    def create_from_item(bom_item, sequence: int, tree_ref) -> BOMTreeItemNode:
        return BOMTreeItemNode(
            node_type="ITEM",
            tree_ref=tree_ref,
            node_unique_id=frappe.generate_hash(),
            sequence=sequence,
            item_code=bom_item.item_code,
            internal_name=bom_item.item_code,
            display_name=bom_item.item_code,
            quantity=bom_item.qty,
            uom=bom_item.uom,
        )

    @staticmethod
    def create_from_operation(bom_operation, sequence: int, tree_ref) -> BOMTreeOperationNode:
        ws = bom_operation.workstation or bom_operation.workstation_type
        workstation_display_text = f" [{ws}]" if ws else ""
        return BOMTreeOperationNode(
            node_type="OPERATION",
            tree_ref=tree_ref,
            node_unique_id=frappe.generate_hash(),
            sequence=sequence,
            operation=bom_operation.operation,
            internal_name=bom_operation.operation,
            display_name=f"{bom_operation.idx}: {bom_operation.operation}{workstation_display_text}",
            time_in_mins=bom_operation.time_in_mins,
            workstation_type=bom_operation.workstation_type,
            workstation=bom_operation.workstation,
        )