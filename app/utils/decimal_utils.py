"""Decimal arithmetic helpers"""

from decimal import ROUND_HALF_UP, Decimal


def round_decimal(value: Decimal, decimal_places: int = 2) -> Decimal:
    """
    Round a decimal value to specified decimal places.

    Args:
        value: Decimal value to round
        decimal_places: Number of decimal places (default 2)

    Returns:
        Rounded decimal value
    """
    quantize_value = Decimal(10) ** -decimal_places
    return value.quantize(quantize_value, rounding=ROUND_HALF_UP)


def sum_decimals(values: list[Decimal]) -> Decimal:
    """
    Sum a list of decimal values.

    Args:
        values: List of decimal values

    Returns:
        Sum of all values
    """
    return sum(values, Decimal("0"))
