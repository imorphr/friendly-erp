from collections import OrderedDict, defaultdict
from typing import Dict, List

import frappe

from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTree,
    BOMTreeNode,
    BOMTreeItemNode,
    BOMTreeOperationNode,
    BOMTreeSubAssemblyNode
)

from erpnext.stock.get_item_details import get_conversion_factor
from friendly_erp.friendly_erp.util.progress_notifier import (
    NullProgressNotifier,
    ConcreteProgressNotifier
)


class TreeToBOMConverter:
    def __init__(self, bom_tree: BOMTree, bom_creator, notify_progress: bool = True):
        self.tree = bom_tree
        self.bom_creator = bom_creator
        # node_unique_id -> bom_no
        self.newly_created_boms: Dict[str, str] = {}
        self.progress_notifier = ConcreteProgressNotifier(
        ) if notify_progress else NullProgressNotifier()

    def convert(self) -> None:
        """
        Convert BOMTree into ERPNext BOMs using depth-based bottom-up traversal.
        """
        
        total_steps = len([
            node
            for node in self.tree.node_map.values()
            if self._is_bom_creation_pending(node)
        ])
        self.progress_notifier.init(total_steps, "Creating BOMs")

        completed = 0
        nodes_by_depth = self._group_nodes_by_depth()
        max_depth = max(nodes_by_depth.keys(), default=0)

        # Traverse from deepest level to root
        for depth in range(max_depth, -1, -1):
            for node in nodes_by_depth.get(depth, []):
                if self._is_bom_creation_pending(node):
                    completed += 1
                    self.progress_notifier.step(completed, f"Creating BOM for {node.item_code}")
                    self._validate_children_ready(node)
                    self._create_bom_for_node(node)

        self.progress_notifier.done()

    def _group_nodes_by_depth(self) -> Dict[int, List[BOMTreeNode]]:
        depth_map: Dict[int, List[BOMTreeNode]] = defaultdict(list)
        for node in self.tree.node_map.values():
            depth_map[node.depth].append(node)
        return depth_map

    # -------------------------
    # Decision logic
    # -------------------------

    def _is_bom_creation_pending(self, node: BOMTreeNode) -> bool:
        # If node type is other than Sub-Assembly, skip
        return node.node_type == "SUB_ASSEMBLY" and not getattr(node, "bom_no", None)

    def _validate_children_ready(self, node: BOMTreeSubAssemblyNode) -> None:
        """
        Structural validation: all child sub-assemblies must already have BOMs.
        """
        pending_children = [
            child.item_code
            for child in node.children
            if self._is_bom_creation_pending(child)
        ]

        if pending_children:
            raise frappe.ValidationError(
                "BOM tree depth inconsistency detected. "
                f"Sub-assembly BOMs missing for items: {pending_children}"
            )

    # -------------------------
    # BOM creation
    # -------------------------
    def _create_bom_for_node(self, node: BOMTreeSubAssemblyNode) -> None:
        """
        Creates ERPNext BOM and assigns bom_no back to the node.
        """
        if not node.children:
            frappe.throw(
                f"Cannot create BOM for '{node.item_code}': No child items or operations found.")

        bom = self._create_bom_doc(node)

        # Add child items and operations
        for child in node.children:
            if child.node_type in ("ITEM", "SUB_ASSEMBLY"):
                bom_item = self._create_bom_item(child)
                bom.append("items", bom_item)
            elif child.node_type == "OPERATION":
                bom.with_operations = True
                bom_operation = self._create_bom_operation(child)
                bom.append("operations", bom_operation)

        # Insert and submit
        bom.insert()
        bom.submit()

        node.bom_no = bom.name
        self.newly_created_boms[node.node_unique_id] = bom.name

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _create_bom_doc(self, node: BOMTreeSubAssemblyNode):
        bom = frappe.new_doc("BOM")
        bom.company = self.bom_creator.company
        bom.item = node.item_code
        bom.bom_type = "Production"  # TODO: As of now hardcoding
        bom.set_rate_of_sub_assembly_item_based_on_bom = 1 # For simplicity, always set rate of sub-assembly based on BOM
        bom.uom = node.stock_uom    # BOM uom is always stock_uom of the item
        bom.quantity = node.own_batch_size
        bom.rm_cost_as_per = self.bom_creator.rm_cost_as_per
        bom.project = None  # As of now no project linkage
        bom.currency = self.bom_creator.currency
        bom.conversion_rate = self.bom_creator.conversion_rate
        bom.buying_price_list = self.bom_creator.buying_price_list
        bom.plc_conversion_rate = self.bom_creator.plc_conversion_rate
        bom.price_list_currency = self.bom_creator.price_list_currency

        bom.allow_alternative_item = node.allow_alternative_item

        return bom

    def _create_bom_item(self, node: BOMTreeItemNode | BOMTreeSubAssemblyNode):
        bom_item = frappe.new_doc("BOM Item")
        bom_item.item_code = node.item_code
        bom_item.uom = node.uom
        bom_item.stock_uom = node.stock_uom
        bom_item.conversion_factor = node.conversion_factor
        bom_item.qty = node.component_qty_per_parent_bom_run
        bom_item.stock_qty = node.component_stock_qty_per_parent_bom_run
        # For only non stock item provide rate, otherwise BOM doctype logic will itself pull
        # proper cost. In Multilevel BOM Creator tree cost is calculated but that is only for
        # user's idea. While creating BOM do not assign those rate/cost values for stock items
        # as BOM doctype logic will calculate it. 
        if node.node_type == "ITEM" and not node.is_stock_item:
            bom_item.rate = node.rate
        bom_item.do_not_explode = node.do_not_explode
        bom_item.source_warehouse = None        # TODO: As of now warehouse not supported. In future it should be exposed in Multilevel BOM Creator UI
        bom_item.allow_alternative_item = node.allow_alternative_item
        bom_item.sourced_by_supplier = node.sourced_by_supplier

        if node.node_type == "SUB_ASSEMBLY" and isinstance(node, BOMTreeSubAssemblyNode):
            bom_item.bom_no = node.bom_no

        return bom_item

    def _create_bom_operation(self, node: BOMTreeOperationNode):
        operation = frappe.new_doc("BOM Operation")
        operation.operation = node.operation
        operation.time_in_mins = node.time_in_mins
        operation.fixed_time = node.fixed_time
        operation.sequence_id = node.sequence
        operation.workstation_type = node.workstation_type
        operation.workstation = node.workstation
        operation.hour_rate = node.hour_rate
        operation.batch_size = node.batch_size
        operation.set_cost_based_on_bom_qty = node.set_cost_based_on_bom_qty
        return operation
