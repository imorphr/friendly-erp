from collections import defaultdict
from typing import Dict, List
import frappe

from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree import (
    BOMTree,
    BOMTreeNode,
    BOMTreeOperationNode,
    BOMTreeSubOperationNode
)
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_node_factories import (
    BOMCreatorTreeNodeFactory,
    ExistingBOMTreeNodeFactory
)
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_qty_time_calculator import BOMTreeQtyTimeCalculator
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item_node.multilevel_bom_creator_item_node import MultilevelBOMCreatorItemNode
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_operation_node.multilevel_bom_creator_operation_node import MultilevelBOMCreatorOperationNode

class BOMCreatorTreeBuilder:
    """
    Builds a BOMTree from a Multilevel BOM Creator document.

    This builder traverses the flat list of item and operation nodes stored in the
    Multilevel BOM Creator document and reconstructs the hierarchical tree structure.
    It handles:
    - Root node creation.
    - Recursive addition of child items and operations.
    - Expansion of existing BOMs (sub-assemblies) referenced in the creator.
    - Expansion of operations into sub-operations.

    Note: There is no cycle detection in this tree while adding children. Because
    cycle checks are done upfront while adding item to multi level bom doctype's child items.
    So here it is safe to assume that there is no possibility of cycle.
    """
    def __init__(self, bom_creator_doc):
        if not bom_creator_doc:
            frappe.throw("BOM Creator document is required to build BOM Tree.")
        self.bom_creator_doc = bom_creator_doc
        self.creator_nodes: list[MultilevelBOMCreatorItemNode |
                                 MultilevelBOMCreatorOperationNode] = []
        self.creator_item_nodes_by_parent: Dict[str,
                                                List[MultilevelBOMCreatorItemNode]] = defaultdict(list)
        self.creator_operation_nodes_by_parent: Dict[str,
                                                     List[MultilevelBOMCreatorOperationNode]] = defaultdict(list)
        for item_node in (bom_creator_doc.item_nodes or []):
            self.creator_nodes.append(item_node)
            self.creator_item_nodes_by_parent[item_node.parent_node_unique_id].append(
                item_node)  # Map for fast lookup of children
        for op_node in (bom_creator_doc.operation_nodes or []):
            self.creator_nodes.append(op_node)
            self.creator_operation_nodes_by_parent[op_node.parent_node_unique_id].append(
                op_node)  # Map for fast lookup of children

        self.tree = None

    def create(self) -> BOMTree:
        if self.tree:
            frappe.throw("Tree is already built.")
        self.tree = BOMTree()
        self._build_tree()
        return self.tree

    def _build_tree(self):
        roots = [
            item for item in self.creator_nodes if not item.parent_node_unique_id]
        if len(roots) != 1:
            frappe.throw(
                "BOM Creator document must have exactly one root item.")

        root_item = roots[0]
        if root_item.node_type != "SUB_ASSEMBLY":
            frappe.throw("Root node type should be sub-assembly.")
        root_node = BOMCreatorTreeNodeFactory.create_from_multilevel_bom_creator_item(
            root_item, self.tree)
        self.tree.set_root(root_node)
        self._add_children_recursively(root_node)

    def _add_children_recursively(self, parent_node: BOMTreeNode):
        self._add_child_operation_nodes_recursively(parent_node)
        self._add_child_item_nodes_recursively(parent_node)

    def _add_child_operation_nodes_recursively(self, parent_node: BOMTreeNode):
        child_items = self.creator_operation_nodes_by_parent.get(
            parent_node.node_unique_id, [])

        if not child_items:
            return

        sorted_child_items = sorted(child_items, key=lambda x: x.sequence)

        for item in sorted_child_items:
            child_node = BOMCreatorTreeNodeFactory.create_from_multilevel_bom_creator_operation(
                item, self.tree)
            parent_node.add_child(child_node)
            sub_operation_tree = OperationTreeBuilder(item.operation).create()
            sub_operation_tree.mark_all_nodes_as_projected()
            self.tree.merge_another_tree(child_node, sub_operation_tree, True)


    def _add_child_item_nodes_recursively(self, parent_node: BOMTreeNode):
        child_items = self.creator_item_nodes_by_parent.get(
            parent_node.node_unique_id, [])

        # Existing BOM PROJECTION as well as LEAF NODE DETECTION
        if not child_items:
            if parent_node.node_type == "SUB_ASSEMBLY" and parent_node.is_preexisting_bom and parent_node.bom_no:
                existing_bom_tree = ExistingBOMTreeBuilder(
                    parent_node.bom_no).create()
                # As this tree is being created from existing BOM, mark all nodes as projected
                # Ideally these nodes are not coming from multilevel bom creator, but they are
                # projected from the existing bom node of the multilevel bom creator.
                existing_bom_tree.mark_all_nodes_as_projected()
                # Attach existing BOM tree's children to the current child_node
                self.tree.merge_another_tree(parent_node, existing_bom_tree, True)
            return

        sorted_child_items = sorted(child_items, key=lambda x: x.sequence)

        for item in sorted_child_items:
            child_node = BOMCreatorTreeNodeFactory.create_from_multilevel_bom_creator_item(
                item, self.tree)
            parent_node.add_child(child_node)
            self._add_children_recursively(child_node)


