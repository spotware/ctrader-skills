# /// script
# requires-python = ">=3.11"
# ///

"""Convert cTrader volumes, quotes and money between the values the servers use and the values a trader reads.

The Remote server sends quotes as integers in 1/100000 of the price, takes volumes in 1/100 of the base asset and sends
money as integers in minor units. The Local server takes volumes as decimals in lots or in units. Every value here is an
exact decimal: nothing is floored, rounded to a step or clipped to a limit.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections.abc import Callable
from collections.abc import Mapping
from contextlib import redirect_stderr
from contextlib import redirect_stdout
from decimal import ROUND_CEILING
from decimal import ROUND_FLOOR
from decimal import Decimal
from decimal import InvalidOperation
from decimal import getcontext
from typing import NoReturn
from typing import TypeAlias

getcontext().prec = 28

EXIT_OK = 0
EXIT_INVALID_ARGS = 2
EXIT_NUMERIC_ERROR = 3

Answer: TypeAlias = dict[str, object]
"""The object a subcommand prints."""

SelfTestCase: TypeAlias = (
    tuple[str, list[str], Mapping[str, object], int] | tuple[str, list[str], Mapping[str, object], int, Mapping[str, object]]
)
"""One case of the case table: label, arguments, expected values, exit code and, optionally, checks."""

SELF_TEST_CASES: tuple[SelfTestCase, ...] = (
    (
        'quote-to-price divides by 100000 whatever the digits: the served example 15731000 is 157.31',
        ['quote-to-price', '--values', '15731000'],
        {'prices': [157.31]},
        0,
    ),
    (
        "quote-to-price gives each value in order, whatever the symbol's digits",
        ['quote-to-price', '--values', '15883700', '358825000', '6198159000', '714790000', '109610'],
        {'prices': [158.837, 3588.25, 61981.59, 7147.9, 1.0961]},
        0,
    ),
    (
        'quote-to-price reads the bid and the ask of two quote rows of one minute',
        ['quote-to-price', '--values', '362128000', '362143000', '109729', '109731'],
        {'prices': [3621.28, 3621.43, 1.09729, 1.09731]},
        0,
    ),
    (
        'quote-to-price takes the integers of a quote and refuses a display price',
        ['quote-to-price', '--values', '157.31'],
        {},
        2,
    ),
    (
        'lots-to-cents: 0.01 lot at lot size 100 is a volume of 100',
        ['lots-to-cents', '--lots', '0.01', '--lot-size', '100'],
        {'cents': 100},
        0,
    ),
    (
        'lots-to-cents: 1 lot at lot size 100000 is a volume of 10000000',
        ['lots-to-cents', '--lots', '1', '--lot-size', '100000'],
        {'cents': 10000000},
        0,
    ),
    (
        'lots-to-cents: 1 lot at lot size 1 is a volume of 100',
        ['lots-to-cents', '--lots', '1', '--lot-size', '1'],
        {'cents': 100},
        0,
    ),
    (
        'lots-to-cents keeps a fraction and never rounds down: 0.015 lot at lot size 1 is 1.5',
        ['lots-to-cents', '--lots', '0.015', '--lot-size', '1'],
        {'cents': 1.5},
        0,
    ),
    (
        'lots-to-cents refuses a size that is not above 0',
        ['lots-to-cents', '--lots', '-1', '--lot-size', '100'],
        {'error': '--lots must be above 0, got -1'},
        2,
    ),
    (
        'lots-to-cents refuses a size that is not finite',
        ['lots-to-cents', '--lots', 'inf', '--lot-size', '100'],
        {'error': '--lots must be finite'},
        3,
    ),
    (
        'lots-to-cents needs the lot size',
        ['lots-to-cents', '--lots', '0.01'],
        {},
        2,
    ),
    (
        'lots-to-cents refuses a size that is not a number, with the usage on stderr only',
        ['lots-to-cents', '--lots', 'abc', '--lot-size', '100'],
        {},
        2,
        {'absent': ['error']},
    ),
    (
        'lots-to-units keeps decimals: 0.01 lot at lot size 1 is 0.01 unit',
        ['lots-to-units', '--lots', '0.01', '--lot-size', '1'],
        {'units': 0.01},
        0,
    ),
    (
        'lots-to-units: 0.02 lot at lot size 100000 is 2000 units',
        ['lots-to-units', '--lots', '0.02', '--lot-size', '100000'],
        {'units': 2000},
        0,
    ),
    (
        'units-to-lots takes decimal units: 0.01 unit at lot size 1 is 0.01 lot',
        ['units-to-lots', '--units', '0.01', '--lot-size', '1'],
        {'lots': 0.01},
        0,
    ),
    (
        'units-to-lots: 2000 units at lot size 100000 are 0.02 lot',
        ['units-to-lots', '--units', '2000', '--lot-size', '100000'],
        {'lots': 0.02},
        0,
    ),
    (
        'check-volume names the grid sizes on either side of 0.015 lot, with minimum 1000, maximum 10000000, step 1000',
        [
            'check-volume', '--lots', '0.015', '--lot-size', '100000',
            '--min-volume', '1000', '--max-volume', '10000000', '--volume-step', '1000',
        ],
        {
            'units': 1500,
            'lots': 0.015,
            'on_grid': False,
            'within_limits': True,
            'below': {'units': 1000, 'lots': 0.01},
            'above': {'units': 2000, 'lots': 0.02},
        },
        0,
    ),
    (
        'check-volume reports 1000.5 units against a step of 1000 and rounds nothing',
        [
            'check-volume', '--units', '1000.5', '--lot-size', '100000',
            '--min-volume', '1000', '--max-volume', '10000000', '--volume-step', '1000',
        ],
        {
            'units': 1000.5,
            'on_grid': False,
            'within_limits': True,
            'below': {'units': 1000, 'lots': 0.01},
            'above': {'units': 2000, 'lots': 0.02},
        },
        0,
    ),
    (
        'check-volume: 0.02 lot lies on the grid, so it names no other size',
        [
            'check-volume', '--lots', '0.02', '--lot-size', '100000',
            '--min-volume', '1000', '--max-volume', '10000000', '--volume-step', '1000',
        ],
        {'units': 2000, 'lots': 0.02, 'on_grid': True, 'within_limits': True, 'below': None, 'above': None},
        0,
    ),
    (
        'check-volume: 100 units lie below the minimum, so no grid size lies below them',
        [
            'check-volume', '--units', '100', '--lot-size', '100000',
            '--min-volume', '1000', '--max-volume', '10000000', '--volume-step', '1000',
        ],
        {'units': 100, 'on_grid': False, 'within_limits': False, 'below': None, 'above': {'units': 1000, 'lots': 0.01}},
        0,
    ),
    (
        'check-volume: above 150 units on a step of 100 it names the minimum of 1000, the nearest size within the limits',
        [
            'check-volume', '--units', '150', '--lot-size', '100000',
            '--min-volume', '1000', '--max-volume', '10000000', '--volume-step', '100',
        ],
        {'on_grid': False, 'within_limits': False, 'below': None, 'above': {'units': 1000, 'lots': 0.01}},
        0,
    ),
    (
        'check-volume keeps steps below one unit: 0.05 unit lies on a step of 0.01 at lot size 1',
        [
            'check-volume', '--units', '0.05', '--lot-size', '1',
            '--min-volume', '0.01', '--max-volume', '50', '--volume-step', '0.01',
        ],
        {'units': 0.05, 'lots': 0.05, 'on_grid': True, 'within_limits': True, 'below': None, 'above': None},
        0,
    ),
    (
        'check-volume: 51 units lie on the grid and above the maximum of 50',
        [
            'check-volume', '--units', '51', '--lot-size', '1',
            '--min-volume', '0.01', '--max-volume', '50', '--volume-step', '0.01',
        ],
        {'units': 51, 'on_grid': True, 'within_limits': False, 'below': None, 'above': None},
        0,
    ),
    (
        'check-volume: 50.555 units name the maximum below them and no size above',
        [
            'check-volume', '--units', '50.555', '--lot-size', '1',
            '--min-volume', '0.01', '--max-volume', '50', '--volume-step', '0.01',
        ],
        {'units': 50.555, 'on_grid': False, 'within_limits': False, 'below': {'units': 50, 'lots': 50}, 'above': None},
        0,
    ),
    (
        'check-volume takes a size in lots or in units, not both',
        [
            'check-volume', '--lots', '0.01', '--units', '1000', '--lot-size', '100000',
            '--min-volume', '1000', '--max-volume', '10000000', '--volume-step', '1000',
        ],
        {},
        2,
    ),
    (
        'check-volume refuses a minimum below 0',
        [
            'check-volume', '--units', '1', '--lot-size', '1',
            '--min-volume', '-1', '--max-volume', '50', '--volume-step', '0.01',
        ],
        {'error': '--min-volume must be 0 or more, got -1'},
        2,
    ),
    (
        'check-volume refuses a maximum below the minimum',
        [
            'check-volume', '--units', '1000', '--lot-size', '100000',
            '--min-volume', '2000', '--max-volume', '1000', '--volume-step', '1000',
        ],
        {'error': '--max-volume must not be below --min-volume'},
        2,
    ),
    (
        'display-money divides by 10^moneyDigits: a made-up balance of 12345678 at 2 digits is 123456.78',
        ['display-money', '--raw', '12345678', '--money-digits', '2'],
        {'display': 123456.78},
        0,
    ),
    (
        'display-money at 8 digits, as on crypto-denominated accounts: 150000000 is 1.5',
        ['display-money', '--raw', '150000000', '--money-digits', '8'],
        {'display': 1.5},
        0,
    ),
    (
        'display-money keeps the sign of a loss: -90 at 2 digits is -0.9',
        ['display-money', '--raw', '-90', '--money-digits', '2'],
        {'display': -0.9},
        0,
    ),
    (
        'display-money refuses negative moneyDigits',
        ['display-money', '--raw', '1', '--money-digits', '-1'],
        {'error': '--money-digits must be 0 or more, got -1'},
        2,
    ),
    (
        'a call without a subcommand prints the help on stderr and exits 2',
        [],
        {},
        2,
        {'absent': ['error']},
    ),
)
"""Every behavior the script promises, one case each; ``--self-test`` runs them."""

DEFAULT_TOLERANCE = 1e-9
"""The absolute tolerance of a case's numbers where the case names none."""


