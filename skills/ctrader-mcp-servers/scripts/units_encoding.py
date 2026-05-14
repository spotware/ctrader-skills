# /// script
# requires-python = ">=3.12"
# ///

"""Convert between cTrader display units and server wire encodings.

Display units (lots, prices, money) <-> server wire encodings
(units, cents, pipettes, moneyDigits integers).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from decimal import ROUND_DOWN
from decimal import ROUND_HALF_UP
from decimal import Decimal
from decimal import getcontext
from typing import Any
from typing import NoReturn

getcontext().prec = 28

EXIT_OK = 0
EXIT_INVALID_ARGS = 2
EXIT_NUMERIC_ERROR = 3
EXIT_LOGIC_ERROR = 4


def _emit_json(payload: dict[str, Any]) -> None:
    """Write a JSON payload to stdout, terminated by newline.

    Args:
        payload: Dict to serialize as JSON.
    """
    json.dump(payload, sys.stdout, separators=(',', ':'), ensure_ascii=True)
    sys.stdout.write('\n')
    sys.stdout.flush()


def _emit_error(message: str, *, exit_code: int) -> NoReturn:
    """Emit a diagnostic to stderr, an error JSON to stdout, and exit.

    Args:
        message: Human-readable description of the failure.
        exit_code: Process exit code (non-zero).
    """
    print(f'error: {message}', file=sys.stderr)
    json.dump({'error': message}, sys.stdout, separators=(',', ':'), ensure_ascii=True)
    sys.stdout.write('\n')
    sys.stdout.flush()
    sys.exit(exit_code)


def lots_to_units(lots: Decimal, lot_size: Decimal) -> int:
    """Convert display lots to integer base-asset units (Local server encoding).

    Args:
        lots: Display lots (positive).
        lot_size: Base-asset units per lot (e.g., 100000 for forex, 100 for XAUUSD).

    Returns:
        units = floor(lots * lot_size). Floor is used because partial units are
        not representable on the wire.
    """
    raw = lots * lot_size
    return int(raw.quantize(Decimal(1), rounding=ROUND_DOWN))


def units_to_lots(units: int, lot_size: Decimal) -> Decimal:
    """Convert integer base-asset units to display lots.

    Args:
        units: Base-asset units (positive integer).
        lot_size: Base-asset units per lot.

    Returns:
        Display lots as Decimal.

    Raises:
        ValueError: If ``lot_size`` is not strictly positive.
    """
    if lot_size <= 0:
        raise ValueError(f'lot_size must be > 0, got {lot_size}')
    return Decimal(units) / lot_size


def lots_to_cents(lots: Decimal, lot_size: Decimal) -> int:
    """Convert display lots to integer base-asset cents (Remote server encoding).

    Args:
        lots: Display lots (positive).
        lot_size: Base-asset units per lot.

    Returns:
        cents = floor(lots * lot_size * 100). Cents are one one-hundredth of a unit.
    """
    raw = lots * lot_size * Decimal(100)
    return int(raw.quantize(Decimal(1), rounding=ROUND_DOWN))


def cents_to_units(cents: int) -> int:
    """Convert Remote-server cents to Local-server units. cents = units * 100.

    Args:
        cents: Remote-server volume in cents.

    Returns:
        Equivalent Local-server volume in units (integer division by 100).
    """
    return cents // 100


def units_to_cents(units: int) -> int:
    """Convert Local-server units to Remote-server cents.

    Args:
        units: Local-server volume in units.

    Returns:
        Equivalent Remote-server volume in cents (units * 100).
    """
    return units * 100


def display_money(raw: int, money_digits: int) -> Decimal:
    """Decode a Remote-server money integer to a display value.

    Args:
        raw: Money integer from the wire.
        money_digits: Number of fractional digits (from response moneyDigits field).

    Returns:
        Display value: raw / 10^money_digits.

    Raises:
        ValueError: If ``money_digits`` is negative.
    """
    if money_digits < 0:
        raise ValueError(f'money_digits must be >= 0, got {money_digits}')
    divisor = Decimal(10) ** money_digits
    return Decimal(raw) / divisor


def parse_money(display: Decimal, money_digits: int) -> int:
    """Encode a display money value to a Remote-server money integer.

    Args:
        display: Display money value.
        money_digits: Number of fractional digits.

    Returns:
        raw = round(display * 10^money_digits) using ROUND_HALF_UP.

    Raises:
        ValueError: If ``money_digits`` is negative.
    """
    if money_digits < 0:
        raise ValueError(f'money_digits must be >= 0, got {money_digits}')
    multiplier = Decimal(10) ** money_digits
    return int((display * multiplier).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def pipettes_to_price(pipettes: int, pip_digits: int) -> Decimal:
    """Decode a Remote-server pipette integer to a display price.

    Args:
        pipettes: Pipette integer from the wire.
        pip_digits: Number of fractional digits in the display price.

    Returns:
        Display price: pipettes / 10^pip_digits.

    Raises:
        ValueError: If ``pip_digits`` is negative.
    """
    if pip_digits < 0:
        raise ValueError(f'pip_digits must be >= 0, got {pip_digits}')
    divisor = Decimal(10) ** pip_digits
    return Decimal(pipettes) / divisor


def price_to_pipettes(price: Decimal, pip_digits: int) -> int:
    """Encode a display price to a Remote-server pipette integer.

    Args:
        price: Display price (positive).
        pip_digits: Number of fractional digits.

    Returns:
        pipettes = round(price * 10^pip_digits) using ROUND_HALF_UP.

    Raises:
        ValueError: If ``pip_digits`` is negative.
    """
    if pip_digits < 0:
        raise ValueError(f'pip_digits must be >= 0, got {pip_digits}')
    multiplier = Decimal(10) ** pip_digits
    return int((price * multiplier).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _add_lot_args(parser: argparse.ArgumentParser, lots_required: bool = True) -> None:
    """Attach --lots and --lot-size arguments to a subparser.

    Args:
        parser: Subparser to mutate.
        lots_required: Whether --lots is required.

    --lot-size is ALWAYS REQUIRED: broker lot sizes vary (e.g., forex on Remote
    is typically 100000; ICMarkets Local returns lotSize=1 for EURUSD). Always
    read get_symbol_details(symbolName).lotSize before calling this script.
    See [Q-L1](../references/known-quirks.md#q-l1).
    """
    parser.add_argument('--lots', type=float, required=lots_required)
    parser.add_argument('--lot-size', type=float, required=True)


def _build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argparse.ArgumentParser with 10 subparsers."""
    parser = argparse.ArgumentParser(
        prog='units_encoding.py',
        description='Convert between display units and server wire encodings for cTrader.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Examples:\n'
            '  python units_encoding.py lots-to-units --lots 0.1 --lot-size 100000\n'
            '  python units_encoding.py lots-to-cents --lots 0.1 --lot-size 100000\n'
            '  python units_encoding.py units-to-lots --units 10000 --lot-size 100000\n'
            '  python units_encoding.py cents-to-units --cents 10000000\n'
            '  python units_encoding.py units-to-cents --units 100000\n'
            '  python units_encoding.py display-money --raw 1234567 --money-digits 2\n'
            '  python units_encoding.py parse-money --display 12345.67 --money-digits 2\n'
            '  python units_encoding.py parse-money --raw 1234567 --money-digits 2\n'
            '  python units_encoding.py money-to-units --money 12345.67 --money-digits 2\n'
            '  python units_encoding.py pipettes-to-price --pipettes 108500 --pip-digits 5\n'
            '  python units_encoding.py price-to-pipettes --price 1.0850 --pip-digits 5\n'
            '  python units_encoding.py --self-test\n'
            '\n'
            '--lot-size is REQUIRED on lots-to-units, lots-to-cents, units-to-lots.\n'
            'Broker lot sizes vary: forex on Remote is typically 100000;\n'
            'ICMarkets Local returns lotSize=1 for EURUSD. Always read\n'
            'get_symbol_details(symbolName).lotSize before calling this script.\n'
            'See known-quirks.md#q-l1.\n'
            '\n'
            'Exit codes:\n'
            '  0  success\n'
            '  2  invalid arguments (negative lots, negative money_digits, missing --lot-size, etc.)\n'
            '  3  numeric error\n'
        ),
    )
    parser.add_argument(
        '--self-test',
        action='store_true',
        help='Run built-in self-test cases and exit 0 if all pass.',
    )
    subparsers = parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND')

    p_lu = subparsers.add_parser(
        'lots-to-units',
        help='Lots -> Local server units (lots * lot_size).',
    )
    _add_lot_args(p_lu)

    p_lc = subparsers.add_parser(
        'lots-to-cents',
        help='Lots -> Remote server cents (lots * lot_size * 100).',
    )
    _add_lot_args(p_lc)

    p_ul = subparsers.add_parser(
        'units-to-lots',
        help='Local server units -> lots.',
    )
    p_ul.add_argument('--units', required=True, type=int)
    p_ul.add_argument('--lot-size', type=float, required=True)

    p_cu = subparsers.add_parser(
        'cents-to-units',
        help='Remote server cents -> Local server units (cents // 100).',
    )
    p_cu.add_argument('--cents', required=True, type=int)

    p_uc = subparsers.add_parser(
        'units-to-cents',
        help='Local server units -> Remote server cents (units * 100).',
    )
    p_uc.add_argument('--units', required=True, type=int)

    p_dm = subparsers.add_parser(
        'display-money',
        help='Remote server money integer -> display value (raw / 10^money_digits).',
    )
    p_dm.add_argument('--raw', required=True, type=int)
    p_dm.add_argument('--money-digits', required=True, type=int)

    p_pm = subparsers.add_parser(
        'parse-money',
        help='Display money -> Remote server money integer (or decode --raw inverse).',
    )
    p_pm.add_argument('--display', type=float)
    p_pm.add_argument('--raw', type=int)
    p_pm.add_argument('--money-digits', required=True, type=int)

    p_mu = subparsers.add_parser(
        'money-to-units',
        help="Display money -> Remote server money integer (alias output as 'units').",
    )
    p_mu.add_argument('--money', required=True, type=float)
    p_mu.add_argument('--money-digits', required=True, type=int)

    p_pp = subparsers.add_parser(
        'pipettes-to-price',
        help='Pipette integer -> display price (pipettes / 10^pip_digits).',
    )
    p_pp.add_argument('--pipettes', required=True, type=int)
    p_pp.add_argument('--pip-digits', required=True, type=int)

    p_pp2 = subparsers.add_parser(
        'price-to-pipettes',
        help='Display price -> pipette integer (round(price * 10^pip_digits)).',
    )
    p_pp2.add_argument('--price', required=True, type=float)
    p_pp2.add_argument('--pip-digits', required=True, type=int)

    return parser


