# /// script
# requires-python = ">=3.12"
# ///

"""Convert between pip distance and absolute price for cTrader Local and Remote server display-price encoding.

This script operates on DISPLAY prices throughout. When receiving pipettes from
`get_spot_prices` / `get_trendbars` on the Remote server, decode via
`units_encoding.py pipettes-to-price --pipettes <int> --pip-digits <int>` BEFORE
passing prices to this script. See [Q-K19](../references/known-quirks.md#q-k19).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from decimal import ROUND_HALF_UP
from decimal import Decimal
from decimal import getcontext
from pathlib import Path
from typing import Any
from typing import NoReturn

getcontext().prec = 28

EXIT_OK = 0
EXIT_INVALID_ARGS = 2
EXIT_NUMERIC_ERROR = 3
EXIT_LOGIC_ERROR = 4

_SIDES = ('buy', 'sell')
_DIRECTIONS = ('sl', 'tp')

_ASSET_PATH = Path(__file__).parent.parent / 'assets' / 'symbol_precision_table.json'


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


def _polarity(side: str, direction: str) -> int:
    """Return +1 if pip movement adds to price, -1 if it subtracts.

    Args:
        side: Trade side, 'buy' or 'sell'.
        direction: SL/TP context, 'sl' or 'tp'.

    Returns:
        +1 if (side, direction) combination causes price to add, -1 if subtract.

    Raises:
        ValueError: If the (side, direction) combination is not recognized.
    """
    if side == 'buy' and direction == 'sl':
        return -1
    if side == 'buy' and direction == 'tp':
        return +1
    if side == 'sell' and direction == 'sl':
        return +1
    if side == 'sell' and direction == 'tp':
        return -1
    raise ValueError(f'invalid side/direction combination: side={side!r}, direction={direction!r}')


def _quantize(value: Decimal, digits: int) -> Decimal:
    """Round a Decimal value to a given number of decimal places using ROUND_HALF_UP.

    Args:
        value: The value to round.
        digits: Number of decimal places (>= 0).

    Returns:
        The value rounded to the requested number of decimal places.

    Raises:
        ValueError: If ``digits`` is negative.
    """
    if digits < 0:
        raise ValueError(f'digits must be >= 0, got {digits}')
    quant = Decimal(1) if digits == 0 else Decimal(1).scaleb(-digits)
    return value.quantize(quant, rounding=ROUND_HALF_UP)


def pips_to_price(
    reference_price: Decimal,
    pips: int,
    pip_size: Decimal,
    side: str,
    direction: str,
) -> Decimal:
    """Convert a pip distance to an absolute price.

    Args:
        reference_price: Entry price (for SL/TP placement) or current quote.
        pips: Pip distance (non-negative integer). The polarity relative to reference_price
              is determined by (side, direction).
        pip_size: Price increment per pip (e.g., 0.0001 for EURUSD, 0.01 for USDJPY,
                  0.01 for XAUUSD, 0.1 for an index).
        side: 'buy' or 'sell'.
        direction: 'sl' or 'tp'.

    Returns:
        Absolute price as a Decimal (NOT yet rounded to digits; caller rounds).

    Polarity rules:
        side=buy,  direction=sl: price = reference_price - (pips * pip_size)
        side=buy,  direction=tp: price = reference_price + (pips * pip_size)
        side=sell, direction=sl: price = reference_price + (pips * pip_size)
        side=sell, direction=tp: price = reference_price - (pips * pip_size)
    """
    sign = _polarity(side, direction)
    return reference_price + Decimal(sign) * Decimal(pips) * pip_size


def price_to_pips(
    reference_price: Decimal,
    target_price: Decimal,
    pip_size: Decimal,
) -> tuple[int, Decimal]:
    """Convert an absolute price to a pip distance.

    Args:
        reference_price: Entry price or current quote.
        target_price: Target absolute price (SL or TP level).
        pip_size: Price increment per pip.

    Returns:
        Tuple of (rounded integer pip distance, raw Decimal pip distance).
        The integer pip distance is the absolute value rounded to the nearest pip
        using ROUND_HALF_UP.

    Raises:
        ValueError: If ``pip_size`` is not strictly positive.
    """
    if pip_size <= 0:
        raise ValueError(f'pip_size must be > 0, got {pip_size}')
    raw = abs(target_price - reference_price) / pip_size
    rounded = int(raw.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return rounded, raw


def sl_tp_from_risk_reward(
    entry: Decimal,
    risk_pips: int,
    reward_pips: int,
    pip_size: Decimal,
    side: str,
) -> tuple[Decimal, Decimal]:
    """Given entry, risk-in-pips and reward-in-pips, return (sl_absolute, tp_absolute).

    Args:
        entry: Entry price.
        risk_pips: Distance from entry to stop loss, in pips (positive).
        reward_pips: Distance from entry to take profit, in pips (positive).
        pip_size: Price increment per pip.
        side: 'buy' or 'sell'.

    Returns:
        Tuple of (stop_loss_price, take_profit_price) as Decimals.
    """
    sl = pips_to_price(entry, risk_pips, pip_size, side, 'sl')
    tp = pips_to_price(entry, reward_pips, pip_size, side, 'tp')
    return sl, tp


def sl_tp_to_pip_distances(
    entry: Decimal,
    sl_absolute: Decimal,
    tp_absolute: Decimal,
    pip_size: Decimal,
) -> tuple[int, int]:
    """Given entry + absolute SL + absolute TP, return (sl_pips, tp_pips).

    Args:
        entry: Entry price.
        sl_absolute: Absolute stop-loss price.
        tp_absolute: Absolute take-profit price.
        pip_size: Price increment per pip.

    Returns:
        Tuple of (sl_pips, tp_pips), both non-negative integers.
    """
    sl_pips, _ = price_to_pips(entry, sl_absolute, pip_size)
    tp_pips, _ = price_to_pips(entry, tp_absolute, pip_size)
    return sl_pips, tp_pips


def _load_precision_table() -> dict[str, Any]:
    """Load and parse the precision baseline asset.

    Terminates the process via ``_emit_error`` (``EXIT_LOGIC_ERROR``) when the
    precision baseline asset cannot be loaded (missing file, unreadable
    content, or unexpected JSON shape).

    Returns:
        Parsed JSON dict with top-level keys ``__note__``, ``schema_version``,
        ``as_of``, ``audit_method``, ``symbols`` (list).
    """
    if not _ASSET_PATH.is_file():
        _emit_error(
            f'precision table not found at {_ASSET_PATH}',
            exit_code=EXIT_LOGIC_ERROR,
        )
    try:
        with _ASSET_PATH.open('r', encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        _emit_error(
            f'failed to load precision table: {exc}',
            exit_code=EXIT_LOGIC_ERROR,
        )
    if not isinstance(data, dict) or not isinstance(data.get('symbols'), list):
        _emit_error(
            "precision table has unexpected shape (expected dict with 'symbols' list)",
            exit_code=EXIT_LOGIC_ERROR,
        )
    return data


def _build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argparse.ArgumentParser with three subparsers."""
    parser = argparse.ArgumentParser(
        prog='pip_math.py',
        description='Convert between pip distance and absolute price for cTrader server encodings.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python pip_math.py pips-to-price --pip-size 0.0001 --digits 5 \\\n"
            "      --reference-price 1.0850 --pips 30 --side buy --direction tp\n"
            "  python pip_math.py price-to-pips --pip-size 0.01 --digits 2 \\\n"
            "      --reference-price 1900.50 --price 1901.50 --side buy --direction tp\n"
            "  python pip_math.py lookup-precision --symbol EURUSD\n"
            "  python pip_math.py --self-test\n"
            "\n"
            "Exit codes:\n"
            "  0  success (including 'symbol not in baseline' miss on lookup-precision)\n"
            "  2  invalid arguments\n"
            "  3  numeric error (non-finite reference price, pip_size <= 0)\n"
            "  4  asset-load error (precision table missing or corrupt)\n"
        ),
    )
    parser.add_argument(
        '--self-test',
        action='store_true',
        help='Run built-in self-test cases and exit 0 if all pass.',
    )

    subparsers = parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND')

    p1 = subparsers.add_parser(
        'pips-to-price',
        help='Convert a pip distance into an absolute price.',
    )
    p1.add_argument('--pip-size', required=True, type=float)
    p1.add_argument('--digits', required=True, type=int)
    p1.add_argument('--reference-price', required=True, type=float)
    p1.add_argument('--pips', required=True, type=int)
    p1.add_argument('--side', default='buy', choices=_SIDES)
    p1.add_argument('--direction', default='tp', choices=_DIRECTIONS)

    p2 = subparsers.add_parser(
        'price-to-pips',
        help='Convert an absolute price into a pip distance from the reference price.',
    )
    p2.add_argument('--pip-size', required=True, type=float)
    p2.add_argument('--digits', required=True, type=int)
    p2.add_argument('--reference-price', required=True, type=float)
    p2.add_argument('--price', required=True, type=float)
    p2.add_argument('--side', default='buy', choices=_SIDES)
    p2.add_argument('--direction', default='tp', choices=_DIRECTIONS)

    p3 = subparsers.add_parser(
        'lookup-precision',
        help='Look up baseline precision for a symbol from assets/symbol_precision_table.json.',
    )
    p3.add_argument('--symbol', required=True, type=str)

    return parser


