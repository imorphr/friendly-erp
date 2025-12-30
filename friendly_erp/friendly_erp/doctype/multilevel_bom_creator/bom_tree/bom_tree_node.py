from dataclasses import dataclass, field
from typing import List, Literal, Optional

import frappe
from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item.multilevel_bom_creator_item import MultilevelBOMCreatorItem

NodeType = Literal["ITEM", "SUB_ASSEMBLY", "OPERATION", "COMPOUND_OPERATION"]


@dataclass
class BOMTreeNode:
    node_unique_id: str = ""
    parent_node_unique_id: str | None = None
    parent_node_ref: Optional['BOMTreeNode'] = None
    node_type: NodeType = None
    name: str = ""
    display_name: str = ""
    sequence: int = 0
    # node_type: NodeType = None
    children: List['BOMTreeNode'] = field(default_factory=list)

    can_add_child_item: bool = False
    can_add_child_operation: bool = False
    can_delete: bool = False

    depth: int = 0   # Depth in the tree
    # Indentation level for display purposes. Ideally this is same as depth.
    indent: int = 0

    def add_child(self, child_node: 'BOMTreeNode'):
        self.children.append(child_node)


@dataclass
class BOMTreeItemNode(BOMTreeNode):
    item_code: str = None
    quantity: float = 0.0
    uom: str = None


@dataclass
class BOMTreeSubAssemblyNode(BOMTreeItemNode):
    bom_no: str = ""


@dataclass
class BOMTreeOperationNode(BOMTreeNode):
    time_in_mins: float = 0.0
    workstation_type: str = None
    workstation: str = None


@dataclass
class BOMTreeCompoundOperationNode(BOMTreeOperationNode):
    pass


class BOMCreatorTreeNodeFactory:
    @staticmethod
    def create_from_multilevel_bom_creator_item(item: MultilevelBOMCreatorItem, parent_node_ref: BOMTreeNode) -> BOMTreeNode:
        node = None
        if item.node_type == "ITEM":
            node = BOMCreatorTreeNodeFactory._create_item_node(item)
        elif item.node_type == "SUB_ASSEMBLY":
            node = BOMCreatorTreeNodeFactory._create_sub_assembly_node(item)
        elif item.node_type == "OPERATION":
            node = BOMCreatorTreeNodeFactory._create_operation_node(item)
        elif item.node_type == "COMPOUND_OPERATION":
            node = BOMCreatorTreeNodeFactory._create_compound_operation_node(item)
        else:
            raise ValueError(f"Unknown node type: {item.node_type}")

        BOMCreatorTreeNodeFactory._set_common_fields(node, item.node_unique_id, parent_node_ref, item.sequence)
        # init action flag should always be called after parent_node_ref is set and other members are initialized
        BOMTreeNodeActionFlagInitializer.initialize_action_flags(node)

        return node
    
    @staticmethod
    def _set_common_fields(node, node_unique_id: str, parent_node_ref: BOMTreeNode, sequence: int):
        node.node_unique_id = node_unique_id
        node.parent_node_ref = parent_node_ref
        node.parent_node_unique_id = parent_node_ref.node_unique_id if parent_node_ref else None
        node.sequence = sequence
        if not parent_node_ref:
            node.indent = 0
            node.depth = 0
        else:
            node.indent = parent_node_ref.indent + 1
            node.depth = parent_node_ref.depth + 1

    @staticmethod
    def _create_item_node(item: MultilevelBOMCreatorItem) -> BOMTreeItemNode:
        return BOMTreeItemNode(
            node_type="ITEM",
            name=item.item_code,
            display_name=item.item_code,
            sequence=item.sequence,
            item_code=item.item_code,
            quantity=item.quantity,
            uom=item.uom,
        )

    @staticmethod
    def _create_sub_assembly_node(item: MultilevelBOMCreatorItem) -> BOMTreeSubAssemblyNode:
        return BOMTreeSubAssemblyNode(
            node_type="SUB_ASSEMBLY",
            name=item.item_code,
            display_name=item.item_code,
            sequence=item.sequence,
            item_code=item.item_code,
            quantity=item.quantity,
            uom=item.uom,
            bom_no=item.bom_no,
        )

    @staticmethod
    def _create_operation_node(item: MultilevelBOMCreatorItem) -> BOMTreeOperationNode:
        return BOMTreeOperationNode(
            node_type="OPERATION",
            name=item.operation,
            display_name=item.operation,
            time_in_mins=item.time_in_mins,
            workstation_type=item.workstation_type,
            workstation=item.workstation,
            sequence=item.sequence,
        )

    @staticmethod
    def _create_compound_operation_node(item: MultilevelBOMCreatorItem) -> BOMTreeCompoundOperationNode:
        pass
    
