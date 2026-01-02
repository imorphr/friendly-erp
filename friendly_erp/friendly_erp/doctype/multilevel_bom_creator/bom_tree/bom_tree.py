from collections import defaultdict
from typing import Dict, List
import frappe
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator.bom_tree.bom_tree_node import (
    BOMTreeNode,
    BOMCreatorTreeNodeFactory,
    BOMTreeNodeActionFlagInitializer,
    ExistingBOMTreeNodeFactory
)
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item_node.multilevel_bom_creator_item_node import MultilevelBOMCreatorItemNode
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_operation_node.multilevel_bom_creator_operation_node import MultilevelBOMCreatorOperationNode


class BOMTree:
    def __init__(self):
        self.root: BOMTreeNode = None
        self.node_map: dict[str, BOMTreeNode] = {}

    def set_root(self, root_node: BOMTreeNode):
        if not root_node:
            frappe.throw("Root node must be given")
        if not root_node.node_unique_id:
            frappe.throw("Unique id is not assigned to the root node.")
        if self.root:
            frappe.throw("Root node is already set. Can not set it again.")
        self.root = root_node
        self.root.tree_ref = self   # Putting tree ref inside root node ref
        self.node_map[root_node.node_unique_id] = root_node
        BOMTreeNodeActionFlagInitializer.initialize_action_flags(root_node)

    def add_to_node_map(self, node: BOMTreeNode):
        self.ensure_root_exists()
        if node.tree_ref is not self:
            frappe.throw("Node belongs to a different tree")
        if not node.node_unique_id:
            frappe.throw(
                f"Unique id is not assigned to the node {node.display_name}.")
        if node.node_unique_id in self.node_map:
            frappe.throw(
                f"Node {node.display_name} is already present in the tree.")
        self.node_map[node.node_unique_id] = node

    def find_node_by_unique_id(self, node_unique_id: str) -> BOMTreeNode | None:
        self.ensure_root_exists()
        return self.node_map.get(node_unique_id, None)

    def to_dict(self) -> dict:
        """
        Convert Node (and its children) into a JSON-serializable dict.
        """
        self.ensure_root_exists()
        return self._to_dict_recursive(self.root)

    def _to_dict_recursive(self, node: BOMTreeNode) -> dict:
        data = dict(node.__dict__)
        # Remove tree reference to avoid circular references in JSON
        data.pop("tree_ref", None)
        # Remove parent references to avoid circular references in JSON
        data.pop("parent_node_ref", None)
        # Recursively convert children
        data["children"] = [
            self._to_dict_recursive(child) for child in (node.children or [])
        ]

        return data

    def to_depth_first_flat_list(self) -> list[dict]:
        self.ensure_root_exists()

        rows: list[dict] = []
        self._to_depth_first_flat_list_recursive(self.root, rows)
        return rows

    def _to_depth_first_flat_list_recursive(self, node: BOMTreeNode, rows: list[dict]) -> None:
        row = dict(node.__dict__)
        # Remove tree reference to avoid circular references in JSON
        row.pop("tree_ref", None)
        # Remove children property from flat row
        row.pop("children", None)
        # Remove parent reference to avoid circular refs
        row.pop("parent_node_ref", None)
        rows.append(row)

        for child in (node.children or []):
            self._to_depth_first_flat_list_recursive(child, rows)

    def get_leaf_nodes(self) -> list[BOMTreeNode]:
        self.ensure_root_exists()
        return [node for node in self.node_map.values() if not node.children]

    def mark_all_nodes_as_projected(self) -> None:
        """
        Mark all nodes in the tree as projected.
        """
        self.ensure_root_exists()

        for node in self.node_map.values():
            node.mark_as_projected()

    def ensure_root_exists(self):
        if not self.root:
            frappe.throw("Root node is not present")


class BOMCreatorTreeBuilder:
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
            # self._add_children_recursively(child_node)

    def _add_child_item_nodes_recursively(self, parent_node: BOMTreeNode):
        child_items = self.creator_item_nodes_by_parent.get(
            parent_node.node_unique_id, [])

        # LEAF NODE DETECTION
        if not child_items:
            return

        sorted_child_items = sorted(child_items, key=lambda x: x.sequence)

        for item in sorted_child_items:
            child_node = BOMCreatorTreeNodeFactory.create_from_multilevel_bom_creator_item(
                item, self.tree)
            parent_node.add_child(child_node)
            self._add_children_recursively(child_node)
            # if item.node_type == "SUB_ASSEMBLY" and item.bom_no and not child_node.children:
            #     existing_bom_tree = ExistingBOMTreeBuilder(
            #         item.bom_no, child_node, item.sequence, node_map, leaf_node_list
            #     ).create()
            #     # Attach existing BOM tree's children to the current child_node
            #     for existing_child in existing_bom_tree.root.children:
            #         child_node.add_child(existing_child)


class ExistingBOMTreeBuilder:
    def __init__(self, bom_name: str):
        self.bom_name = bom_name
        self.tree = None

    def create(self) -> BOMTree:
        if self.tree:
            frappe.throw("Tree is already built.")
        self.tree = BOMTree()
        self._traverse_bom(self.bom_name, None, 0)
        return self.tree

    def _traverse_bom(self, bom_name: str, parent_node: BOMTreeNode, sequence: int) -> BOMTreeNode:
        bom = frappe.get_doc("BOM", bom_name)
        if not bom:
            frappe.throw(f"BOM '{bom_name}' not found.")

        node = ExistingBOMTreeNodeFactory.create_from_bom(
            bom, sequence, self.tree)
        if not parent_node:
            self.tree.set_root(node)
        else:
            parent_node.add_child(node)
        self._add_children_recursively(bom, node)

    def _add_children_recursively(self, bom, parent_node: BOMTreeNode):
        self._add_child_operation_nodes_recursively(bom, parent_node)
        self._add_child_item_nodes_recursivly(bom, parent_node)

    def _add_child_operation_nodes_recursively(self, bom, parent_node: BOMTreeNode):
        operations = bom.operations or []
        for bom_operation in operations:
            child_node = ExistingBOMTreeNodeFactory.create_from_operation(
                bom_operation, bom_operation.idx, self.tree)
            parent_node.add_child(child_node)

    def _add_child_item_nodes_recursivly(self, bom, parent_node: BOMTreeNode):
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
