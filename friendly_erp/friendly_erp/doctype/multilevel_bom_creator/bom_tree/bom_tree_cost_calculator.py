from typing import Dict
from frappe.utils import flt

from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTree,
    BOMTreeNode,
    BOMTreeItemNode,
    BOMTreeSubAssemblyNode,
    BOMTreeOperationNode,
    BOMTreeSubOperationNode
)

from erpnext.manufacturing.doctype.bom.bom import get_bom_item_rate
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item_node.multilevel_bom_creator_item_node import MultilevelBOMCreatorItemNode


class BOMTreeCostCalculator:
    """
    Calculates cost for BOMTree nodes using bottom-up traversal.

    fetch_fresh_rate_for_node_ids: set of node_unique_ids for which fresh rates
    should be fetched. If it contains '*', fresh rates will be fetched for all item nodes
    """

    def __init__(self, bom, bom_tree: BOMTree, item_map_to_update: Dict[str, MultilevelBOMCreatorItemNode], fetch_fresh_rate_for_node_ids: set):
        self.bom = bom
        self.bom_tree = bom_tree
        self.item_map_to_update = item_map_to_update
        self.fetch_fresh_rate_for_node_ids = fetch_fresh_rate_for_node_ids or set()

    def calculate(self):
        self._calculate_recursively(self.bom_tree.root)

    def _calculate_recursively(self, node: BOMTreeNode):
        for child in node.children:
            self._calculate_recursively(child)

        if node.node_type == "ITEM":
            self._calculate_item_node_cost(node)
        elif node.node_type == "SUB_ASSEMBLY":
            self._calculate_sub_assembly_node_cost(node)

        self.update_item_map(node)

    def _calculate_item_node_cost(self, node: BOMTreeItemNode):
        if node.node_unique_id in self.fetch_fresh_rate_for_node_ids or '*' in self.fetch_fresh_rate_for_node_ids:
            result = BOMTreeCostCalculationHelper.calculate_item_cost(
                bom=self.bom,
                item_code=node.item_code,
                bom_no=None,
                qty=node.component_qty_per_parent_bom_run,
                uom=node.uom,
                stock_uom=node.stock_uom,
                conversion_factor=node.conversion_factor,
                sourced_by_supplier=False
            )

            node.rate = result.get("rate", 0.0)
            node.amount = result.get("amount", 0.0)
            node.base_rate = result.get("base_rate", 0.0)
            node.base_amount = result.get("base_amount", 0.0)
        else:
            node.amount = flt(
                node.rate * node.component_qty_per_parent_bom_run)
            node.base_amount = flt(
                node.base_rate * node.component_qty_per_parent_bom_run)

        node.total_required_amount = flt(node.rate * node.total_required_qty)

    def _calculate_sub_assembly_node_cost(self, node: BOMTreeSubAssemblyNode):
        if node.is_preexisting_bom:
            pass  # TODO: Call calc helper for pre existing BOM
        else:
            total_amount = 0.0
            total_base_amount = 0.0
            for child in node.children:
                if child.node_type in ["ITEM", "SUB_ASSEMBLY"]:
                    total_amount += child.amount or 0.0
                    total_base_amount += child.base_amount or 0.0

            node.rate = (
                total_amount / node.component_qty_per_parent_bom_run) if node.component_qty_per_parent_bom_run else 0.0
            node.amount = total_amount
            node.base_rate = (
                total_base_amount / node.component_qty_per_parent_bom_run) if node.component_qty_per_parent_bom_run else 0.0
            node.base_amount = total_base_amount

        node.total_required_amount = flt(node.rate * node.total_required_qty)

    def update_item_map(self, node: BOMTreeNode):
        if self.item_map_to_update and node.node_type in ["ITEM", "SUB_ASSEMBLY"]:
            item_node = self.item_map_to_update.get(node.node_unique_id)
            if item_node:
                item_node.rate = node.rate
                item_node.amount = node.amount
                item_node.base_rate = node.base_rate
                item_node.base_amount = node.base_amount
                item_node.total_required_amount = node.total_required_amount


class BOMTreeCostCalculationHelper:
    @classmethod
    def calculate_item_cost(cls, bom, item_code: str, bom_no: str, qty: float, uom: str, stock_uom: str, conversion_factor: float, sourced_by_supplier: bool) -> dict:
        rate = get_bom_item_rate(
            {
                "company": bom.company,
                "item_code": item_code,
                "bom_no": bom_no,
                "qty": qty,
                "uom": uom,
                "stock_uom": stock_uom,
                "conversion_factor": conversion_factor,
                "sourced_by_supplier": sourced_by_supplier
            },
            bom,
        )

        amount = rate * qty

        return {
            "rate": flt(rate),
            "amount": flt(amount),
            "base_rate": flt(rate * bom.conversion_rate),
            "base_amount": flt(amount * bom.conversion_rate)
        }