class ExistingBOMTreeNodeFactory:
    @staticmethod
    def create_from_existing_bom(bom, parent_node_ref: BOMTreeNode, sequence: int) -> BOMTreeSubAssemblyNode:
        node = BOMTreeSubAssemblyNode(
            node_type="SUB_ASSEMBLY",
            name=bom.name,
            display_name=f"{bom.item_name} [{bom.name}]",
            sequence=sequence,
            item_code=bom.item_name,
            quantity=bom.quantity,
            uom=bom.uom,
            bom_no=bom.name,
        )
        ExistingBOMTreeNodeFactory._set_common_fields(node, frappe.generate_hash(), parent_node_ref, sequence)
        # init action flag should always be called after parent_node_ref is set and other members are initialized
        BOMTreeNodeActionFlagInitializer.initialize_action_flags(node)

        return node
    
    @staticmethod
    def create_from_existing_bom_item(bom_item, parent_node_ref: BOMTreeNode, sequence: int) -> BOMTreeItemNode:
        node = BOMTreeItemNode(
            node_type="ITEM",
            name=bom_item.item_code,
            display_name=bom_item.item_code,
            sequence=sequence,
            item_code=bom_item.item_code,
            quantity=bom_item.qty,
            uom=bom_item.uom,
        )
        ExistingBOMTreeNodeFactory._set_common_fields(node, frappe.generate_hash(), parent_node_ref, sequence)
        # init action flag should always be called after parent_node_ref is set and other members are initialized
        BOMTreeNodeActionFlagInitializer.initialize_action_flags(node)
        return node
    
    @staticmethod
    def create_from_existing_bom_operation(bom_operation, parent_node_ref: BOMTreeNode, sequence: int) -> BOMTreeOperationNode:
        workstation_display_text = f"{bom_operation.workstation or bom_operation.workstation_type}"
        workstation_display_text = f" [{workstation_display_text}]" if workstation_display_text else ""
        node = BOMTreeOperationNode(
            node_type="OPERATION",
            name=bom_operation.operation,
            display_name=f"{bom_operation.idx}: {bom_operation.operation}{workstation_display_text}",
            time_in_mins=bom_operation.time_in_mins,
            workstation_type=bom_operation.workstation_type,
            workstation=bom_operation.workstation,
            sequence=sequence,
        )
        ExistingBOMTreeNodeFactory._set_common_fields(node, frappe.generate_hash(), parent_node_ref, sequence)
        # init action flag should always be called after parent_node_ref is set and other members are initialized
        BOMTreeNodeActionFlagInitializer.initialize_action_flags(node)
        return node
    
    @staticmethod
    def _set_common_fields(node, node_unique_id: str, parent_node_ref: BOMTreeNode, sequence: int):
        node.node_unique_id = node_unique_id
        node.parent_node_ref = parent_node_ref
        node.parent_node_unique_id = parent_node_ref.node_unique_id if parent_node_ref else None
        node.sequence = sequence
        if not parent_node_ref:
            node.indent = 0
            node.depth = 0
        else:
            node.indent = parent_node_ref.indent + 1
            node.depth = parent_node_ref.depth + 1

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
            node.can_add_child_item = False if hasattr(node, "bom_no") and node.bom_no or is_child_of_existing_sub_assembly else True
            node.can_add_child_operation = False if hasattr(node, "bom_no") and node.bom_no or is_child_of_existing_sub_assembly else True
            node.can_delete = False if is_child_of_existing_sub_assembly else True

        elif node.node_type == "ITEM":
            node.can_add_child_item = False if is_child_of_existing_sub_assembly else True
            node.can_add_child_operation = False if is_child_of_existing_sub_assembly else True
            node.can_delete = False if is_child_of_existing_sub_assembly else True

        elif node.node_type in ["OPERATION", "COMPOUND_OPERATION"]:
            node.can_add_child_item = False
            node.can_add_child_operation = False
            node.can_delete = False if is_child_of_existing_sub_assembly else True