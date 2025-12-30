# Copyright (c) 2025, iMORPHr Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class MultilevelBOMCreatorItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		allow_alternative_item: DF.Check
		bom_no: DF.Link | None
		cost: DF.Currency
		currency: DF.Link | None
		do_not_explode: DF.Check
		has_variants: DF.Check
		include_item_in_manufacturing: DF.Check
		inspection_required: DF.Check
		is_stock_item: DF.Check
		item_code: DF.Link | None
		item_operation: DF.Link | None
		node_type: DF.Literal["", "ROOT", "ITEM", "OPERATION", "SUB_ASSEMBLY", "COMPOUND_OPERATION"]
		node_unique_id: DF.Data
		operation: DF.Link | None
		parent: DF.Data
		parent_node_unique_id: DF.Data | None
		parentfield: DF.Data
		parenttype: DF.Data
		project: DF.Link | None
		quantity: DF.Float
		rate: DF.Float
		rm_cost_as_per: DF.Literal["Valuation Rate", "Last Purchase Rate", "Price List"]
		sequence: DF.Int
		set_rate_of_sub_assembly_item_based_on_bom: DF.Check
		source_warehouse: DF.Link | None
		sourced_by_supplier: DF.Check
		time_in_mins: DF.Float
		uom: DF.Link | None
		workstation: DF.Link | None
		workstation_type: DF.Link | None
	# end: auto-generated types
	pass
