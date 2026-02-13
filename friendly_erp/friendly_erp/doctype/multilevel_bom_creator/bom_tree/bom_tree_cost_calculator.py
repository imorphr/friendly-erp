from typing import Dict

import frappe
from frappe.utils import flt

from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTree,
    BOMTreeNode,
    BOMTreeItemNode,
    BOMTreeSubAssemblyNode,
    BOMTreeOperationNode,
    BOMTreeSubOperationNode,
    BOMTreeCostAwareNode
)

from erpnext.manufacturing.doctype.bom.bom import get_bom_item_rate
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item_node.multilevel_bom_creator_item_node import MultilevelBOMCreatorItemNode
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_operation_node.multilevel_bom_creator_operation_node import MultilevelBOMCreatorOperationNode


class BOMTreeCostCalculator:
    """
    Calculates cost for BOMTree nodes using bottom-up traversal.

    fetch_fresh_rate_for_node_ids: set of node_unique_ids for which fresh rates
    should be fetched. If it contains '*', fresh rates will be fetched for all item nodes
    """

    def __init__(self, bom_creator, root_node: BOMTreeSubAssemblyNode, item_map_to_update: Dict[str, MultilevelBOMCreatorItemNode | MultilevelBOMCreatorOperationNode], fetch_fresh_rate_for_node_ids: set):
        self.bom_creator = bom_creator
        self.root_node = root_node
        self.item_map_to_update = item_map_to_update
        self.fetch_fresh_rate_for_node_ids = fetch_fresh_rate_for_node_ids or set()

    def calculate(self):
        self._calculate_recursively(self.root_node)

    def _calculate_recursively(self, node: BOMTreeNode):
        for child in node.children:
            self._calculate_recursively(child)

        if node.node_type == "ITEM":
            self._calculate_item_node_cost(node)
        elif node.node_type == "SUB_ASSEMBLY":
            self._calculate_sub_assembly_node_cost(node)
        elif node.node_type == "OPERATION":
            self._calculate_operation_node_cost(node)

        self.update_item_map(node)

    def should_fetch_fresh_rate_for_node(self, node: BOMTreeNode) -> bool:
        if node.is_projected:
            return False

        return (
            "*" in self.fetch_fresh_rate_for_node_ids
            or node.node_unique_id in self.fetch_fresh_rate_for_node_ids
        )

    def _calculate_item_node_cost(self, node: BOMTreeItemNode):
        fetch_fresh = self.should_fetch_fresh_rate_for_node(node)
        base_rate = node.base_rate
        # Fetch base_rate only if instructed by should_fetch_fresh_rate_for_node
        # otherwise use existing base_rate value
        if fetch_fresh:
            base_rate = BOMTreeCostCalculationHelper.get_item_base_rate_in_company_currency_according_to_required_uom(
                bom_creator=self.bom_creator,
                item_code=node.item_code,
                qty_in_required_uom=node.component_qty_per_parent_bom_run,
                required_uom=node.uom,
                stock_uom=node.stock_uom,
                conversion_factor=node.conversion_factor,
                sourced_by_supplier=False,
                is_stock_item=node.is_stock_item,
                existing_base_rate=node.base_rate
            )

        BOMTreeCostCalculationHelper.apply_base_rate_to_item_and_sub_assembly_node(
            node, base_rate, self.bom_creator.conversion_rate)

    def _calculate_sub_assembly_node_cost(self, node: BOMTreeSubAssemblyNode):
        fetch_fresh = self.should_fetch_fresh_rate_for_node(node)
        base_rate = node.base_rate
        if node.is_preexisting_bom:
            # Fetch base_rate only if instructed by should_fetch_fresh_rate_for_node
            # otherwise use existing base_rate value
            if fetch_fresh:
                base_rate = BOMTreeCostCalculationHelper.get_existing_bom_base_rate_in_company_currency_according_to_required_uom(
                    bom_no=node.bom_no,
                    conversion_factor=node.conversion_factor
                )
        else:
            base_rate = BOMTreeCostCalculationHelper.get_new_bom_base_rate_in_company_currency_according_to_required_uom(
                node)

        BOMTreeCostCalculationHelper.apply_base_rate_to_item_and_sub_assembly_node(
            node, base_rate, self.bom_creator.conversion_rate)

    def _calculate_operation_node_cost(self, node: BOMTreeOperationNode):
        fetch_fresh = self.should_fetch_fresh_rate_for_node(node)
        base_rate = BOMTreeCostCalculationHelper.get_operation_base_rate_in_company_currency_according_to_required_uom(
            node, fetch_fresh, self.bom_creator.conversion_rate)
        BOMTreeCostCalculationHelper.apply_base_rate_to_operation_node(
            node, base_rate, self.bom_creator.conversion_rate)

    def update_item_map(self, node: BOMTreeCostAwareNode):
        if self.item_map_to_update and node.node_type in ["ITEM", "SUB_ASSEMBLY", "OPERATION"]:
            item_node = self.item_map_to_update.get(node.node_unique_id)
            if item_node:
                if node.node_type == "OPERATION":
                    self._update_additional_operation_cost_fields(
                        item_node, node)

                item_node.rate = node.rate
                item_node.amount = node.amount
                item_node.base_rate = node.base_rate
                item_node.base_amount = node.base_amount
                item_node.total_required_amount = node.total_required_amount

    def _update_additional_operation_cost_fields(self, item_node: MultilevelBOMCreatorOperationNode, node: BOMTreeOperationNode):
        item_node.hour_rate = node.hour_rate
        item_node.base_hour_rate = node.base_hour_rate


