import pytest

from polish_retail_bonds import bonds

from . import bond_test_utils


@pytest.mark.parametrize(
    "expected",
    bond_test_utils.load_test_cases("tos.csv"),
    ids=bond_test_utils.bond_id,
)
def test_tos_values(expected: bonds.Bond) -> None:
    actual = bonds.create_tos_bond(
        series_name=expected.series_name,
        isin=expected.isin,
        sale_from=expected.sale_from,
        sale_to=expected.sale_to,
        interest_rate=expected.interest_rate,
    )
    # ignore "expected" early redemption cost since test data doesn't have this info
    expected.early_redemption_cost = actual.early_redemption_cost

    assert actual == expected
    bond_test_utils.assert_common_bond_traits(actual)
    bond_test_utils.assert_compound_interest_bond_traits(actual)


@pytest.mark.parametrize(
    "expected",
    bond_test_utils.load_test_cases("coi.csv"),
    ids=bond_test_utils.bond_id,
)
def test_coi_values(expected: bonds.Bond) -> None:
    actual = bonds.create_coi_bond(
        series_name=expected.series_name,
        isin=expected.isin,
        sale_from=expected.sale_from,
        sale_to=expected.sale_to,
        interest_rate=expected.interest_rate,
    )
    # ignore "expected" early redemption cost since test data doesn't have this info
    expected.early_redemption_cost = actual.early_redemption_cost

    assert actual == expected
    bond_test_utils.assert_common_bond_traits(actual)
    bond_test_utils.assert_simple_interest_bond_traits(actual)


@pytest.mark.parametrize(
    "expected",
    bond_test_utils.load_test_cases("edo.csv"),
    ids=bond_test_utils.bond_id,
)
def test_edo_values(expected: bonds.Bond) -> None:
    actual = bonds.create_edo_bond(
        series_name=expected.series_name,
        isin=expected.isin,
        sale_from=expected.sale_from,
        sale_to=expected.sale_to,
        interest_rate=expected.interest_rate,
    )
    # ignore "expected" early redemption cost since test data doesn't have this info
    expected.early_redemption_cost = actual.early_redemption_cost

    assert actual == expected
    bond_test_utils.assert_common_bond_traits(actual)
    bond_test_utils.assert_compound_interest_bond_traits(actual)