def _handle_pips_to_price(args: argparse.Namespace) -> dict[str, Any]:
    """Dispatch handler for the `pips-to-price` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    pip_size = Decimal(str(args.pip_size))
    if pip_size <= 0:
        _emit_error(f'--pip-size must be > 0, got {args.pip_size}', exit_code=EXIT_NUMERIC_ERROR)
    if args.digits < 0:
        _emit_error(f'--digits must be >= 0, got {args.digits}', exit_code=EXIT_INVALID_ARGS)
    if not math.isfinite(args.reference_price):
        _emit_error(
            f'--reference-price must be finite, got {args.reference_price}',
            exit_code=EXIT_NUMERIC_ERROR,
        )
    reference = Decimal(str(args.reference_price))
    raw = pips_to_price(reference, args.pips, pip_size, args.side, args.direction)
    rounded = _quantize(raw, args.digits)
    return {
        'absolute_price': float(rounded),
        'pip_size_used': float(pip_size),
        'rounded_to_digits': args.digits,
    }


def _handle_price_to_pips(args: argparse.Namespace) -> dict[str, Any]:
    """Dispatch handler for the `price-to-pips` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    pip_size = Decimal(str(args.pip_size))
    if pip_size <= 0:
        _emit_error(f'--pip-size must be > 0, got {args.pip_size}', exit_code=EXIT_NUMERIC_ERROR)
    if not math.isfinite(args.reference_price) or not math.isfinite(args.price):
        _emit_error('--reference-price and --price must be finite', exit_code=EXIT_NUMERIC_ERROR)
    reference = Decimal(str(args.reference_price))
    target = Decimal(str(args.price))
    rounded, raw = price_to_pips(reference, target, pip_size)
    return {
        'pip_distance': rounded,
        'pip_distance_raw': float(raw),
        'pip_size_used': float(pip_size),
    }