def quote_to_price(value: int) -> Decimal:
    """Return the display price of a Remote quote integer.

    Args:
        value: An integer of ``get_spot_prices`` or ``get_trendbars``, in 1/100000 of the price for every symbol.

    Returns:
        The price.
    """
    return Decimal(value).scaleb(-5)


def lots_to_units(lots: Decimal, lot_size: Decimal) -> Decimal:
    """Return a size in lots in units of the base asset.

    Args:
        lots: The size in lots.
        lot_size: The units in one lot.

    Returns:
        The exact product of the two.
    """
    return lots * lot_size


def lots_to_cents(lots: Decimal, lot_size: Decimal) -> Decimal:
    """Return a size in lots as a Remote volume, in 1/100 of the base asset.

    Args:
        lots: The size in lots.
        lot_size: The units in one lot.

    Returns:
        The exact product ``lots x lot size x 100``.
    """
    return lots * lot_size * 100


def units_to_lots(units: Decimal, lot_size: Decimal) -> Decimal:
    """Return a size in units of the base asset in lots.

    Args:
        units: The size in units.
        lot_size: The units in one lot.

    Returns:
        The quotient of the two.
    """
    return units / lot_size


def display_money(raw: int, money_digits: int) -> Decimal:
    """Return the amount a Remote money integer stands for.

    Args:
        raw: The integer, in minor units of the deposit currency.
        money_digits: The ``moneyDigits`` that goes with it.

    Returns:
        ``raw / 10^moneyDigits``.
    """
    return Decimal(raw).scaleb(-money_digits)


