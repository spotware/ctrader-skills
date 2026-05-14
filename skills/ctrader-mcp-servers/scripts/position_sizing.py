# /// script
# requires-python = ">=3.12"
# ///

"""Compute order size from a risk-percent or risk-amount target, with pip value and quote-to-account currency conversion."""

from __future__ import annotations

import argparse
import json
import math
import sys
from decimal import ROUND_DOWN
from decimal import Decimal
from decimal import getcontext
from typing import Any
from typing import NoReturn

getcontext().prec = 28

EXIT_OK = 0
EXIT_INVALID_ARGS = 2
EXIT_NUMERIC_ERROR = 3
EXIT_LOGIC_ERROR = 4

DEFAULT_LOT_SIZE = Decimal(100000)
DEFAULT_MIN_VOLUME_STEP = Decimal(1)
DEFAULT_MIN_VOLUME = Decimal(0)
DEFAULT_CONVERSION_RATE = Decimal(1)


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


def _round_down_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Round value DOWN to the nearest multiple of step.

    Args:
        value: Non-negative value to round.
        step: Positive step size.

    Returns:
        Largest multiple of step that does not exceed value.

    Raises:
        ValueError: If ``step`` is not strictly positive or if ``value`` is negative.
    """
    if step <= 0:
        raise ValueError(f'step must be > 0, got {step}')
    if value < 0:
        raise ValueError(f'value must be >= 0, got {value}')
    multiples = (value / step).quantize(Decimal(1), rounding=ROUND_DOWN)
    return multiples * step


def _size_from_risk_amount(
    risk_amount: Decimal,
    sl_pips: int,
    pip_value_per_lot: Decimal,
    conversion_rate: Decimal,
    lot_size: Decimal,
    min_volume_step: Decimal,
    min_volume: Decimal,
    max_volume: Decimal | None,
) -> dict[str, Any]:
    """Shared core: compute units / cents / lots / actual risk from a risk amount.

    Args:
        risk_amount: Risk amount in account currency (positive).
        sl_pips: Stop loss distance in pips (positive integer).
        pip_value_per_lot: Pip value per lot in the symbol's quote currency (positive).
        conversion_rate: Multiplier converting quote currency to account currency.
        lot_size: Number of base-asset units per lot (e.g., 100000 for forex).
        min_volume_step: Minimum volume increment in base-asset units (positive).
        min_volume: Minimum allowed volume in base-asset units.
        max_volume: Maximum allowed volume in base-asset units (None = unlimited).

    Returns:
        Output payload with units, cents, lots, risk_currency_amount, warnings.
    """
    if sl_pips <= 0:
        _emit_error('--sl-pips must be > 0', exit_code=EXIT_INVALID_ARGS)
    if pip_value_per_lot <= 0:
        _emit_error('--pip-value-per-lot must be > 0', exit_code=EXIT_INVALID_ARGS)
    if conversion_rate <= 0:
        _emit_error('--conversion-rate must be > 0', exit_code=EXIT_INVALID_ARGS)
    if lot_size <= 0:
        _emit_error('--lot-size must be > 0', exit_code=EXIT_INVALID_ARGS)
    if min_volume_step <= 0:
        _emit_error('--min-volume-step must be > 0', exit_code=EXIT_INVALID_ARGS)
    if min_volume < 0:
        _emit_error('--min-volume must be >= 0', exit_code=EXIT_INVALID_ARGS)

    warnings: list[str] = []

    pip_value_per_lot_account = pip_value_per_lot * conversion_rate
    target_lots = risk_amount / (Decimal(sl_pips) * pip_value_per_lot_account)
    target_units_raw = target_lots * lot_size

    target_units_rounded = _round_down_to_step(target_units_raw, min_volume_step)
    rounding_loss = target_units_raw - target_units_rounded
    if rounding_loss >= min_volume_step:
        warnings.append(
            f'volume rounded down from {float(target_units_raw)} to '
            f'{float(target_units_rounded)} due to volume step {float(min_volume_step)}',
        )

    intended_risk = float(risk_amount)
    if target_units_rounded < min_volume:
        original = target_units_rounded
        target_units_rounded = min_volume
        warnings.append(
            f'computed volume {float(original)} below minimum {float(min_volume)}; clipped to minimum',
        )
        actual_lots = target_units_rounded / lot_size
        actual_risk = float(actual_lots * Decimal(sl_pips) * pip_value_per_lot_account)
        if actual_risk > intended_risk:
            warnings.append(
                f'clipping to min_volume increases risk from {intended_risk} to {actual_risk} '
                f'in account currency',
            )

    if max_volume is not None and target_units_rounded > max_volume:
        original = target_units_rounded
        target_units_rounded = max_volume
        warnings.append(
            f'computed volume {float(original)} above maximum {float(max_volume)}; clipped to maximum',
        )

    final_lots = target_units_rounded / lot_size
    actual_risk_amount = final_lots * Decimal(sl_pips) * pip_value_per_lot_account

    units_int = int(target_units_rounded)
    cent_lot_size = lot_size * Decimal(100)
    target_cents_raw = target_lots * cent_lot_size
    target_cents_rounded = _round_down_to_step(target_cents_raw, Decimal(1))
    if min_volume > 0 and target_cents_rounded < min_volume * Decimal(100):
        target_cents_rounded = min_volume * Decimal(100)
    if max_volume is not None and target_cents_rounded > max_volume * Decimal(100):
        target_cents_rounded = max_volume * Decimal(100)
    cents_int = int(target_cents_rounded)

    return {
        'units': units_int,
        'cents': cents_int,
        'lots': float(final_lots),
        'risk_currency_amount': float(actual_risk_amount),
        'warnings': warnings,
    }


def from_risk_percent(
    balance: Decimal,
    risk_pct: Decimal,
    sl_pips: int,
    pip_value_per_lot: Decimal,
    conversion_rate: Decimal,
    lot_size: Decimal,
    min_volume_step: Decimal,
    min_volume: Decimal,
    max_volume: Decimal | None,
) -> dict[str, Any]:
    """Compute units / cents / lots / risk amount from a risk-percent target.

    Args:
        balance: Account balance in account currency (positive).
        risk_pct: Risk percentage of balance (positive, < 100).
        sl_pips: Stop loss distance in pips (positive).
        pip_value_per_lot: Pip value per lot in symbol's quote currency.
        conversion_rate: Multiplier from quote currency to account currency.
        lot_size: Base-asset units per lot.
        min_volume_step: Minimum volume increment in base-asset units.
        min_volume: Minimum allowed volume in base-asset units.
        max_volume: Maximum allowed volume in base-asset units (None = unlimited).

    Returns:
        Output payload with units, cents, lots, risk_currency_amount, warnings.
    """
    if balance <= 0:
        _emit_error('--balance must be > 0', exit_code=EXIT_INVALID_ARGS)
    if risk_pct <= 0 or risk_pct >= 100:
        _emit_error('--risk-pct must be > 0 and < 100', exit_code=EXIT_INVALID_ARGS)
    risk_amount = balance * (risk_pct / Decimal(100))
    return _size_from_risk_amount(
        risk_amount=risk_amount,
        sl_pips=sl_pips,
        pip_value_per_lot=pip_value_per_lot,
        conversion_rate=conversion_rate,
        lot_size=lot_size,
        min_volume_step=min_volume_step,
        min_volume=min_volume,
        max_volume=max_volume,
    )


def from_risk_amount(
    risk_amount: Decimal,
    sl_pips: int,
    pip_value_per_lot: Decimal,
    conversion_rate: Decimal,
    lot_size: Decimal,
    min_volume_step: Decimal,
    min_volume: Decimal,
    max_volume: Decimal | None,
) -> dict[str, Any]:
    """Compute units / cents / lots from an explicit risk amount in account currency.

    Args:
        risk_amount: Risk amount in account currency (positive).
        sl_pips: Stop loss distance in pips (positive).
        pip_value_per_lot: Pip value per lot in symbol's quote currency.
        conversion_rate: Multiplier from quote currency to account currency.
        lot_size: Base-asset units per lot.
        min_volume_step: Minimum volume increment in base-asset units.
        min_volume: Minimum allowed volume in base-asset units.
        max_volume: Maximum allowed volume in base-asset units (None = unlimited).

    Returns:
        Output payload with units, cents, lots, risk_currency_amount, warnings.
    """
    if risk_amount <= 0:
        _emit_error('--risk-amount must be > 0', exit_code=EXIT_INVALID_ARGS)
    return _size_from_risk_amount(
        risk_amount=risk_amount,
        sl_pips=sl_pips,
        pip_value_per_lot=pip_value_per_lot,
        conversion_rate=conversion_rate,
        lot_size=lot_size,
        min_volume_step=min_volume_step,
        min_volume=min_volume,
        max_volume=max_volume,
    )


def _build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argparse.ArgumentParser with two subparsers."""
    parser = argparse.ArgumentParser(
        prog='position_sizing.py',
        description='Compute order size from a risk-percent or risk-amount target.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Examples:\n'
            '  python position_sizing.py from-risk-percent --balance 10000 --risk-pct 1 \\\n'
            '      --sl-pips 30 --pip-value-per-lot 10 --conversion-rate 1.0\n'
            '  python position_sizing.py from-risk-amount --risk-amount 100 --sl-pips 30 \\\n'
            '      --pip-value-per-lot 10 --conversion-rate 1.0\n'
            '  python position_sizing.py --self-test\n'
            '\n'
            'Exit codes:\n'
            '  0  success\n'
            '  2  invalid arguments (including sl_pips=0, balance<=0, risk_pct out of range)\n'
            '  3  numeric error\n'
        ),
    )
    parser.add_argument(
        '--self-test',
        action='store_true',
        help='Run built-in self-test cases and exit 0 if all pass.',
    )

    subparsers = parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND')

    common_optional: list[tuple[str, dict[str, Any]]] = [
        ('--conversion-rate', {'type': float, 'default': 1.0}),
        ('--lot-size', {'type': float, 'default': 100000.0}),
        ('--min-volume-step', {'type': float, 'default': 1.0}),
        ('--min-volume', {'type': float, 'default': 0.0}),
        ('--max-volume', {'type': float, 'default': None}),
    ]

    p1 = subparsers.add_parser(
        'from-risk-percent',
        help='Compute size from a risk percentage of account balance.',
    )
    p1.add_argument('--balance', required=True, type=float)
    p1.add_argument('--risk-pct', required=True, type=float)
    p1.add_argument('--sl-pips', required=True, type=int)
    p1.add_argument('--pip-value-per-lot', required=True, type=float)
    for name, kwargs in common_optional:
        p1.add_argument(name, **kwargs)

    p2 = subparsers.add_parser(
        'from-risk-amount',
        help='Compute size from an explicit risk amount in account currency.',
    )
    p2.add_argument('--risk-amount', required=True, type=float)
    p2.add_argument('--sl-pips', required=True, type=int)
    p2.add_argument('--pip-value-per-lot', required=True, type=float)
    for name, kwargs in common_optional:
        p2.add_argument(name, **kwargs)

    return parser


