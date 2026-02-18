import frappe
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTreeNode, 
    BOMTreeItemNode, 
    BOMTreeOperationNode, 
    BOMTreeSubAssemblyNode,
    BOMTreeCostAwareNode
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
            is_stock_item=item.is_stock_item,
            component_qty_per_parent_bom_run=item.component_qty_per_parent_bom_run,
            total_required_qty=item.total_required_qty,
            uom=item.uom,
            stock_uom=item.stock_uom,
            conversion_factor=item.conversion_factor,
            component_stock_qty_per_parent_bom_run=item.component_stock_qty_per_parent_bom_run,
            do_not_explode=item.do_not_explode,
            rate=item.rate,
            amount=item.amount,
            base_rate=item.base_rate,
            base_amount=item.base_amount,
            total_required_amount=item.total_required_amount,
            allow_alternative_item=item.allow_alternative_item
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
            is_stock_item=item.is_stock_item,
            component_qty_per_parent_bom_run=item.component_qty_per_parent_bom_run,
            own_batch_size=item.own_batch_size,
            bom_run_count=item.bom_run_count,
            total_required_qty=item.total_required_qty,
            uom=item.uom,
            stock_uom=item.stock_uom,
            conversion_factor=item.conversion_factor,
            component_stock_qty_per_parent_bom_run=item.component_stock_qty_per_parent_bom_run,
            do_not_explode=item.do_not_explode,
            rate=item.rate,
            amount=item.amount,
            base_rate=item.base_rate,
            base_amount=item.base_amount,
            total_required_amount=item.total_required_amount,
            allow_alternative_item=item.allow_alternative_item
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
            total_required_time_in_mins=item.total_required_time_in_mins,
            fixed_time=item.fixed_time,
            workstation_type=item.workstation_type,
            workstation=item.workstation,
            hour_rate=item.hour_rate,
            base_hour_rate=item.base_hour_rate,
            batch_size=item.batch_size,
            set_cost_based_on_bom_qty=item.set_cost_based_on_bom_qty,
            rate=item.rate,
            amount=item.amount,
            base_rate=item.base_rate,
            base_amount=item.base_amount,
            total_required_amount=item.total_required_amount
        )


class ExistingBOMTreeNodeFactory:
    @staticmethod
    def create_from_bom(bom, sequence: int, tree_ref, bom_item=None) -> BOMTreeSubAssemblyNode:
        display_name = f"{sequence}: {bom.item} [{bom.name}]"
        qty_per_parent_bom_run = bom_item.qty if bom_item else bom.quantity
        stock_qty_per_parent_bom_run = bom_item.stock_qty if bom_item else bom.quantity
        return BOMTreeSubAssemblyNode(
            node_type="SUB_ASSEMBLY",
            tree_ref=tree_ref,
            node_unique_id=frappe.generate_hash(),  # Using a GUID longer than 10 characters to reduce the risk of ID collisions
            sequence=sequence,
            item_code=bom.item,
            is_stock_item=1,  # BOM items are alays stock items
            bom_no=bom.name,
            is_preexisting_bom=True,
            internal_name=bom.item,
            display_name=display_name,

            allow_alternative_item=bom.allow_alternative_item,

            uom=bom_item.uom if bom_item else bom.uom,
            stock_uom=bom_item.stock_uom if bom_item else bom.uom,
            conversion_factor=bom_item.conversion_factor if bom_item else 1.0,

            own_batch_size=bom.quantity,

            component_qty_per_parent_bom_run=qty_per_parent_bom_run,
            component_stock_qty_per_parent_bom_run=stock_qty_per_parent_bom_run,
            total_required_qty=None, # It should be calculated after tree construction

            # Calculate base rate for qty in Required UOM
            base_rate=bom.base_total_cost/(qty_per_parent_bom_run or 1.0),
            base_amount=None,   # It should be calculated after tree construction
            rate=None,          # It should be calculated after tree construction
            amount=None,        # It should be calculated after tree construction
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
            is_stock_item=bom_item.is_stock_item,
            allow_alternative_item=bom_item.allow_alternative_item,

            uom=bom_item.uom,
            stock_uom=bom_item.stock_uom,
            conversion_factor=bom_item.conversion_factor,

            component_qty_per_parent_bom_run=bom_item.qty,
            component_stock_qty_per_parent_bom_run=bom_item.stock_qty,
            total_required_qty=None, # It should be calculated after tree construction
            
            rate=bom_item.rate,
            amount=bom_item.amount,
            base_rate=bom_item.base_rate,
            base_amount=bom_item.base_amount
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
            hour_rate=bom_operation.hour_rate,
            batch_size=bom_operation.batch_size,
            set_cost_based_on_bom_qty=bom_operation.set_cost_based_on_bom_qty,
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

        BOMTreeNodeToCreatorItemConverter.assign_id_sequence_and_type(doc, node)
        doc.item_code = node.item_code
        doc.do_not_explode = node.do_not_explode
        doc.is_stock_item = node.is_stock_item
        doc.allow_alternative_item = node.allow_alternative_item

        doc.component_qty_per_parent_bom_run = node.component_qty_per_parent_bom_run
        doc.uom = node.uom
        doc.component_stock_qty_per_parent_bom_run = node.component_stock_qty_per_parent_bom_run
        doc.stock_uom = node.stock_uom
        doc.conversion_factor = node.conversion_factor
        doc.total_required_qty = node.total_required_qty

        BOMTreeNodeToCreatorItemConverter.assign_rate_and_amount(doc, node)
        
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
        doc.bom_run_count = node.bom_run_count
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

        doc: MultilevelBOMCreatorOperationNode = frappe.new_doc("Multilevel BOM Creator Operation Node")

        BOMTreeNodeToCreatorItemConverter.assign_id_sequence_and_type(doc, node)
        doc.operation = node.operation
        doc.time_in_mins = node.time_in_mins
        doc.fixed_time = node.fixed_time
        doc.total_required_time_in_mins = node.total_required_time_in_mins

        doc.workstation_type = node.workstation_type
        doc.workstation = node.workstation

        doc.hour_rate = node.hour_rate
        doc.base_hour_rate = node.base_hour_rate
        doc.batch_size = node.batch_size
        doc.set_cost_based_on_bom_qty = node.set_cost_based_on_bom_qty

        BOMTreeNodeToCreatorItemConverter.assign_rate_and_amount(doc, node)
        
        return doc
    
    @staticmethod
    def assign_id_sequence_and_type(doc: MultilevelBOMCreatorItemNode | MultilevelBOMCreatorOperationNode, node: BOMTreeNode) -> None:
        doc.node_type = node.node_type
        doc.node_unique_id = node.node_unique_id
        doc.parent_node_unique_id = node.parent_node_ref.node_unique_id
        doc.sequence = node.sequence

    @staticmethod
    def assign_rate_and_amount(doc: MultilevelBOMCreatorItemNode | MultilevelBOMCreatorOperationNode, node: BOMTreeCostAwareNode) -> None:
        doc.rate = node.rate
        doc.amount = node.amount
        doc.base_rate = node.base_rate
        doc.base_amount = node.base_amount
        doc.total_required_amount = node.total_required_amount
