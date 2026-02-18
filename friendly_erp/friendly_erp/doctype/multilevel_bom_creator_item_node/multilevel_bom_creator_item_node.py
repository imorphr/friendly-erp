# Copyright (c) 2025, iMORPHr Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class MultilevelBOMCreatorItemNode(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		allow_alternative_item: DF.Check
		amount: DF.Currency
		base_amount: DF.Currency
		base_rate: DF.Currency
		bom_no: DF.Link | None
		bom_run_count: DF.Float
		component_qty_per_parent_bom_run: DF.Float
		component_stock_qty_per_parent_bom_run: DF.Float
		conversion_factor: DF.Float
		do_not_explode: DF.Check
		include_item_in_manufacturing: DF.Check
		inspection_required: DF.Check
		is_preexisting_bom: DF.Check
		is_stock_item: DF.Check
		item_code: DF.Link | None
		item_operation: DF.Link | None
		node_type: DF.Literal["ITEM", "SUB_ASSEMBLY"]
		node_unique_id: DF.Data
		own_batch_size: DF.Float
		parent: DF.Data
		parent_node_unique_id: DF.Data | None
		parentfield: DF.Data
		parenttype: DF.Data
		rate: DF.Currency
		sequence: DF.Int
		sourced_by_supplier: DF.Check
		stock_uom: DF.Link | None
		total_required_amount: DF.Currency
		total_required_qty: DF.Float
		uom: DF.Link | None
	# end: auto-generated types
	pass