def _common_decimal_args(args: argparse.Namespace) -> dict[str, Any]:
    """Convert common float CLI args into Decimal kwargs for the core function.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Dict ready to splat into the sizing core.
    """
    for name, value in [
        ('pip_value_per_lot', args.pip_value_per_lot),
        ('conversion_rate', args.conversion_rate),
        ('lot_size', args.lot_size),
        ('min_volume_step', args.min_volume_step),
        ('min_volume', args.min_volume),
    ]:
        if not math.isfinite(value):
            _emit_error(f"--{name.replace('_', '-')} must be finite", exit_code=EXIT_NUMERIC_ERROR)
    if args.max_volume is not None and not math.isfinite(args.max_volume):
        _emit_error('--max-volume must be finite', exit_code=EXIT_NUMERIC_ERROR)

    return {
        'pip_value_per_lot': Decimal(str(args.pip_value_per_lot)),
        'conversion_rate': Decimal(str(args.conversion_rate)),
        'lot_size': Decimal(str(args.lot_size)),
        'min_volume_step': Decimal(str(args.min_volume_step)),
        'min_volume': Decimal(str(args.min_volume)),
        'max_volume': Decimal(str(args.max_volume)) if args.max_volume is not None else None,
    }


def _handle_from_risk_percent(args: argparse.Namespace) -> dict[str, Any]:
    """Dispatch handler for `from-risk-percent`.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    if not math.isfinite(args.balance):
        _emit_error('--balance must be finite', exit_code=EXIT_NUMERIC_ERROR)
    if not math.isfinite(args.risk_pct):
        _emit_error('--risk-pct must be finite', exit_code=EXIT_NUMERIC_ERROR)
    base = _common_decimal_args(args)
    return from_risk_percent(
        balance=Decimal(str(args.balance)),
        risk_pct=Decimal(str(args.risk_pct)),
        sl_pips=args.sl_pips,
        **base,
    )


def _handle_from_risk_amount(args: argparse.Namespace) -> dict[str, Any]:
    """Dispatch handler for `from-risk-amount`.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    if not math.isfinite(args.risk_amount):
        _emit_error('--risk-amount must be finite', exit_code=EXIT_NUMERIC_ERROR)
    base = _common_decimal_args(args)
    return from_risk_amount(
        risk_amount=Decimal(str(args.risk_amount)),
        sl_pips=args.sl_pips,
        **base,
    )


