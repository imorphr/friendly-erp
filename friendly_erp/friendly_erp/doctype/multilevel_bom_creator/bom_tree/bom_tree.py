from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional
import frappe

# ===============================================================================
#                             Tree Node Classes
# ===============================================================================

NodeType = Literal["ITEM", "SUB_ASSEMBLY", "OPERATION", "SUB_OPERATION"]
NodeErrorCode = Literal["CYCLIC_NODE"]


@dataclass
class BOMTreeNode:
    node_type: NodeType
    node_unique_id: str = None
    internal_name: str = None
    display_name: str = None
    parent_node_unique_id: str = None
    parent_node_ref: Optional['BOMTreeNode'] = None
    tree_ref: 'BOMTree' = None
    children: List['BOMTreeNode'] = field(default_factory=list)
    child_count: int = 0
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

    error_messages: Dict[NodeErrorCode, str] = field(default_factory=dict)
    warning_messages: Dict[NodeErrorCode, str] = field(default_factory=dict)

    # Action flags
    can_add_child_item: bool = False
    can_add_child_operation: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_duplicate_bom: bool = False

    # ⚠️ Use this method to add child. Do not directly append to children array of node.
    # Because this method performs some validations and assigns important fields like
    # parent ref, indent and depth.
    def add_child(self, child_node: 'BOMTreeNode'):
        if not self.tree_ref:
            frappe.throw("Node is not attached to any tree")
        if child_node.parent_node_ref is not None:
            frappe.throw(f"Node '{self.display_name}' already has a parent")
        if child_node.tree_ref is not self.tree_ref:
            frappe.throw("Node belongs to a different tree")

        current = self
        while current:
            if current is child_node:
                frappe.throw(
                    f"Circular parent-child relationship detected for {child_node.display_name}")
            current = current.parent_node_ref

        child_node.parent_node_unique_id = self.node_unique_id
        child_node.parent_node_ref = self
        child_node.depth = self.depth + 1
        # Indent and depth will have same value.
        child_node.indent = child_node.depth

        self.children.append(child_node)
        self.child_count = len(self.children)
        self.tree_ref.add_to_node_map(child_node)

        # Calling Order Important: Always call this after parent_node_ref is assigned and node is added to tree
        BOMTreeNodeActionFlagInitializer.initialize_action_flags(child_node)

    def mark_as_projected(self):
        self.is_projected = True

    def is_leaf(self):
        return not self.children


@dataclass
class BOMTreeCostAwareNode(BOMTreeNode):
    rate: float = None
    amount: float = None
    base_rate: float = None
    base_amount: float = None
    # Root-relative cost (derived):Total cost of this node required to produce
    # the configured BOM quantity of the ROOT node.
    total_required_amount: float = None


@dataclass
class BOMTreeItemNode(BOMTreeCostAwareNode):
    item_code: str = None
    do_not_explode: bool = False
    is_stock_item: bool = False

    uom: str = None                 # Required UOM
    stock_uom: str = None           # Stock UOM
    conversion_factor: float = 1.0  # 1 Required UOM = <conversion_factor> Stock UOM

    # Parent-relative quantity: Quantity of this item required to produce BOM-quantity of the parent node in Required UOM.
    # ie Quantity needed per ONE execution of parent BOM in Required UOM.
    component_qty_per_parent_bom_run: float = 0.0
    # Quantity needed per ONE execution of parent BOM in Stock UOM.
    component_stock_qty_per_parent_bom_run: float = 0.0
    # Root-relative quantity (derived):Total quantity of this item required to produce
    # the configured BOM quantity of the ROOT node.
    # This value is calculated by propagating quantities top-down through the BOM tree.
    total_required_qty: float = 0.0


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

    # Self BOM quantity: Quantity of the sub-assembly item produced by ONE execution of this sub-assembly BOM.
    # This is in Stock UOM.
    own_batch_size: float = 0.0

    # Number of times this sub-assembly BOM must be executed in order to satisfy
    # the total_required_qty coming from the parent BOM.
    #
    # This value bridges the mismatch between:
    # - how much of this sub-assembly the parent needs, and
    # - how much this sub-assembly BOM produces per execution.
    #
    # Child nodes of this sub-assembly must use bom_run_count (not total_required_qty)
    # as the effective parent quantity when calculating their own requirements.
    bom_run_count: float = 0.0


