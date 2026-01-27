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
            display_name=f"{item.sequence}: {item.item_code}",
            component_qty_per_parent_bom_run=item.component_qty_per_parent_bom_run,
            total_required_qty=None, # It should be calculated after tree construction
            uom=item.uom,
            do_not_explode=item.do_not_explode
        )

    @staticmethod
    def _create_sub_assembly_node(item: MultilevelBOMCreatorItemNode) -> BOMTreeSubAssemblyNode:
        display_name = f"{item.sequence}: {item.item_code} [{item.bom_no if item.bom_no else 'New BOM'}]"
        return BOMTreeSubAssemblyNode(
            node_type="SUB_ASSEMBLY",
            item_code=item.item_code,
            bom_no=item.bom_no,
            is_preexisting_bom=item.is_preexisting_bom,
            internal_name=item.item_code,
            display_name=display_name,
            component_qty_per_parent_bom_run=item.component_qty_per_parent_bom_run,
            own_batch_size=item.own_batch_size,
            total_required_qty=None, # It should be calculated after tree construction
            uom=item.uom,
            do_not_explode=item.do_not_explode
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
            fixed_time=item.fixed_time,
            workstation_type=item.workstation_type,
            workstation=item.workstation,
        )


class ExistingBOMTreeNodeFactory:
    @staticmethod
    def create_from_bom(bom, sequence: int, tree_ref) -> BOMTreeSubAssemblyNode:
        display_name = f"{sequence}: {bom.item} [{bom.name}]"
        return BOMTreeSubAssemblyNode(
            node_type="SUB_ASSEMBLY",
            tree_ref=tree_ref,
            node_unique_id=frappe.generate_hash(),  # Using a GUID longer than 10 characters to reduce the risk of ID collisions
            sequence=sequence,
            item_code=bom.item,
            bom_no=bom.name,
            is_preexisting_bom=True,
            internal_name=bom.item,
            display_name=display_name,
            component_qty_per_parent_bom_run=bom.quantity,
            own_batch_size=bom.quantity,
            total_required_qty=None, # It should be calculated after tree construction
            uom=bom.uom,
        )

    @staticmethod
    def create_from_item(bom_item, sequence: int, tree_ref) -> BOMTreeItemNode:
        display_name = f"{sequence}: {bom_item.item_code}"
        return BOMTreeItemNode(
            node_type="ITEM",
            tree_ref=tree_ref,
            node_unique_id=frappe.generate_hash(),  # Using a GUID longer than 10 characters to reduce the risk of ID collisions
            sequence=sequence,
            item_code=bom_item.item_code,
            internal_name=bom_item.item_code,
            display_name=display_name,
            component_qty_per_parent_bom_run=bom_item.qty,
            total_required_qty=None, # It should be calculated after tree construction
            uom=bom_item.uom,
        )

    @staticmethod
    def create_from_operation(bom_operation, sequence: int, tree_ref) -> BOMTreeOperationNode:
        ws = bom_operation.workstation or bom_operation.workstation_type
        workstation_display_text = f" [{ws}]" if ws else ""
        return BOMTreeOperationNode(
            node_type="OPERATION",
            tree_ref=tree_ref,
            node_unique_id=frappe.generate_hash(),  # Using a GUID longer than 10 characters to reduce the risk of ID collisions
            sequence=sequence,
            operation=bom_operation.operation,
            internal_name=bom_operation.operation,
            display_name=f"{bom_operation.idx}: {bom_operation.operation}{workstation_display_text}",
            time_in_mins=bom_operation.time_in_mins,
            fixed_time=bom_operation.fixed_time,
            workstation_type=bom_operation.workstation_type,
            workstation=bom_operation.workstation,
        )
    
class BOMTreeNodeToCreatorItemConverter:
    """
    Converts BOMTree nodes into Multilevel BOM Creator child documents.
    This class performs only structural mapping. It does NOT save documents.
    """
    
    # ---------------------------------------------------------------------
    # Item / Sub-Assembly
    # ---------------------------------------------------------------------

    @staticmethod
    def convert_item_node(
        node: BOMTreeItemNode
    ) -> MultilevelBOMCreatorItemNode:
        if node.node_type not in ("ITEM", "SUB_ASSEMBLY"):
            frappe.throw("Invalid node type for item conversion")

        doc: MultilevelBOMCreatorItemNode = frappe.new_doc("Multilevel BOM Creator Item Node")

        doc.node_type = node.node_type
        doc.node_unique_id = node.node_unique_id
        doc.parent_node_unique_id = node.parent_node_ref.node_unique_id
        doc.sequence = node.sequence
        doc.item_code = node.item_code
        doc.component_qty_per_parent_bom_run = node.component_qty_per_parent_bom_run
        doc.uom = node.uom
        doc.do_not_explode = node.do_not_explode
        return doc

    @staticmethod
    def convert_sub_assembly_node(
        node: BOMTreeSubAssemblyNode,
    ) -> MultilevelBOMCreatorItemNode:
        if node.node_type != "SUB_ASSEMBLY":
            frappe.throw("Invalid node type for sub-assembly conversion")

        doc = BOMTreeNodeToCreatorItemConverter.convert_item_node(node)
        doc.bom_no = node.bom_no
        doc.is_preexisting_bom = node.is_preexisting_bom
        doc.own_batch_size = node.own_batch_size
        return doc

    # ---------------------------------------------------------------------
    # Operation
    # ---------------------------------------------------------------------

    @staticmethod
    def convert_operation_node(
        node: BOMTreeOperationNode
    ) -> MultilevelBOMCreatorOperationNode:
        if node.node_type != "OPERATION":
            frappe.throw("Invalid node type for operation conversion")

        doc = frappe.new_doc("Multilevel BOM Creator Operation Node")

        doc.node_type = "OPERATION"
        doc.node_unique_id = node.node_unique_id
        doc.parent_node_unique_id = node.parent_node_ref.node_unique_id
        doc.sequence = node.sequence

        doc.operation = node.operation
        doc.time_in_mins = node.time_in_mins
        doc.fixed_time = node.fixed_time
        doc.workstation_type = node.workstation_type
        doc.workstation = node.workstation
        return doc
