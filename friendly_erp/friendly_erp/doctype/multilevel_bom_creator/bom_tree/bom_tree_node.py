from dataclasses import dataclass, field
from typing import List, Literal

from friendly_erp.friendly_erp.doctype.multilevel_bom_creator_item.multilevel_bom_creator_item import MultilevelBOMCreatorItem

NodeType = Literal["ITEM", "SUB_ASSEMBLY", "OPERATION", "COMPOUND_OPERATION"]

@dataclass
class BOMTreeNode:
    node_guid: str = ""
    parent_node_guid: str | None = None
    name: str = ""
    display_name: str = ""
    sequence: int = 0
    node_type: NodeType = None
    children: List['BOMTreeNode'] = field(default_factory=list)

    def add_child(self, child_node: 'BOMTreeNode'):
        self.children.append(child_node)

@dataclass
class BOMTreeItemNode(BOMTreeNode):
    item_code: str = ""
    quantity: float = 0
    uom: str = ""
    node_type = "ITEM"

@dataclass
class BOMTreeSubAssemblyNode(BOMTreeItemNode):
    node_type = "SUB_ASSEMBLY"

@dataclass
class BOMTreeOperationNode(BOMTreeNode):
    node_type = "OPERATION"

@dataclass
class BOMTreeCompoundOperationNode(BOMTreeOperationNode):
    node_type = "COMPOUND_OPERATION"

class BOMTreeNodeFactory:
    @staticmethod
    def create_from_multilevel_bom_creator_item(item: MultilevelBOMCreatorItem) -> BOMTreeNode:
       if item.node_type == "ITEM":
           return BOMTreeNodeFactory._create_item_node(item)
       elif item.node_type == "SUB_ASSEMBLY":
           return BOMTreeNodeFactory._create_sub_assembly_node(item)
       elif item.node_type == "OPERATION":
           return BOMTreeNodeFactory._create_operation_node(item)
       elif item.node_type == "COMPOUND_OPERATION":
           return BOMTreeNodeFactory._create_compound_operation_node(item)
       else:
           raise ValueError(f"Unknown node type: {item.node_type}")

    def _create_item_node(item: MultilevelBOMCreatorItem) -> BOMTreeItemNode:
        return BOMTreeItemNode(
            node_guid = item.node_guid,
            parent_node_guid = item.parent_node_guid,
            node_type = "ITEM",
            name = item.item_code,
            display_name = item.item_code,
            sequence = item.sequence,
            item_code = item.item_code,
            quantity = item.quantity,
            uom = item.uom,
        )
    
    def _create_sub_assembly_node(item: MultilevelBOMCreatorItem) -> BOMTreeSubAssemblyNode:
        return BOMTreeSubAssemblyNode(
            node_guid = item.node_guid,
            parent_node_guid = item.parent_node_guid,
            node_type = "SUB_ASSEMBLY",
            name = item.item_code,
            display_name = item.item_code,
            sequence = item.sequence,
            item_code = item.item_code,
            quantity = item.quantity,
            uom = item.uom,
        )
    
    def _create_operation_node(item: MultilevelBOMCreatorItem) -> BOMTreeOperationNode:
        pass

    def _create_compound_operation_node(item: MultilevelBOMCreatorItem) -> BOMTreeCompoundOperationNode:
        pass