def grid_neighbors(
    units: Decimal, minimum: Decimal, maximum: Decimal, step: Decimal
) -> tuple[Decimal | None, Decimal | None]:
    """Return the nearest sizes below and above a size that are whole multiples of the step within the limits.

    Args:
        units: The size, in units.
        minimum: The smallest size allowed, in units.
        maximum: The largest size allowed, in units.
        step: The step every size is a whole multiple of, in units.

    Returns:
        The largest such size below ``units`` and the smallest above it, each ``None`` when the limits hold none.
    """
    lowest = (minimum / step).to_integral_value(rounding=ROUND_CEILING)
    highest = (maximum / step).to_integral_value(rounding=ROUND_FLOOR)
    below = min((units / step).to_integral_value(rounding=ROUND_FLOOR), highest)
    above = max((units / step).to_integral_value(rounding=ROUND_CEILING), lowest)
    return (below * step if below >= lowest else None), (above * step if above <= highest else None)


def check_volume(units: Decimal, lot_size: Decimal, minimum: Decimal, maximum: Decimal, step: Decimal) -> Answer:
    """Check a size against the volume grid of a symbol, changing nothing.

    Args:
        units: The size, in units.
        lot_size: The units in one lot.
        minimum: The smallest size allowed, in units.
        maximum: The largest size allowed, in units.
        step: The step every size is a whole multiple of, in units.

    Returns:
        The size in units and lots, whether it is a whole multiple of the step, whether it lies within the limits, and
        for a size off the grid the nearest grid sizes within the limits below and above it, in units and lots.
    """
    on_grid = units % step == 0
    below, above = (None, None) if on_grid else grid_neighbors(units, minimum, maximum, step)
    return {
        'units': units,
        'lots': units / lot_size,
        'on_grid': on_grid,
        'within_limits': minimum <= units <= maximum,
        'below': None if below is None else {'units': below, 'lots': below / lot_size},
        'above': None if above is None else {'units': above, 'lots': above / lot_size},
    }


