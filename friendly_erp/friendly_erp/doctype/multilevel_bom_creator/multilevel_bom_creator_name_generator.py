import re

import frappe
from frappe.utils import cint

class MultilevelBOMCreatorNameGenerator:
    PREFIX = "MLBOMC"
    MAX_NAME_LENGTH = 140

    @classmethod
    def generate(cls, doc) -> str:
        name = None
        search_key = f"{cls.PREFIX}-{doc.item_code}%"
        existing_creators = frappe.get_all(
            "Multilevel BOM Creator", filters={"name": search_key, "amended_from": ["is", "not set"]}, pluck="name"
        )

        index = cls.get_index_for_bom(existing_creators)
        suffix = "%.3i" % index  # convert index to string (1 -> "001")
        creator_name = f"{cls.PREFIX}-{doc.item_code}-{suffix}"

        if len(creator_name) <= cls.MAX_NAME_LENGTH:
            name = creator_name
        else:
            # since max characters for name is 140, remove enough characters from the
            # item name to fit the prefix, suffix and the separators
            truncated_length = cls.MAX_NAME_LENGTH - (len(cls.PREFIX) + len(suffix) + 2)
            truncated_item_name = doc.item_code[:truncated_length]
            # if a partial word is found after truncate, remove the extra characters
            truncated_item_name = truncated_item_name.rsplit(" ", 1)[0]
            name = f"{cls.PREFIX}-{truncated_item_name}-{suffix}"

        if frappe.db.exists("Multilevel BOM Creator", name):
            existing_creators = frappe.get_all(
                "Multilevel BOM Creator", filters={"name": ("like", search_key), "amended_from": ["is", "not set"]}, pluck="name"
            )

            index = cls.get_index_for_bom(existing_creators)
            suffix = "%.3i" % index
            name = f"{cls.PREFIX}-{doc.item_code}-{suffix}"

        return name
    
    @classmethod
    def get_index_for_bom(cls, existing_creators):
        index = 1
        if existing_creators:
            index = MultilevelBOMCreatorNameGenerator.get_next_version_index(existing_creators)
        return index
    
    @staticmethod
    def get_next_version_index(existing_creators: list[str]) -> int:
        # split by "/" and "-"
        delimiters = ["/", "-"]
        pattern = "|".join(map(re.escape, delimiters))
        creator_parts = [re.split(pattern, creator_name)
                       for creator_name in existing_creators]

        # filter out BOMs that do not follow the following formats: BOM/ITEM/001, BOM-ITEM-001
        valid_creator_parts = list(
            filter(lambda x: len(x) > 1 and x[-1], creator_parts))

        # extract the current index from the BOM parts
        if valid_creator_parts:
            # handle cancelled and submitted documents
            indexes = [cint(part[-1]) for part in valid_creator_parts]
            index = max(indexes) + 1
        else:
            index = 1

        return index