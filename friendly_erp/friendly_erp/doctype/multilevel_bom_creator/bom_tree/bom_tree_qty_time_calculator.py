import math
import frappe

from frappe.utils import flt
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTree,
    BOMTreeNode,
    BOMTreeItemNode,
    BOMTreeSubAssemblyNode,
    BOMTreeOperationNode,
    BOMTreeSubOperationNode
)


class BOMTreeQtyTimeCalculator:
    """
    Calculates quantity and time propagation for a multi-level BOM tree.

    For items and operations, values are derived relative to the parent
    sub-assembly requirement.

    For sub-assemblies, required quantity may not align with the BOM
    batch size. In such cases, the BOM must be executed multiple times
    to satisfy the demand.

    The bom_run_count represents how many times a sub-assembly BOM
    needs to be executed in order to produce the required quantity,
    and is therefore essential for correctly deriving both downstream
    quantities and operation times.

    Quantity semantics:
    - component_qty_per_parent_bom_run  : quantity needed per ONE execution of parent BOM
    - total_required_qty                : total quantity needed to satisfy ROOT BOM quantity
    - bom_run_count                     : number of times a sub-assembly BOM must be executed

    Time semantics:
    - time_in_mins                      : time needed per ONE execution of parent BOM
    - total_required_time_in_mins       : total time needed to satisfy ROOT BOM quantity


    Root node:
    - total_required_qty = own_batch_size
    - bom_run_count = 1
    - component_qty_per_parent_bom_run = own_batch_size
    """

    def __init__(self, bom_tree: BOMTree):
        self.bom_tree = bom_tree
        self.root_node: BOMTreeSubAssemblyNode = bom_tree.root
        self.PRECISION = 6

    def calculate(self):
        """
        Entry point to calculate quantities for the entire tree.
        """
        self.root_node.component_qty_per_parent_bom_run = self.root_node.own_batch_size
        self.root_node.total_required_qty = self.root_node.own_batch_size
        self.root_node.bom_run_count = 1

        # Start recursion from children, not root
        for child in (self.root_node.children or []):
            self._calculate_recursively(child)

    def _calculate_recursively(self, node: BOMTreeNode):
        """
        Recursively calculates quantities for ITEM and SUB_ASSEMBLY nodes.

        Child quantity is always calculated relative to the number of times
        the parent BOM is executed.
        """
        if node.node_type == "ITEM":
            self._calculate_qty_for_item_node(node)
        elif node.node_type == "SUB_ASSEMBLY":
            self._calculate_qty_for_sub_assembly_node(node)
        elif node.node_type == "OPERATION":
            self._calculate_time_for_operation_node(node)
        elif node.node_type == "SUB_OPERATION":
            self._calculate_time_for_sub_operation_node(node)

        for child in (node.children or []):
            self._calculate_recursively(child)

    def _calculate_qty_for_item_node(self, node: BOMTreeItemNode):
        parent_node: BOMTreeSubAssemblyNode = node.parent_node_ref
        if not isinstance(parent_node, BOMTreeSubAssemblyNode):
            frappe.throw(
                "Parent of ITEM/SUB_ASSEMBLY must be a Sub Assembly node")
        parent_bom_run_count = parent_node.bom_run_count

        node.total_required_qty = flt(
            parent_bom_run_count * node.component_qty_per_parent_bom_run, self.PRECISION)

    def _calculate_qty_for_sub_assembly_node(self, node: BOMTreeSubAssemblyNode):
        self._calculate_qty_for_item_node(node)
        node.bom_run_count = node.total_required_qty / node.own_batch_size

    def _calculate_time_for_operation_node(self, node: BOMTreeOperationNode):
        if node.fixed_time:
            node.total_required_time_in_mins = node.time_in_mins
        else:
            parent_node: BOMTreeSubAssemblyNode = node.parent_node_ref
            if not isinstance(parent_node, BOMTreeSubAssemblyNode):
                frappe.throw(
                    "Parent of operation must be a Sub Assembly node")

            # Assuming that to calculate operation time, always need to consider full BOM runs.
            # Because even if a sub-assembly is needed partially, the operation needs to be done for the full batch.
            # Hence using math.ceil to round up.
            parent_bom_run_count = math.ceil(parent_node.bom_run_count)
            node.total_required_time_in_mins = flt(
                parent_bom_run_count * node.time_in_mins, self.PRECISION)

    def _calculate_time_for_sub_operation_node(self, node: BOMTreeSubOperationNode):
        is_fixed_time = False
        parent_operation_node = node.parent_node_ref
        while parent_operation_node is not None and (isinstance(parent_operation_node, BOMTreeOperationNode) or isinstance(parent_operation_node, BOMTreeSubOperationNode)):
            if parent_operation_node.fixed_time:
                is_fixed_time = True
                break
            parent_operation_node = parent_operation_node.parent_node_ref

        if is_fixed_time:
            node.total_required_time_in_mins = node.time_in_mins
        else:
            parent_sub_assembly_node = node.parent_node_ref
            while parent_sub_assembly_node is not None and not isinstance(parent_sub_assembly_node, BOMTreeSubAssemblyNode):
                parent_sub_assembly_node = parent_sub_assembly_node.parent_node_ref

            if parent_sub_assembly_node:
                parent_bom_run_count = math.ceil(
                    parent_sub_assembly_node.bom_run_count)
                node.total_required_time_in_mins = flt(
                    parent_bom_run_count * node.time_in_mins, self.PRECISION)