class OperationTreeBuilder:
    def __init__(self, operation: str):
        self.operation = operation
        self.tree = None

    def create(self) -> BOMTree:
        if self.tree:
            frappe.throw("Tree is already built.")
        self.tree = BOMTree()
        operation = frappe.get_doc("Operation", self.operation)
        if not operation:
            frappe.throw(f"Operation '{self.operation}' not found.")
        op_node = BOMTreeOperationNode(
            tree_ref=self.tree,
            node_unique_id=frappe.generate_hash(), # Using a GUID longer than 10 characters to reduce the risk of ID collisions
            node_type="OPERATION",
            sequence=1,
            operation=operation.name,
            internal_name=operation.name,
            display_name=operation.name,
        )
        
        self.tree.set_root(op_node)
        self._traverse_operations(self.operation, op_node)
        return self.tree

    def _traverse_operations(self, operation, parent_node: BOMTreeNode):
        operation_doc = frappe.get_doc("Operation", operation)
        for sub_operation in operation_doc.sub_operations or []:
            op_node = BOMTreeSubOperationNode(
                tree_ref=self.tree,
                node_unique_id=frappe.generate_hash(),  # Using a GUID longer than 10 characters to reduce the risk of ID collisions
                node_type="SUB_OPERATION",
                sequence=sub_operation.idx,
                operation=sub_operation.operation,
                internal_name=sub_operation.operation,
                display_name=f"{sub_operation.idx}: {sub_operation.operation}",
                time_in_mins=sub_operation.time_in_mins,
            )
            parent_node.add_child(op_node)
            # To prevent cycles, only expand the node if this operation does not exist in the ancestor path.
            if not self.tree.operation_node_exists_in_upward_path(parent_node.node_unique_id, sub_operation.operation):
                self._traverse_operations(sub_operation.operation, op_node)
            else:
                op_node.error_messages["CYCLIC_NODE"] = "Cyclic operation detected"

class ExistingBOMTreeBuilder:
    def __init__(self, bom_no: str):
        self.bom_no = bom_no
        self.tree = None

    def create(self) -> BOMTree:
        if self.tree:
            frappe.throw("Tree is already built.")
        self.tree = BOMTree()
        self._traverse_bom(self.bom_no, None, 0)
        return self.tree

    def _traverse_bom(self, bom_no: str, parent_node: BOMTreeNode, sequence: int):
        bom = frappe.get_doc("BOM", bom_no)
        if not bom:
            frappe.throw(f"BOM '{bom_no}' not found.")

        node = ExistingBOMTreeNodeFactory.create_from_bom(
            bom, sequence, self.tree)
        if not parent_node:
            self.tree.set_root(node)
        else:
            parent_node.add_child(node)

        # To prevent cycles, only expand the node if this item does not exist in the ancestor path.
        if not parent_node or not self.tree.item_node_exists_in_upward_path(parent_node.node_unique_id, bom.item):
            self._add_children_recursively(bom, node)
        else:
            node.error_messages["CYCLIC_NODE"] = "Cyclic item detected"

    def _add_children_recursively(self, bom, parent_node: BOMTreeNode):
        self._add_child_operation_nodes_recursively(bom, parent_node)
        self._add_child_item_nodes_recursively(bom, parent_node)

    def _add_child_operation_nodes_recursively(self, bom, parent_node: BOMTreeNode):
        operations = bom.operations or []
        for bom_operation in operations:
            child_node = ExistingBOMTreeNodeFactory.create_from_operation(
                bom_operation, bom_operation.idx, self.tree)
            parent_node.add_child(child_node)
            sub_operation_tree = OperationTreeBuilder(bom_operation.operation).create()
            sub_operation_tree.mark_all_nodes_as_projected()
            self.tree.merge_another_tree(child_node, sub_operation_tree, True)

    def _add_child_item_nodes_recursively(self, bom, parent_node: BOMTreeNode):
        items = bom.items or []
        for bom_item in items:
            is_sub_assembly = self._is_item_representing_sub_assembly(bom_item)
            should_not_explode = self._should_not_explode(bom_item)
            child_node = None
            if is_sub_assembly and not should_not_explode:
                self._traverse_bom(bom_item.bom_no, parent_node, bom_item.idx)
            else:
                child_node = ExistingBOMTreeNodeFactory.create_from_item(
                    bom_item, bom_item.idx, self.tree)
                parent_node.add_child(child_node)

    def _is_item_representing_sub_assembly(self, item) -> bool:
        return bool(item.bom_no)

    def _should_not_explode(self, item) -> bool:
        return item.do_not_explode