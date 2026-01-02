from collections import OrderedDict
from typing import Dict

import frappe

from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTree,
    BOMTreeNode,
    BOMTreeSubAssemblyNode
)

class TreeToBOMConverter:
    def __init__(self, bom_tree: BOMTree, company: str):
        self.tree = bom_tree
        self.company = company
        self.processing_set: OrderedDict[str, BOMTreeNode] = OrderedDict()
        self.newly_created_boms: Dict[str, str] = {}  # node_unique_id -> bom_no

    def convert(self) -> None:
        # Step 1: Seed with leaf nodes
        for node in self.tree.leaf_nodes:
            self._enqueue_to_processing_set(node)

        # Step 2: Process until all eligible nodes are handled
        while self.processing_set:
            made_progress = False
            pass_size = len(self.processing_set)

            for _ in range(pass_size):
                node = self._dequeue_from_processing_set()
                if not self._is_bom_creation_pending(node):
                    self._enqueue_to_processing_set(node.parent_node_ref)
                    made_progress = True
                elif self._can_create_bom(node):
                    self._create_bom_for_node(node)
                    self._enqueue_to_processing_set(node.parent_node_ref)
                    made_progress = True
                else:
                    # Children not ready yet → requeue
                    self._enqueue_to_processing_set(node)

            # 🚨 Infinite loop detection. If any one pass happens without progress
            # then there is an infinite loop.
            if not made_progress and self.processing_set:
                stuck_nodes = [
                    n.name for n in self.processing_set.values()
                    if self._is_bom_creation_pending(n)
                ]
                raise frappe.ValidationError(
                    "Infinite BOM dependency detected. "
                    f"Unable to resolve BOMs for items: {stuck_nodes}"
                )

    # -------------------------
    # Queue / Set helpers
    # -------------------------

    def _enqueue_to_processing_set(self, node: BOMTreeNode | None):
        if not node:
            return
        self.processing_set[node.node_unique_id] = node

    def _dequeue_from_processing_set(self) -> BOMTreeNode:
        _, node = self.processing_set.popitem(last=False)
        return node

    # -------------------------
    # Decision logic
    # -------------------------

    def _is_bom_creation_pending(self, node: BOMTreeNode) -> bool:
        # If node type is other than Sub-Assembly, skip
        return node.node_type == "SUB_ASSEMBLY" and not getattr(node, "bom_no", None)

    def _can_create_bom(self, node: BOMTreeSubAssemblyNode) -> bool:
        """
        BOM can be created only if all children are ready.
        """
        for child in node.children:
            if self._is_bom_creation_pending(child):
                return False
        return True
    
    # -------------------------
    # BOM creation
    # -------------------------

    def _create_bom_for_node(self, node: BOMTreeSubAssemblyNode) -> None:
        """
        Creates ERPNext BOM and assigns bom_no back to the node.
        """

        bom = frappe.new_doc("BOM")
        bom.company = self.company
        bom.item = node.item_code
        bom.bom_type = "Production" #TODO: As of now hardcoding
        bom.quantity = node.quantity
        bom.rm_cost_as_per = "Valuation Rate" # TODO: As of now hardcoding
        bom.project = None      #TODO: pending wiring
        bom.currency = "GBP"  # TODO: As of now hardcoding
        bom.conversion_rate = 1 #TODO: As of now hardcoding
        bom.buying_price_list = None #TODO: pending wiring
        # bom.is_active = 1
        # bom.is_default = 0

        #TODO: Order children by sequence
        for child in node.children:
            if child.node_type == "ITEM":
                item = frappe.new_doc("BOM Item")
                item.item_code = child.item_code
                item.qty = child.quantity
                item.uom = child.uom
                item.rate = 1 # TODO: As of now hardcoding
                item.stock_qty = child.quantity # TODO: think about this?
                item.stock_uom = child.uom # TODO: think about this?
                item.conversion_factor = 1 # TODO: As of now hardcoding
                item.do_not_explode = 0 # TODO: As of now hardcoding
                item.source_warehouse = None # TODO: pending wiring
                item.allow_alternative_item = 0 # TODO: As of now hardcoding
                bom.append("items", item)
            elif child.node_type == "SUB_ASSEMBLY":
                item = frappe.new_doc("BOM Item")
                item.item_code = child.item_code
                item.qty = child.quantity
                item.uom = child.uom
                item.rate = 1 # TODO: As of now hardcoding
                item.stock_qty = child.quantity # TODO: think about this?
                item.stock_uom = child.uom # TODO: think about this?
                item.conversion_factor = 1 # TODO: As of now hardcoding
                item.do_not_explode = 0 # TODO: As of now hardcoding
                item.source_warehouse = None # TODO: pending wiring
                item.allow_alternative_item = 0 # TODO: As of now hardcoding
                item.bom_no = child.bom_no
                bom.append("items", item)
            elif child.node_type == "OPERATION":
                bom.with_operations = True
                operation = frappe.new_doc("BOM Operation")
                operation.operation = child.name
                operation.time_in_mins = child.time_in_mins
                operation.sequence_id = child.sequence
                operation.workstation_type = child.workstation_type
                operation.workstation = child.workstation
                bom.append("operations", operation)

        bom.insert()
        bom.submit()  # TODO: Should submit immediately? Looks like yes it should be, to use it as sub-assembly in parent BOMs
        
        node.bom_no = bom.name
        self.newly_created_boms[node.node_unique_id] = bom.name