def _decimal_from_positive_float(value: float, *, flag_name: str) -> Decimal:
    """Convert a float CLI flag to a Decimal, validating positivity and finiteness.

    Args:
        value: Float input.
        flag_name: CLI flag name for error reporting.

    Returns:
        Validated Decimal value.
    """
    if not math.isfinite(value):
        _emit_error(f'{flag_name} must be finite', exit_code=EXIT_NUMERIC_ERROR)
    if value <= 0:
        _emit_error(f'{flag_name} must be > 0, got {value}', exit_code=EXIT_INVALID_ARGS)
    return Decimal(str(value))


def _handle_lots_to_units(args: argparse.Namespace) -> dict[str, Any]:
    """Handler for `lots-to-units`.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    lots = _decimal_from_positive_float(args.lots, flag_name='--lots')
    lot_size = _decimal_from_positive_float(args.lot_size, flag_name='--lot-size')
    return {'units': lots_to_units(lots, lot_size)}


def _handle_lots_to_cents(args: argparse.Namespace) -> dict[str, Any]:
    """Handler for `lots-to-cents`.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    lots = _decimal_from_positive_float(args.lots, flag_name='--lots')
    lot_size = _decimal_from_positive_float(args.lot_size, flag_name='--lot-size')
    return {'cents': lots_to_cents(lots, lot_size)}