def _plain(number: Decimal) -> str:
    """Write a number in plain decimal notation.

    Args:
        number: The number.

    Returns:
        Its digits without an exponent: a whole value without a fraction, any other value without a trailing zero.
    """
    text = format(number.normalize(), 'f')
    return '0' if text == '-0' else text


def _json(value: object) -> str:
    """Write a value of an answer as JSON, every number in plain decimal notation.

    Args:
        value: The value: an object, a list, a decimal, an integer, a boolean, a string or ``None``.

    Returns:
        The JSON text, ASCII only, with no space after a separator.
    """
    if isinstance(value, dict):
        return '{' + ','.join(f'{json.dumps(key)}:{_json(item)}' for key, item in value.items()) + '}'
    if isinstance(value, list):
        return '[' + ','.join(_json(item) for item in value) + ']'
    if isinstance(value, Decimal):
        return _plain(value)
    return json.dumps(value, ensure_ascii=True)


def _emit_json(payload: Answer) -> None:
    """Write an answer to stdout as one line of JSON.

    Args:
        payload: The answer.
    """
    sys.stdout.write(_json(payload) + '\n')
    sys.stdout.flush()


def _emit_error(message: str, *, exit_code: int) -> NoReturn:
    """Report a refusal on stderr and as a JSON object on stdout, and exit.

    Args:
        message: The reason.
        exit_code: The exit code.

    Raises:
        SystemExit: Always, with the exit code.
    """
    print(f'error: {message}', file=sys.stderr)
    sys.stdout.write(json.dumps({'error': message}, separators=(',', ':'), ensure_ascii=True) + '\n')
    sys.stdout.flush()
    raise SystemExit(exit_code)


def _number(text: str) -> Decimal:
    """Read a number of the command line as an exact decimal.

    Args:
        text: The text of the argument.

    Returns:
        The number.

    Raises:
        argparse.ArgumentTypeError: When the text is not a number.
    """
    try:
        return Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f'not a number: {text!r}') from None


def _finite(value: Decimal, flag: str) -> Decimal:
    """Refuse a value that is not finite.

    Args:
        value: The value.
        flag: The flag that gave it.

    Returns:
        The value.
    """
    if not value.is_finite():
        _emit_error(f'{flag} must be finite', exit_code=EXIT_NUMERIC_ERROR)
    return value


def _positive(value: Decimal, flag: str) -> Decimal:
    """Refuse a value that is not finite or not above 0.

    Args:
        value: The value.
        flag: The flag that gave it.

    Returns:
        The value.
    """
    if _finite(value, flag) <= 0:
        _emit_error(f'{flag} must be above 0, got {_plain(value)}', exit_code=EXIT_INVALID_ARGS)
    return value


def _handle_quote_to_price(args: argparse.Namespace) -> Answer:
    """Answer ``quote-to-price``.

    Args:
        args: The parsed arguments.

    Returns:
        The display prices, in the order of the values.
    """
    return {'prices': [quote_to_price(value) for value in args.values]}


