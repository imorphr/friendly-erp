import frappe

from frappe.utils import flt
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTree,
    BOMTreeNode,
    BOMTreeItemNode,
    BOMTreeSubAssemblyNode
)


class BOMTreeQtyCalculator:
    """
    Calculates quantity propagation for a multi-level BOM tree.

    Quantity semantics:
    - component_qty_per_parent_bom_run  : quantity needed per ONE execution of parent BOM
    - total_required_qty                : total quantity needed to satisfy ROOT BOM quantity
    - bom_run_count                     : number of times a sub-assembly BOM must be executed

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
        # Recursive Qty calculations only apply to ITEM and SUB_ASSEMBLY nodes
        if not isinstance(node, BOMTreeItemNode) and not isinstance(node, BOMTreeSubAssemblyNode):
            return

        parent_node: BOMTreeSubAssemblyNode = node.parent_node_ref
        if not isinstance(parent_node, BOMTreeSubAssemblyNode):
            frappe.throw(
                "Parent of ITEM/SUB_ASSEMBLY must be a Sub Assembly node")
        parent_bom_run_count = parent_node.bom_run_count

        node.total_required_qty = flt(
            parent_bom_run_count * node.component_qty_per_parent_bom_run, self.PRECISION)
        if isinstance(node, BOMTreeSubAssemblyNode):
            node.bom_run_count = node.total_required_qty / node.own_batch_size

        for child in (node.children or []):
            self._calculate_recursively(child)