def _handle_units_to_lots(args: argparse.Namespace) -> dict[str, Any]:
    """Handler for `units-to-lots`.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    if args.units <= 0:
        _emit_error('--units must be > 0', exit_code=EXIT_INVALID_ARGS)
    lot_size = _decimal_from_positive_float(args.lot_size, flag_name='--lot-size')
    return {'lots': float(units_to_lots(args.units, lot_size))}


def _handle_cents_to_units(args: argparse.Namespace) -> dict[str, Any]:
    """Handler for `cents-to-units`.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    if args.cents <= 0:
        _emit_error('--cents must be > 0', exit_code=EXIT_INVALID_ARGS)
    return {'units': cents_to_units(args.cents)}


def _handle_units_to_cents(args: argparse.Namespace) -> dict[str, Any]:
    """Handler for `units-to-cents`.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    if args.units <= 0:
        _emit_error('--units must be > 0', exit_code=EXIT_INVALID_ARGS)
    return {'cents': units_to_cents(args.units)}


def _handle_display_money(args: argparse.Namespace) -> dict[str, Any]:
    """Handler for `display-money`.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    if args.money_digits < 0:
        _emit_error('--money-digits must be >= 0', exit_code=EXIT_INVALID_ARGS)
    return {'display': float(display_money(args.raw, args.money_digits))}


