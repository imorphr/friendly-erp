from dataclasses import dataclass, field
from typing import List, Literal, Optional

import frappe
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item_node.multilevel_bom_creator_item_node import MultilevelBOMCreatorItemNode
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_operation_node.multilevel_bom_creator_operation_node import MultilevelBOMCreatorOperationNode

NodeType = Literal["ITEM", "SUB_ASSEMBLY", "OPERATION"]


# ===============================================================================
#                             Tree Node Classes
# ===============================================================================
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
     
        self.children.append(child_node)
        self.tree_ref.add_to_node_map(child_node)
        child_node.parent_node_ref = self
        child_node.depth = self.depth + 1
        # Indent and depth will have same value.
        child_node.indent = child_node.depth

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
#                             Tree Node Factories
# ===============================================================================

class BOMCreatorTreeNodeFactory:
    @staticmethod
    def create_from_multilevel_bom_creator_item(item: MultilevelBOMCreatorItemNode, tree_ref) -> BOMTreeNode:
        node = None
        if item.node_type == "ITEM":
            node = BOMCreatorTreeNodeFactory._create_item_node(item)
        elif item.node_type == "SUB_ASSEMBLY":
            node = BOMCreatorTreeNodeFactory._create_sub_assembly_node(item)
        else:
            raise ValueError(f"Unknown node type: {item.node_type}")

        node.node_unique_id = item.node_unique_id
        node.sequence = item.sequence
        node.tree_ref = tree_ref
        return node
    
    @staticmethod
    def create_from_multilevel_bom_creator_operation(item: MultilevelBOMCreatorOperationNode, tree_ref) -> BOMTreeNode:
        node = None
        if item.node_type == "OPERATION":
            node = BOMCreatorTreeNodeFactory._create_operation_node(item)
        else:
            raise ValueError(f"Unknown node type: {item.node_type}")

        node.node_unique_id = item.node_unique_id
        node.sequence = item.sequence
        node.tree_ref = tree_ref
        return node

    @staticmethod
    def _create_item_node(item: MultilevelBOMCreatorItemNode) -> BOMTreeItemNode:
        return BOMTreeItemNode(
            node_type="ITEM",
            item_code=item.item_code,
            internal_name=item.item_code,
            display_name=item.item_code,    # TODO: should we use item_name here?
            quantity=item.quantity,
            uom=item.uom,
        )

    @staticmethod
    def _create_sub_assembly_node(item: MultilevelBOMCreatorItemNode) -> BOMTreeSubAssemblyNode:
        return BOMTreeSubAssemblyNode(
            node_type="SUB_ASSEMBLY",
            item_code=item.item_code,
            bom_no=item.bom_no,
            internal_name=item.item_code,
            display_name=item.item_code,
            quantity=item.quantity,
            uom=item.uom,
        )

    @staticmethod
    def _create_operation_node(item: MultilevelBOMCreatorOperationNode) -> BOMTreeOperationNode:
        ws = item.workstation or item.workstation_type
        workstation_display_text = f" [{ws}]" if ws else ""
        return BOMTreeOperationNode(
            node_type="OPERATION",
            operation=item.operation,
            internal_name=item.operation,
            display_name=f"{item.sequence}: {item.operation}{workstation_display_text}",
            time_in_mins=item.time_in_mins,
            workstation_type=item.workstation_type,
            workstation=item.workstation,
        )


class ExistingBOMTreeNodeFactory:
    @staticmethod
    def create_from_bom(bom, sequence: int, tree_ref) -> BOMTreeSubAssemblyNode:
        return BOMTreeSubAssemblyNode(
            node_type="SUB_ASSEMBLY",
            tree_ref=tree_ref,
            node_unique_id=frappe.generate_hash(),
            sequence=sequence,
            item_code=bom.item,
            bom_no=bom.name,
            internal_name=bom.item,
            display_name=bom.item,
            quantity=bom.quantity,
            uom=bom.uom,
        )

    @staticmethod
    def create_from_item(bom_item, sequence: int, tree_ref) -> BOMTreeItemNode:
        return BOMTreeItemNode(
            node_type="ITEM",
            tree_ref=tree_ref,
            node_unique_id=frappe.generate_hash(),
            sequence=sequence,
            item_code=bom_item.item_code,
            internal_name=bom_item.item_code,
            display_name=bom_item.item_code,
            quantity=bom_item.qty,
            uom=bom_item.uom,
        )

    @staticmethod
    def create_from_operation(bom_operation, sequence: int, tree_ref) -> BOMTreeOperationNode:
        ws = bom_operation.workstation or bom_operation.workstation_type
        workstation_display_text = f" [{ws}]" if ws else ""
        return BOMTreeOperationNode(
            node_type="OPERATION",
            tree_ref=tree_ref,
            node_unique_id=frappe.generate_hash(),
            sequence=sequence,
            operation=bom_operation.operation,
            internal_name=bom_operation.operation,
            display_name=f"{bom_operation.idx}: {bom_operation.operation}{workstation_display_text}",
            time_in_mins=bom_operation.time_in_mins,
            workstation_type=bom_operation.workstation_type,
            workstation=bom_operation.workstation,
        )

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

        elif node.node_type in ["OPERATION", "COMPOUND_OPERATION"]:
            node.can_add_child_item = False
            node.can_add_child_operation = False
            node.can_delete = False if is_child_of_existing_sub_assembly else True