class BOMTreeCostCalculationHelper:
    @classmethod
    def get_item_base_rate_in_company_currency_according_to_required_uom(cls, bom_creator, item_code: str, qty_in_required_uom: float, required_uom: str, stock_uom: str, conversion_factor: float, sourced_by_supplier: bool, is_stock_item: bool, existing_base_rate: float) -> float:
        # get_bom_item_rate is ERPNext method which gives rate in Company Currency according to "Required UOM".
        rate_in_company_currency_according_to_required_uom = get_bom_item_rate(
            {
                "company": bom_creator.company,
                "item_code": item_code,
                "bom_no": None,
                "qty": qty_in_required_uom,
                "uom": required_uom,
                "stock_uom": stock_uom,
                "conversion_factor": conversion_factor,
                "sourced_by_supplier": sourced_by_supplier
            },
            bom_creator,
        )

        if (bom_creator.rm_cost_as_per == "Price List"):
            # For Price List erpnext standard get_bom_item_rate method is not taking actual value of plc_conversion_rate
            # And taking it as 1. So in case of "Price List", need to multiply rate with plc_conversion_rate.
            rate_in_company_currency_according_to_required_uom = flt(
                rate_in_company_currency_according_to_required_uom) * flt(bom_creator.plc_conversion_rate or 1.0)

        # For non stock item use provided existing rate if standard get_bom_item_rate method does not return value
        if not is_stock_item and not rate_in_company_currency_according_to_required_uom and existing_base_rate:
            rate_in_company_currency_according_to_required_uom = existing_base_rate

        return rate_in_company_currency_according_to_required_uom or 0.0

    @classmethod
    def get_existing_bom_base_rate_in_company_currency_according_to_required_uom(cls, bom_no: str, conversion_factor: float) -> float:
        base_total_cost, bom_quantity = frappe.db.get_value(
            "BOM", bom_no, ["base_total_cost", "quantity"])
        bom_qty_in_required_uom = bom_quantity / (conversion_factor or 1.0)
        rate_in_company_currency_according_to_required_uom = flt(
            (base_total_cost / bom_qty_in_required_uom))
        return rate_in_company_currency_according_to_required_uom or 0.0

    @classmethod
    def get_new_bom_base_rate_in_company_currency_according_to_required_uom(cls, node: BOMTreeSubAssemblyNode) -> float:
        total_child_base_amount = 0.0
        for child in node.children:
            if child.node_type in ["ITEM", "SUB_ASSEMBLY", "OPERATION"]:
                total_child_base_amount += child.base_amount or 0.0

        batch_size_in_required_uom = node.own_batch_size / \
            (node.conversion_factor or 1.0)
        base_rate = total_child_base_amount / \
            (batch_size_in_required_uom or 1.0)
        return base_rate or 0.0

    @classmethod
    def get_operation_base_rate_in_company_currency_according_to_required_uom(cls, node: BOMTreeOperationNode, fetch_ws_hour_rate: bool, conversion_rate: float) -> float:
        hour_rate = flt(node.hour_rate)
        base_hour_rate = flt(node.hour_rate) * flt(conversion_rate or 1.0)

        if fetch_ws_hour_rate:
            # Priority: Workstation > Workstation Type
            if node.workstation:
                base_hour_rate = flt(
                    frappe.get_cached_value(
                        "Workstation", node.workstation, "hour_rate")
                )
            if not hour_rate and node.workstation_type:
                base_hour_rate = flt(
                    frappe.get_cached_value(
                        "Workstation Type", node.workstation_type, "hour_rate")
                )

            hour_rate = base_hour_rate / (conversion_rate or 1.0)

        # Keep node fields in sync with freshly fetched master data
        node.base_hour_rate = flt(base_hour_rate)
        node.hour_rate = flt(hour_rate)

        operating_cost = flt(base_hour_rate) * flt(node.time_in_mins) / 60.0
        parent_node: BOMTreeSubAssemblyNode = node.parent_node_ref
        # node.batch_size as well as parent_node.own_batch_size both are in stock uom
        batch_size_in_stock_uom = node.batch_size if node.set_cost_based_on_bom_qty else parent_node.own_batch_size
        operating_cost_company_currency_stock_uom = flt(operating_cost) / \
            (batch_size_in_stock_uom or 1.0)
        operating_cost_company_currency_required_uom = flt(operating_cost_company_currency_stock_uom) * \
            flt(parent_node.conversion_factor or 1.0)
        return operating_cost_company_currency_required_uom or 0.0

    @classmethod
    def apply_base_rate_to_item_and_sub_assembly_node(cls, node: BOMTreeItemNode, base_rate: float, conversion_rate: float) -> None:
        conversion_rate = conversion_rate or 1.0
        node.base_rate = base_rate
        node.base_amount = flt(
            base_rate * node.component_qty_per_parent_bom_run)
        node.rate = flt(node.base_rate / conversion_rate)
        node.amount = flt(node.base_amount / conversion_rate)
        node.total_required_amount = flt(node.rate * node.total_required_qty)

    @classmethod
    def apply_base_rate_to_operation_node(cls, node: BOMTreeItemNode, base_rate: float, conversion_rate: float) -> None:
        conversion_rate = conversion_rate or 1.0
        node.base_rate = base_rate
        parent_bom_node: BOMTreeSubAssemblyNode = node.parent_node_ref

        # Service/operation nodes do not carry their own quantity, so amount is derived
        # from the parent BOM batch size. Since base_rate is in required UOM while
        # parent batch size is in stock UOM, convert it using the parent conversion factor.
        parent_bom_qty_in_required_uom = parent_bom_node.own_batch_size / parent_bom_node.conversion_factor
        node.base_amount = flt(
            base_rate * parent_bom_qty_in_required_uom)
        node.rate = flt(node.base_rate / conversion_rate)
        node.amount = flt(node.base_amount / conversion_rate)
        node.total_required_amount = flt(node.rate * parent_bom_node.total_required_qty)
        