def _handle_parse_money(args: argparse.Namespace) -> dict[str, Any]:
    """Handler for `parse-money` (dual-mode: --display->raw or --raw->display).

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    if args.money_digits < 0:
        _emit_error('--money-digits must be >= 0', exit_code=EXIT_INVALID_ARGS)
    has_display = args.display is not None
    has_raw = args.raw is not None
    if has_display and has_raw:
        _emit_error(
            'parse-money accepts EITHER --display OR --raw, not both',
            exit_code=EXIT_INVALID_ARGS,
        )
    if not has_display and not has_raw:
        _emit_error(
            'parse-money requires either --display <float> or --raw <int>',
            exit_code=EXIT_INVALID_ARGS,
        )
    if has_display:
        if not math.isfinite(args.display):
            _emit_error('--display must be finite', exit_code=EXIT_NUMERIC_ERROR)
        return {'raw': parse_money(Decimal(str(args.display)), args.money_digits)}
    return {'display': float(display_money(args.raw, args.money_digits))}


def _handle_money_to_units(args: argparse.Namespace) -> dict[str, Any]:
    """Handler for `money-to-units` (alias of parse-money with --money input, 'units' output).

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    if args.money_digits < 0:
        _emit_error('--money-digits must be >= 0', exit_code=EXIT_INVALID_ARGS)
    if not math.isfinite(args.money):
        _emit_error('--money must be finite', exit_code=EXIT_NUMERIC_ERROR)
    return {'units': parse_money(Decimal(str(args.money)), args.money_digits)}


def _handle_pipettes_to_price(args: argparse.Namespace) -> dict[str, Any]:
    """Handler for `pipettes-to-price`.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    if args.pip_digits < 0:
        _emit_error('--pip-digits must be >= 0', exit_code=EXIT_INVALID_ARGS)
    return {'price': float(pipettes_to_price(args.pipettes, args.pip_digits))}


def _handle_price_to_pipettes(args: argparse.Namespace) -> dict[str, Any]:
    """Handler for `price-to-pipettes`.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    if not math.isfinite(args.price) or args.price <= 0:
        _emit_error('--price must be a positive finite number', exit_code=EXIT_NUMERIC_ERROR)
    if args.pip_digits < 0:
        _emit_error('--pip-digits must be >= 0', exit_code=EXIT_INVALID_ARGS)
    return {'pipettes': price_to_pipettes(Decimal(str(args.price)), args.pip_digits)}


_DISPATCH: dict[str, Any] = {
    'lots-to-units': _handle_lots_to_units,
    'lots-to-cents': _handle_lots_to_cents,
    'units-to-lots': _handle_units_to_lots,
    'cents-to-units': _handle_cents_to_units,
    'units-to-cents': _handle_units_to_cents,
    'display-money': _handle_display_money,
    'parse-money': _handle_parse_money,
    'money-to-units': _handle_money_to_units,
    'pipettes-to-price': _handle_pipettes_to_price,
    'price-to-pipettes': _handle_price_to_pipettes,
}


