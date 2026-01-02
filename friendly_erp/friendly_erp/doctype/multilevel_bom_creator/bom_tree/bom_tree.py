from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional
import frappe

# ===============================================================================
#                             Tree Node Classes
# ===============================================================================

NodeType = Literal["ITEM", "SUB_ASSEMBLY", "OPERATION"]

@dataclass
class BOMTreeNode:
    node_type: NodeType
    node_unique_id: str = None
    internal_name: str = None
    display_name: str = None
    parent_node_ref: Optional['BOMTreeNode'] = None
    tree_ref: 'BOMTree' = None
    children: List['BOMTreeNode'] = field(default_factory=list)
    # When node is part of a tree, sequence indicates the order among siblings
    sequence: int = 0
    # When node is part of a tree, depth indicates the level in the tree
    depth: int = 0
    # Indentation level for display purposes. Frappe UI tree control needs it.
    # Ideally this is same as depth.
    indent: int = 0
    # This flag  indicates whether this node is part of the tree or was projected from existing BOM
    # Projected nodes are there to give full structure/picture of the BOM to user on UI.
    # But projected nodes cannot be modified or deleted. Hence this flag helps to identify such nodes.
    is_projected: bool = False

    # Action flags
    can_add_child_item: bool = False
    can_add_child_operation: bool = False
    can_delete: bool = False

    # ⚠️ Use this method to add child. Do not directly append to children array of node.
    # Because this method performs some validations and assigns important fields like
    # parent ref, indent and depth.
    def add_child(self, child_node: 'BOMTreeNode'):
        if not self.tree_ref:
            frappe.throw("Node is not attached to any tree")
        if child_node.parent_node_ref is not None:
            frappe.throw(f"Node '{self.display_name}' already has a parent")

        current = self
        while current:
            if current is child_node:
                frappe.throw(f"Circular parent-child relationship detected for {child_node.display_name}")
            current = current.parent_node_ref
     
        child_node.parent_node_ref = self
        child_node.depth = self.depth + 1
        # Indent and depth will have same value.
        child_node.indent = child_node.depth

        self.children.append(child_node)
        self.tree_ref.add_to_node_map(child_node)

        # Calling Order Important: Always call this after parent_node_ref is assigned and node is added to tree
        BOMTreeNodeActionFlagInitializer.initialize_action_flags(child_node)

    def mark_as_projected(self):
        self.is_projected = True

    def is_leaf(self):
        return not self.children


@dataclass
class BOMTreeItemNode(BOMTreeNode):
    item_code: str = None
    quantity: float = 0.0
    uom: str = None


@dataclass
class BOMTreeSubAssemblyNode(BOMTreeItemNode):
    bom_no: str = ""
    # Flag to indicate whether this sub-assembly node corresponds to an existing BOM
    # While creating Multi-level BOM,
    # (1) user can add nested item nodes to create new sub-assemblies
    # for such newly added sub-assemblies, this flag will be False.
    # (2) or user can reference existing BOMs as sub-assemblies
    # for such existing BOM referenced sub-assemblies, this flag will be True.
    # Once all the BOMs from BOM creator tree are created, then ideally all sub-assembly nodes
    # will have BOM numbers. But at that time also this flag specifically will indicate
    # whether the sub-assembly was being created afresh while converting tree to BOMs
    # or the sub-assembly was referencing a pre-existing BOM.
    is_preexisting_bom: bool = False
    do_not_explode: bool = False


@dataclass
class BOMTreeOperationNode(BOMTreeNode):
    operation: str = None
    time_in_mins: float = 0.0
    workstation_type: str = None
    workstation: str = None
    
# ===============================================================================
#                             Tree Class
# ===============================================================================

class BOMTree:
    def __init__(self):
        self.root: BOMTreeNode = None
        self.node_map: Dict[str, BOMTreeNode] = {}

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

# ===============================================================================
#                             Node Action Flag Initializer
# ===============================================================================

class BOMTreeNodeActionFlagInitializer:
    @staticmethod
    def initialize_action_flags(node: BOMTreeNode):
        if not node.parent_node_ref:
            # This is the root node
            node.can_add_child_item = True
            node.can_add_child_operation = True
            node.can_delete = False  # Root node cannot be deleted
            return

        # Traverse up using parent_node_ref up to root and check any parent with type SUB_ASSEMBLY and bom_no is present
        current_node = node.parent_node_ref
        is_child_of_existing_sub_assembly = False
        while current_node:
            if current_node.node_type == "SUB_ASSEMBLY" and hasattr(current_node, "bom_no") and current_node.bom_no:
                is_child_of_existing_sub_assembly = True
                break
            current_node = current_node.parent_node_ref

        if node.node_type == "SUB_ASSEMBLY":
            # If the node is a Sub-Assembly with an existing BOM, no actions allowed because existing BOMs cannot be modified
            node.can_add_child_item = False if hasattr(
                node, "bom_no") and node.bom_no or is_child_of_existing_sub_assembly else True
            node.can_add_child_operation = False if hasattr(
                node, "bom_no") and node.bom_no or is_child_of_existing_sub_assembly else True
            node.can_delete = False if is_child_of_existing_sub_assembly else True

        elif node.node_type == "ITEM":
            node.can_add_child_item = False if is_child_of_existing_sub_assembly else True
            node.can_add_child_operation = False if is_child_of_existing_sub_assembly else True
            node.can_delete = False if is_child_of_existing_sub_assembly else True

        elif node.node_type == "OPERATION":
            node.can_add_child_item = False
            node.can_add_child_operation = False
            node.can_delete = False if is_child_of_existing_sub_assembly else True