def _handle_lots_to_cents(args: argparse.Namespace) -> Answer:
    """Answer ``lots-to-cents``.

    Args:
        args: The parsed arguments.

    Returns:
        The Remote volume.
    """
    return {'cents': lots_to_cents(_positive(args.lots, '--lots'), _positive(args.lot_size, '--lot-size'))}


def _handle_lots_to_units(args: argparse.Namespace) -> Answer:
    """Answer ``lots-to-units``.

    Args:
        args: The parsed arguments.

    Returns:
        The size in units.
    """
    return {'units': lots_to_units(_positive(args.lots, '--lots'), _positive(args.lot_size, '--lot-size'))}


def _handle_units_to_lots(args: argparse.Namespace) -> Answer:
    """Answer ``units-to-lots``.

    Args:
        args: The parsed arguments.

    Returns:
        The size in lots.
    """
    return {'lots': units_to_lots(_positive(args.units, '--units'), _positive(args.lot_size, '--lot-size'))}


def _handle_check_volume(args: argparse.Namespace) -> Answer:
    """Answer ``check-volume``.

    Args:
        args: The parsed arguments.

    Returns:
        The size, where it lies on the grid, and the nearest grid sizes around a size off the grid.
    """
    lot_size = _positive(args.lot_size, '--lot-size')
    if args.lots is not None:
        units = lots_to_units(_positive(args.lots, '--lots'), lot_size)
    else:
        units = _positive(args.units, '--units')
    minimum = _finite(args.min_volume, '--min-volume')
    if minimum < 0:
        _emit_error(f'--min-volume must be 0 or more, got {_plain(minimum)}', exit_code=EXIT_INVALID_ARGS)
    maximum = _positive(args.max_volume, '--max-volume')
    if maximum < minimum:
        _emit_error('--max-volume must not be below --min-volume', exit_code=EXIT_INVALID_ARGS)
    return check_volume(units, lot_size, minimum, maximum, _positive(args.volume_step, '--volume-step'))


def _handle_display_money(args: argparse.Namespace) -> Answer:
    """Answer ``display-money``.

    Args:
        args: The parsed arguments.

    Returns:
        The amount.
    """
    if args.money_digits < 0:
        _emit_error(f'--money-digits must be 0 or more, got {args.money_digits}', exit_code=EXIT_INVALID_ARGS)
    return {'display': display_money(args.raw, args.money_digits)}


LOT_SIZE_HELP = (
    'Lot size of the symbol, in units: lotSize of get_symbol_details on the Local server. '
    'The Remote server serves none, so take it as the skill describes.'
)

EPILOG = """\
Run it as python3 <skill folder>/scripts/units_encoding.py on macOS and Linux, and as
python <skill folder>/scripts/units_encoding.py on Windows (py in place of python where python is not on the path).

Examples:
  python3 <skill folder>/scripts/units_encoding.py quote-to-price --values 15731000
  python3 <skill folder>/scripts/units_encoding.py lots-to-cents --lots 0.01 --lot-size 100
  python3 <skill folder>/scripts/units_encoding.py lots-to-units --lots 0.01 --lot-size 1
  python3 <skill folder>/scripts/units_encoding.py units-to-lots --units 2000 --lot-size 100000
  python3 <skill folder>/scripts/units_encoding.py check-volume --units 0.015 --lot-size 1 \\
      --min-volume 0.01 --max-volume 50 --volume-step 0.01
  python3 <skill folder>/scripts/units_encoding.py display-money --raw -90 --money-digits 2
  python3 <skill folder>/scripts/units_encoding.py --self-test

Remote server: the quotes of get_spot_prices and get_trendbars are integers in 1/100000 of the price, whatever the
symbol's digits; a volume is in 1/100 of the base asset (lots x lot size x 100); money is an integer in minor units
of the deposit currency, with its moneyDigits. The server serves no lot size: take it as the skill describes.

Local server: a volume is a decimal sent with volumeType "lots" or "units" (units = lots x lot size); lotSize,
minVolume, maxVolume and volumeStep come from get_symbol_details, the last three in units; money is already a decimal
in the account currency and needs no conversion.

Every answer is one line of JSON on stdout. A refusal writes "error: <reason>" on stderr and {"error": "<reason>"} on
stdout. Exit codes: 0 success, 2 invalid input, 3 a value that is not finite. --self-test runs the script's own cases
and exits 0 when every case holds, 1 otherwise.
"""