def _self_test() -> int:
    """Run canonical self-test cases.

    Returns:
        0 if all cases pass, 1 otherwise.
    """
    parser = _build_parser()
    cases: list[tuple[str, list[str], dict[str, Any], int]] = [
        (
            '0.1 lot forex -> units',
            ['lots-to-units', '--lots', '0.1', '--lot-size', '100000'],
            {'units': 10000},
            0,
        ),
        (
            '0.1 lot forex -> cents (SKILL.md row 5)',
            ['lots-to-cents', '--lots', '0.1', '--lot-size', '100000'],
            {'cents': 1000000},
            0,
        ),
        (
            'XAUUSD 0.5 lot, lot_size=100 -> units',
            ['lots-to-units', '--lots', '0.5', '--lot-size', '100'],
            {'units': 50},
            0,
        ),
        (
            'US500 0.1 lot, lot_size=1 -> cents',
            ['lots-to-cents', '--lots', '0.1', '--lot-size', '1'],
            {'cents': 10},
            0,
        ),
        (
            'units-to-lots: 10000 units -> 0.1 lot',
            ['units-to-lots', '--units', '10000', '--lot-size', '100000'],
            {'lots': 0.1},
            0,
        ),
        (
            'cents-to-units: 10000000 -> 100000',
            ['cents-to-units', '--cents', '10000000'],
            {'units': 100000},
            0,
        ),
        (
            'units-to-cents: 100000 -> 10000000',
            ['units-to-cents', '--units', '100000'],
            {'cents': 10000000},
            0,
        ),
        (
            'Remote money 1234567 with moneyDigits=2 -> display',
            ['display-money', '--raw', '1234567', '--money-digits', '2'],
            {'display': 12345.67},
            0,
        ),
        (
            'Display 100.5 with moneyDigits=2 -> raw',
            ['parse-money', '--display', '100.5', '--money-digits', '2'],
            {'raw': 10050},
            0,
        ),
        (
            'parse-money dual-mode: --raw input -> display output',
            ['parse-money', '--raw', '1234567', '--money-digits', '2'],
            {'display': 12345.67},
            0,
        ),
        (
            'money-to-units: --money 12345.67 -> units 1234567',
            ['money-to-units', '--money', '12345.67', '--money-digits', '2'],
            {'units': 1234567},
            0,
        ),
        (
            'EURUSD 1.0850 with pipDigits=5 -> pipettes',
            ['price-to-pipettes', '--price', '1.0850', '--pip-digits', '5'],
            {'pipettes': 108500},
            0,
        ),
        (
            '108500 with pipDigits=5 -> price',
            ['pipettes-to-price', '--pipettes', '108500', '--pip-digits', '5'],
            {'price': 1.085},
            0,
        ),
        (
            'XAUUSD 0.01 with moneyDigits=2 -> raw=1',
            ['parse-money', '--display', '0.01', '--money-digits', '2'],
            {'raw': 1},
            0,
        ),
        (
            'edge: negative lots rejected',
            ['lots-to-units', '--lots', '-0.1', '--lot-size', '100000'],
            {},
            EXIT_INVALID_ARGS,
        ),
        (
            'edge: parse-money rejects both flags',
            [
                'parse-money',
                '--display', '1.0',
                '--raw', '100',
                '--money-digits', '2',
            ],
            {},
            EXIT_INVALID_ARGS,
        ),
        (
            'edge: missing --lot-size rejected (lots-to-units)',
            ['lots-to-units', '--lots', '0.1'],
            {},
            EXIT_INVALID_ARGS,
        ),
        (
            'edge: missing --lot-size rejected (lots-to-cents)',
            ['lots-to-cents', '--lots', '0.1'],
            {},
            EXIT_INVALID_ARGS,
        ),
        (
            'edge: missing --lot-size rejected (units-to-lots)',
            ['units-to-lots', '--units', '10000'],
            {},
            EXIT_INVALID_ARGS,
        ),
    ]

    failures = 0
    for label, argv, expected, expected_exit in cases:
        try:
            args = parser.parse_args(argv)
            handler = _DISPATCH.get(args.subcommand)
            if handler is None:
                print(f'FAIL: {label} unknown subcommand {args.subcommand!r}', file=sys.stderr)
                failures += 1
                continue
            actual = handler(args)
        except SystemExit as exc:
            if exc.code == expected_exit:
                print(f'PASS: {label}', file=sys.stderr)
            else:
                print(f'FAIL: {label} expected exit {expected_exit}, got {exc.code}', file=sys.stderr)
                failures += 1
            continue

        if expected_exit != 0:
            print(f'FAIL: {label} expected exit {expected_exit}, completed normally', file=sys.stderr)
            failures += 1
            continue

        case_ok = True
        for key, exp_val in expected.items():
            act_val = actual.get(key)
            if isinstance(exp_val, float):
                ok = isinstance(act_val, (int, float)) and math.isclose(
                    float(act_val), exp_val, rel_tol=1e-9, abs_tol=1e-9,
                )
            else:
                ok = act_val == exp_val
            if not ok:
                print(
                    f'FAIL: {label} key={key} expected={exp_val!r} got={act_val!r}',
                    file=sys.stderr,
                )
                failures += 1
                case_ok = False
                break
        if case_ok:
            print(f'PASS: {label}', file=sys.stderr)

    if failures:
        print(f'\n{failures} test(s) failed', file=sys.stderr)
        return 1
    print('\nAll self-tests passed', file=sys.stderr)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: CLI argument list (or None to use sys.argv).

    Returns:
        Process exit code.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        return _self_test()
    handler = _DISPATCH.get(args.subcommand)
    if handler is None:
        parser.print_help(sys.stderr)
        return EXIT_INVALID_ARGS
    payload = handler(args)
    _emit_json(payload)
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
