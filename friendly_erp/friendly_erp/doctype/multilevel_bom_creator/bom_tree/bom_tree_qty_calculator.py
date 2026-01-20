from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTree,
    BOMTreeNode,
    BOMTreeItemNode
)


class BOMTreeQtyCalculator:
    """
    Calculates total_required_qty for all nodes in a multi-level BOM tree.

    Formula:
        node's total_required_qty = parent node's total_required_qty * node's qty_per_parent_unit
    """

    def __init__(self, bom_tree: BOMTree):
        self.bom_tree = bom_tree
        self.root_node: BOMTreeItemNode = bom_tree.root

    def calculate(self):
        """
        Entry point to calculate quantities for the entire tree.
        """
        self.root_node.total_required_qty = self.root_node.qty_per_parent_unit
        self._calculate_recursively(self.root_node)

    def _calculate_recursively(self, parent_node: BOMTreeNode):
        """
        Recursively calculates total_required_qty for child nodes.
        """
        for child in parent_node.children:
            if child.node_type == "ITEM" or child.node_type == "SUB_ASSEMBLY":
                child.total_required_qty = (
                    parent_node.total_required_qty * child.qty_per_parent_unit
                )

            self._calculate_recursively(child)
