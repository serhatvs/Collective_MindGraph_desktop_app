import importlib

from collective_mindgraph.architecture import DOMAIN_CONTRACTS, SPREADSHEET_SECTIONS


def test_v2_domains_match_spreadsheet_sections_in_order():
    assert SPREADSHEET_SECTIONS == (
        "AI Meeting Assistant",
        "Knowledge Management Tool",
        "Productivity Tool",
        "Enterprise Software",
        "Collaboration Tool",
        "Smart Assistant",
    )


def test_v2_submodule_counts_match_spreadsheet_hierarchy():
    assert [len(contract.submodules) for contract in DOMAIN_CONTRACTS] == [6, 4, 3, 4, 5, 12]


def test_v2_domain_and_submodule_packages_are_importable():
    for contract in DOMAIN_CONTRACTS:
        importlib.import_module(contract.package)
        for submodule in contract.submodules:
            importlib.import_module(submodule.package)


def test_v2_contracts_do_not_allow_forbidden_dependencies():
    for contract in DOMAIN_CONTRACTS:
        assert set(contract.allowed_dependencies).isdisjoint(contract.forbidden_dependencies)