def _self_test() -> int:
    """Run canonical self-test cases.

    Returns:
        0 if all cases pass, 1 otherwise.
    """
    parser = _build_parser()
    cases: list[tuple[str, list[str], dict[str, Any], int]] = [
        (
            'EURUSD 1% risk on 10000 USD, 30 pip SL (SKILL.md row 2)',
            [
                'from-risk-percent',
                '--balance', '10000',
                '--risk-pct', '1',
                '--sl-pips', '30',
                '--pip-value-per-lot', '10',
                '--conversion-rate', '1.0',
            ],
            {'units': 33333, 'cents': 3333333, 'risk_currency_amount': 99.999},
            0,
        ),
        (
            'XAUUSD 2% risk on 5000 USD, 100 pip SL, lot_size=100',
            [
                'from-risk-percent',
                '--balance', '5000',
                '--risk-pct', '2',
                '--sl-pips', '100',
                '--pip-value-per-lot', '1',
                '--conversion-rate', '1.0',
                '--lot-size', '100',
                '--min-volume-step', '1',
            ],
            {'lots': 1.0, 'units': 100, 'cents': 10000, 'risk_currency_amount': 100.0},
            0,
        ),
        (
            'US500 fixed 50 USD risk, 20 pip SL, lot_size=1',
            [
                'from-risk-amount',
                '--risk-amount', '50',
                '--sl-pips', '20',
                '--pip-value-per-lot', '1',
                '--conversion-rate', '1.0',
                '--lot-size', '1',
                '--min-volume-step', '1',
            ],
            {'units': 2, 'cents': 250, 'risk_currency_amount': 40.0},
            0,
        ),
        (
            'cross-ccy 1% on EUR account, conversion_rate=0.85',
            [
                'from-risk-percent',
                '--balance', '10000',
                '--risk-pct', '1',
                '--sl-pips', '30',
                '--pip-value-per-lot', '10',
                '--conversion-rate', '0.85',
            ],
            {'units': 39215, 'cents': 3921568},
            0,
        ),
    ]

    failures = 0
    for label, argv, expected, expected_exit in cases:
        try:
            args = parser.parse_args(argv)
            if args.subcommand == 'from-risk-percent':
                actual = _handle_from_risk_percent(args)
            elif args.subcommand == 'from-risk-amount':
                actual = _handle_from_risk_amount(args)
            else:
                print(f'FAIL: {label} unknown subcommand {args.subcommand!r}', file=sys.stderr)
                failures += 1
                continue
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
                    float(act_val), exp_val, rel_tol=1e-3, abs_tol=1e-3,
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

    edge_argv = [
        'from-risk-percent',
        '--balance', '0',
        '--risk-pct', '1',
        '--sl-pips', '30',
        '--pip-value-per-lot', '10',
        '--conversion-rate', '1.0',
    ]
    try:
        args = parser.parse_args(edge_argv)
        _handle_from_risk_percent(args)
        print('FAIL: edge: zero balance should be rejected', file=sys.stderr)
        failures += 1
    except SystemExit as exc:
        if exc.code == EXIT_INVALID_ARGS:
            print('PASS: edge: zero balance rejected with exit 2', file=sys.stderr)
        else:
            print(
                f'FAIL: edge: zero balance expected exit 2, got {exc.code}',
                file=sys.stderr,
            )
            failures += 1

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
    if args.subcommand == 'from-risk-percent':
        payload = _handle_from_risk_percent(args)
    elif args.subcommand == 'from-risk-amount':
        payload = _handle_from_risk_amount(args)
    else:
        parser.print_help(sys.stderr)
        return EXIT_INVALID_ARGS
    _emit_json(payload)
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