def _build_parser() -> argparse.ArgumentParser:
    """Build the parser of the command line.

    Returns:
        The parser, with one subparser per subcommand.
    """
    parser = argparse.ArgumentParser(
        prog='units_encoding.py',
        description='Convert cTrader volumes, quotes and money between server values and the values a trader reads.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument('--self-test', action='store_true', help="Run the script's own cases; exit 0 when all hold.")
    subparsers = parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND')

    quotes = subparsers.add_parser('quote-to-price', help='Display prices of Remote quote integers: value / 100000.')
    quotes.add_argument(
        '--values', nargs='+', type=int, required=True, help='Integers of get_spot_prices or get_trendbars (Remote).'
    )
    quotes.set_defaults(handler=_handle_quote_to_price)

    cents = subparsers.add_parser('lots-to-cents', help='Remote volume of a size in lots: lots x lot size x 100.')
    cents.add_argument('--lots', type=_number, required=True, help='The size in lots.')
    cents.add_argument('--lot-size', type=_number, required=True, help=LOT_SIZE_HELP)
    cents.set_defaults(handler=_handle_lots_to_cents)

    units = subparsers.add_parser(
        'lots-to-units',
        help='Size in units of a size in lots: lots x lot size, the volume for volumeType "units" on the Local server; '
        'the lots themselves go with volumeType "lots".',
    )
    units.add_argument('--lots', type=_number, required=True, help='The size in lots.')
    units.add_argument('--lot-size', type=_number, required=True, help=LOT_SIZE_HELP)
    units.set_defaults(handler=_handle_lots_to_units)

    lots = subparsers.add_parser('units-to-lots', help='Size in lots of a size in units: units / lot size.')
    lots.add_argument('--units', type=_number, required=True, help='The size in units; decimals are allowed.')
    lots.add_argument('--lot-size', type=_number, required=True, help=LOT_SIZE_HELP)
    lots.set_defaults(handler=_handle_units_to_lots)

    grid = subparsers.add_parser(
        'check-volume',
        help='Check a size against minVolume, maxVolume and volumeStep of get_symbol_details. It reports and changes '
        'nothing: ask the user for a size off the grid or outside the limits.',
    )
    size = grid.add_mutually_exclusive_group(required=True)
    size.add_argument('--lots', type=_number, help='The size in lots.')
    size.add_argument('--units', type=_number, help='The size in units.')
    grid.add_argument('--lot-size', type=_number, required=True, help=LOT_SIZE_HELP)
    grid.add_argument('--min-volume', type=_number, required=True, help='minVolume of get_symbol_details, in units.')
    grid.add_argument('--max-volume', type=_number, required=True, help='maxVolume of get_symbol_details, in units.')
    grid.add_argument('--volume-step', type=_number, required=True, help='volumeStep of get_symbol_details, in units.')
    grid.set_defaults(handler=_handle_check_volume)

    money = subparsers.add_parser(
        'display-money', help='Amount of a Remote money integer: raw / 10^moneyDigits. Local money needs no conversion.'
    )
    money.add_argument('--raw', type=int, required=True, help='The money integer, in minor units.')
    money.add_argument(
        '--money-digits',
        type=int,
        required=True,
        help='moneyDigits of the same object (a position, a closePositionDetail, the deal of a close_position answer), '
        'else that of get_balance, as for a row of get_deals, which carries none at its top level.',
    )
    money.set_defaults(handler=_handle_display_money)
    return parser


def _self_test() -> int:
    """Run every case of the case table through ``main`` and name each case that fails on stderr.

    Returns:
        0 when every case holds, 1 otherwise.
    """
    failed = 0
    for case in SELF_TEST_CASES:
        label, argv, expected, exit_code = case[:4]
        checks = case[4] if len(case) == 5 else {}
        status, answer = _run_case(argv)
        problems = _case_problems(expected, exit_code, checks, status, answer)
        if problems:
            failed += 1
            detail = '; '.join(problems)
            print(f'FAIL: {label}: {detail}', file=sys.stderr)
    if failed:
        print(f'{failed} of {len(SELF_TEST_CASES)} cases failed', file=sys.stderr)
        return 1
    print(f'all {len(SELF_TEST_CASES)} cases passed', file=sys.stderr)
    return EXIT_OK


def _run_case(argv: list[str]) -> tuple[int, dict[str, object] | None]:
    """Run ``main`` on the arguments of a case with both output streams captured.

    Args:
        argv: The arguments of the case.

    Returns:
        The exit status of the call, and the object it printed or ``None`` when standard output is not one line: every
        line the script prints on standard output is one JSON object, and its help is more than one line.
    """
    printed = io.StringIO()
    with redirect_stdout(printed), redirect_stderr(io.StringIO()):
        try:
            status = main(list(argv))
        except SystemExit as stop:
            status = stop.code if isinstance(stop.code, int) else int(stop.code is not None)
    lines = printed.getvalue().splitlines()
    answer = json.loads(lines[0]) if len(lines) == 1 else None
    return status, answer if isinstance(answer, dict) else None


def _case_problems(
    expected: Mapping[str, object],
    exit_code: int,
    checks: Mapping[str, object],
    status: int,
    answer: dict[str, object] | None,
) -> list[str]:
    """Compare the outcome of a call with the case that promises it.

    Args:
        expected: The values the case expects under the keys it lists; a key it does not list is not compared.
        exit_code: The exit code the case expects.
        checks: The tolerance of the case's numbers, the keys the answer must not hold, both or neither.
        status: The exit status of the call.
        answer: The object the call printed, or ``None`` when it printed none.

    Returns:
        One description per difference; empty when the outcome keeps the case.
    """
    problems = [] if status == exit_code else [f'exit code {status}, expected {exit_code}']
    if answer is None:
        return [*problems, 'printed no JSON object'] if expected else problems
    tolerance = checks.get('tolerance', DEFAULT_TOLERANCE)
    absent = checks.get('absent', [])
    keys = absent if isinstance(absent, list) else []
    limit = float(tolerance) if isinstance(tolerance, int | float) else DEFAULT_TOLERANCE
    problems.extend(_mismatches(expected, answer, '', limit))
    problems.extend(f'{key}: printed, expected absent' for key in keys if key in answer)
    return problems


def _mismatches(expected: object, printed: object, path: str, tolerance: float) -> list[str]:
    """Compare a printed value with the value a case expects at the same key path.

    A number matches a number within the tolerance, ``None`` matches JSON null and nothing else, a boolean or a string
    matches only the same value of its own type, an object is compared on the keys the case lists, and an array element
    by element at equal length, each by the same rule.

    Args:
        expected: The value the case expects.
        printed: The value the call printed.
        path: The key path of the value, empty for the printed object itself.
        tolerance: The absolute tolerance of numbers.

    Returns:
        One description per difference.
    """
    where = path or 'answer'
    difference = [f'{where}: expected {expected!r}, got {printed!r}']
    if isinstance(expected, dict):
        if not isinstance(printed, dict):
            return difference
        problems: list[str] = []
        for key, value in expected.items():
            key_path = f'{path}.{key}' if path else str(key)
            if key in printed:
                problems.extend(_mismatches(value, printed[key], key_path, tolerance))
            else:
                problems.append(f'{key_path}: missing')
        return problems
    if isinstance(expected, list | tuple):
        if not isinstance(printed, list) or len(printed) != len(expected):
            return difference
        return [
            problem
            for index, (value, item) in enumerate(zip(expected, printed, strict=True))
            for problem in _mismatches(value, item, f'{where}[{index}]', tolerance)
        ]
    if isinstance(expected, int | float) and not isinstance(expected, bool):
        if isinstance(printed, bool) or not isinstance(printed, int | float):
            return difference
        return [] if abs(printed - expected) <= tolerance else difference
    return [] if type(printed) is type(expected) and printed == expected else difference


def main(argv: list[str] | None = None) -> int:
    """Run the command line.

    Args:
        argv: The arguments, or ``None`` for those of the process.

    Returns:
        The exit code.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        return _self_test()
    if args.subcommand is None:
        parser.print_help(sys.stderr)
        return EXIT_INVALID_ARGS
    handler: Callable[[argparse.Namespace], Answer] = args.handler
    _emit_json(handler(args))
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