@dataclass
class BOMTreeOperationNode(BOMTreeCostAwareNode):
    operation: str = None
    time_in_mins: float = 0.0
    fixed_time: bool = False
    workstation_type: str = None
    workstation: str = None
    # Root-relative time (derived):Total time of this operation required to produce
    # the configured BOM quantity of the ROOT node.
    # This value is calculated by propagating time top-down through the BOM tree.
    total_required_time_in_mins: float = 0.0

    # Following fields are important to calculate rate and amount fields for operation node
    hour_rate: float = 0.0
    base_hour_rate: float = 0.0
    batch_size: float = 0.0
    set_cost_based_on_bom_qty: bool = False

@dataclass
class BOMTreeSubOperationNode(BOMTreeOperationNode):
    pass


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
        self.root.parent_node_unique_id = None
        self.root.parent_node_ref = None
        self.root.depth = 0
        self.root.indent = 0
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

    def get_descendant_node_ids(self, node_unique_id: str) -> set[str]:
        """
        Return a set of node_unique_id values for the given node and
        all of its descendants (up to n levels deep).

        The returned set always includes the given node itself.
        """
        self.ensure_root_exists()

        start_node = self.find_node_by_unique_id(node_unique_id)
        if not start_node:
            frappe.throw(f"Node with id '{node_unique_id}' not found in tree")

        descendant_ids: set[str] = set()

        def _collect(node: BOMTreeNode):
            descendant_ids.add(node.node_unique_id)
            for child in (node.children or []):
                _collect(child)

        _collect(start_node)
        return descendant_ids

    def item_node_exists_in_upward_path(self, start_node_unique_id: str, item_code: str) -> bool:
        """
        Check whether the given item_code exists on the start node
        or any of its parent nodes (upward traversal).

        Used to prevent cycles in the tree.
        """
        start_node = self.node_map.get(start_node_unique_id)

        if not start_node:
            frappe.throw(
                f"Node with unique_id '{start_node_unique_id}' not found in BOM tree."
            )

        current = start_node
        while current:
            if current.node_type == "ITEM" or current.node_type == "SUB_ASSEMBLY":
                if current.item_code == item_code:
                    return True

            current = current.parent_node_ref

        return False

    def operation_node_exists_in_upward_path(self, start_node_unique_id: str, operation: str) -> bool:
        """
        Check whether the given operation exists on the start node
        or any of its parent nodes (upward traversal).

        Used to prevent cycles in the tree.
        """
        start_node = self.node_map.get(start_node_unique_id)

        if not start_node:
            frappe.throw(
                f"Node with unique_id '{start_node_unique_id}' not found in BOM tree."
            )

        current = start_node
        while current:
            if current.node_type == "OPERATION" or current.node_type == "SUB_OPERATION":
                if current.operation == operation:
                    return True

            current = current.parent_node_ref

        return False

    def mark_all_nodes_as_projected(self) -> None:
        """
        Mark all nodes in the tree as projected.
        """
        self.ensure_root_exists()

        # To avoid recursion, self.node_map is used which has all the nodes of the tree
        for node in self.node_map.values():
            node.mark_as_projected()

    def merge_another_tree(self, parent_node: BOMTreeNode, another_tree: 'BOMTree', exclude_root: bool):
        """
        Merge another BOMTree into this tree under the given parent_node.

        Algorithm:
        1. Validate inputs and ownership.
        2. Decide which nodes from another_tree should be attached
        (root OR root's children based on exclude_root).
        3. Attach selected nodes under parent_node and fix parent references.
        4. Update tree_ref for all merged nodes to point to this tree.
        5. Merge node_map entries from another_tree into this tree's node_map.
        """
        self.ensure_root_exists()
        if not another_tree:
            frappe.throw("Other tree was not given for merge operation.")
        if not parent_node:
            frappe.throw("Parent node not specified.")

        # Validate parent node belongs to this tree
        if (
            parent_node.tree_ref is not self
            or parent_node.node_unique_id not in self.node_map
            or self.node_map[parent_node.node_unique_id] is not parent_node
        ):
            frappe.throw(
                f"Parent node '{parent_node.display_name}' does not belong to this tree"
            )

        another_tree.ensure_root_exists()

        # Step 1: Decide nodes to merge
        if exclude_root:
            nodes_to_merge = another_tree.root.children or []
        else:
            nodes_to_merge = [another_tree.root]

        # Step 2: Update tree_ref for nodes to merge
        for node in another_tree.node_map.values():
            if exclude_root and node is another_tree.root:
                continue     # Skip root if excluded

            node.tree_ref = self

        # Step 4: Attach nodes to parent_node
        for node in nodes_to_merge:
            # Reset parent_node_ref as it is going to be child of new parent
            node.parent_node_ref = None
            parent_node.add_child(node)
            # Delete added node from another tree's node_map as node is now merged
            del another_tree.node_map[node.node_unique_id]

        # Step 5: Update depth & indent
        base_depth = parent_node.depth + 1
        for node in nodes_to_merge:
            self._update_subtree_depth_and_indent(node, base_depth)

        # Step 6: Merge node_map entries for all (upto n level) merged nodes
        for unique_id, node in another_tree.node_map.items():
            # Skip root if excluded
            if exclude_root and node is another_tree.root:
                continue

            if unique_id in self.node_map:
                frappe.throw(
                    f"Duplicate node '{node.display_name}' detected while merging trees"
                )

            self.add_to_node_map(node)

    def _update_subtree_depth_and_indent(
        self,
        node: BOMTreeNode,
        base_depth: int
    ):
        """
        Update depth and indent for the given node and its subtree.
        """
        node.depth = base_depth
        node.indent = base_depth

        for child in (node.children or []):
            self._update_subtree_depth_and_indent(child, base_depth + 1)

    def ensure_root_exists(self):
        if not self.root:
            frappe.throw("Root node is not present")

    def get_total_node_count(self) -> int:
        """
        Return total number of nodes present in the tree.
        """
        self.ensure_root_exists()
        return len(self.node_map)

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
            node.can_edit = False # Root node cannot be edited
            node.can_delete = False  # Root node cannot be deleted
            node.can_duplicate_bom = False
            return

        # If current node is projected node then do not allow any option on it
        if node.is_projected:
            node.can_add_child_item = False
            node.can_add_child_operation = False
            node.can_edit = False
            node.can_delete = False
            node.can_duplicate_bom = False
            return

        # Traverse up using parent_node_ref up to root and check any parent with type SUB_ASSEMBLY and is_preexisting_bom is true
        current_node = node.parent_node_ref
        is_child_of_existing_sub_assembly = False
        while current_node:
            if current_node.node_type == "SUB_ASSEMBLY" and hasattr(current_node, "is_preexisting_bom") and current_node.is_preexisting_bom:
                is_child_of_existing_sub_assembly = True
                break
            current_node = current_node.parent_node_ref

        if node.node_type == "SUB_ASSEMBLY":
            # If the node is a Sub-Assembly with an existing BOM, no actions allowed because existing BOMs cannot be modified
            node.can_add_child_item = False if hasattr(
                node, "bom_no") and node.bom_no or is_child_of_existing_sub_assembly else True
            node.can_add_child_operation = False if hasattr(
                node, "bom_no") and node.bom_no or is_child_of_existing_sub_assembly else True
            node.can_edit = False if is_child_of_existing_sub_assembly else True
            node.can_delete = False if is_child_of_existing_sub_assembly else True
            node.can_duplicate_bom = True if hasattr(
                node, "bom_no") and node.bom_no and not is_child_of_existing_sub_assembly and hasattr(
                node, "is_preexisting_bom") and node.is_preexisting_bom else False

        elif node.node_type == "ITEM":
            node.can_add_child_item = False
            node.can_add_child_operation = False
            node.can_edit = False if is_child_of_existing_sub_assembly else True
            node.can_delete = False if is_child_of_existing_sub_assembly else True
            node.can_duplicate_bom = False

        elif node.node_type == "OPERATION":
            node.can_add_child_item = False
            node.can_add_child_operation = False
            node.can_edit = False if is_child_of_existing_sub_assembly else True
            node.can_delete = False if is_child_of_existing_sub_assembly else True
            node.can_duplicate_bom = False

        elif node.node_type == "SUB_OPERATION":
            node.can_add_child_item = False
            node.can_add_child_operation = False
            node.can_edit = False
            node.can_delete = False
            node.can_duplicate_bom = False
