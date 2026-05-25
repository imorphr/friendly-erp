from friendly_erp.setup.workspace import add_multilevel_bom_creator_to_manufacturing_workspace


def after_install():
    add_multilevel_bom_creator_to_manufacturing_workspace()