def _handle_lookup_precision(args: argparse.Namespace) -> dict[str, Any]:
    """Dispatch handler for the `lookup-precision` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON. If the symbol is found, returns the
        row plus the table-level `__note__`. If the symbol is not in the
        baseline, returns `{"available": false, "symbol": ..., "suggestion": ...}`
        with exit code 0 (a miss is not an error -- the caller falls back
        to `get_symbol_details`).
    """
    table = _load_precision_table()
    note = table.get('__note__', '')
    for row in table['symbols']:
        if isinstance(row, dict) and row.get('symbol') == args.symbol:
            return {
                'symbol': row.get('symbol'),
                'pipDigits': row.get('pipDigits'),
                'pipettesPerUnit': row.get('pipettesPerUnit'),
                'lotSize_baseline': row.get('lotSize_baseline'),
                'source': row.get('source'),
                'as_of': row.get('as_of'),
                '__note__': note,
            }
    return {
        'available': False,
        'symbol': args.symbol,
        'suggestion': 'symbol not in baseline -- verify against get_symbol_details(symbol)',
        '__note__': note,
    }


def _self_test() -> int:
    """Run canonical self-test cases.

    Returns:
        0 if all cases pass, 1 otherwise.
    """
    parser = _build_parser()
    cases: list[tuple[str, list[str], dict[str, Any]]] = [
        (
            'EURUSD long SL 30 pips below 1.0850',
            [
                'pips-to-price',
                '--pip-size', '0.0001',
                '--digits', '5',
                '--reference-price', '1.0850',
                '--pips', '30',
                '--side', 'buy',
                '--direction', 'sl',
            ],
            {'absolute_price': 1.082, 'pip_size_used': 0.0001},
        ),
        (
            'EURUSD long TP 30 pips above 1.0850 (SKILL.md row 1)',
            [
                'pips-to-price',
                '--pip-size', '0.0001',
                '--digits', '5',
                '--reference-price', '1.0850',
                '--pips', '30',
                '--side', 'buy',
                '--direction', 'tp',
            ],
            {'absolute_price': 1.088, 'pip_size_used': 0.0001},
        ),
        (
            'USDJPY short SL 50 pips above 150.30',
            [
                'pips-to-price',
                '--pip-size', '0.01',
                '--digits', '3',
                '--reference-price', '150.30',
                '--pips', '50',
                '--side', 'sell',
                '--direction', 'sl',
            ],
            {'absolute_price': 150.8, 'pip_size_used': 0.01},
        ),
        (
            'XAUUSD long TP 100 pips above 1900.50 (metal pip_size=0.01)',
            [
                'pips-to-price',
                '--pip-size', '0.01',
                '--digits', '2',
                '--reference-price', '1900.50',
                '--pips', '100',
                '--side', 'buy',
                '--direction', 'tp',
            ],
            {'absolute_price': 1901.5, 'pip_size_used': 0.01},
        ),
        (
            'US500 long SL 20 pips below 5000.0 (index pip_size=0.1)',
            [
                'pips-to-price',
                '--pip-size', '0.1',
                '--digits', '1',
                '--reference-price', '5000.0',
                '--pips', '20',
                '--side', 'buy',
                '--direction', 'sl',
            ],
            {'absolute_price': 4998.0, 'pip_size_used': 0.1},
        ),
        (
            'price-to-pips EURUSD entry 1.0850 SL 1.0820',
            [
                'price-to-pips',
                '--pip-size', '0.0001',
                '--digits', '5',
                '--reference-price', '1.0850',
                '--price', '1.0820',
                '--side', 'buy',
                '--direction', 'sl',
            ],
            {'pip_distance': 30, 'pip_size_used': 0.0001},
        ),
        (
            'edge: zero pip distance',
            [
                'pips-to-price',
                '--pip-size', '0.0001',
                '--digits', '5',
                '--reference-price', '1.0850',
                '--pips', '0',
                '--side', 'buy',
                '--direction', 'sl',
            ],
            {'absolute_price': 1.085, 'pip_size_used': 0.0001},
        ),
        (
            'lookup-precision EURUSD baseline (Phase 2 asset row 1)',
            [
                'lookup-precision',
                '--symbol', 'EURUSD',
            ],
            {
                'symbol': 'EURUSD',
                'pipDigits': 5,
                'pipettesPerUnit': 100000,
                'lotSize_baseline': 100000,
                'source': 'remote',
            },
        ),
        (
            'lookup-precision XAUUSD baseline (3-digit pip per Phase 2 override)',
            [
                'lookup-precision',
                '--symbol', 'XAUUSD',
            ],
            {
                'symbol': 'XAUUSD',
                'pipDigits': 3,
                'pipettesPerUnit': 1000,
                'lotSize_baseline': 100,
                'source': 'local',
            },
        ),
        (
            'lookup-precision unknown ticker returns available:false',
            [
                'lookup-precision',
                '--symbol', 'UNKNOWN_TICKER',
            ],
            {
                'available': False,
                'symbol': 'UNKNOWN_TICKER',
            },
        ),
    ]

    failures = 0
    for label, argv, expected in cases:
        try:
            args = parser.parse_args(argv)
            if args.subcommand == 'pips-to-price':
                actual = _handle_pips_to_price(args)
            elif args.subcommand == 'price-to-pips':
                actual = _handle_price_to_pips(args)
            elif args.subcommand == 'lookup-precision':
                actual = _handle_lookup_precision(args)
            else:
                print(f'FAIL: {label} unknown subcommand {args.subcommand!r}', file=sys.stderr)
                failures += 1
                continue
        except SystemExit as exc:
            print(f'FAIL: {label} unexpected exit {exc.code}', file=sys.stderr)
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
    if args.subcommand == 'pips-to-price':
        payload = _handle_pips_to_price(args)
    elif args.subcommand == 'price-to-pips':
        payload = _handle_price_to_pips(args)
    elif args.subcommand == 'lookup-precision':
        payload = _handle_lookup_precision(args)
    else:
        parser.print_help(sys.stderr)
        return EXIT_INVALID_ARGS
    _emit_json(payload)
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
