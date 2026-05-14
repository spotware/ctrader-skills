# /// script
# requires-python = ">=3.12"
# ///

"""Compute dynamic-leverage required margin in USD across a per-tier leverage curve for a cTrader position."""

from __future__ import annotations

import argparse
import json
import math
import sys
from decimal import Decimal
from decimal import getcontext
from typing import Any
from typing import NoReturn
from typing import cast

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


def _validate_tiers(tiers: object) -> list[dict[str, Any]]:
    """Validate the tier list shape and ordering.

    Args:
        tiers: Parsed JSON value (raw input).

    Returns:
        Normalized list with `upper` as int|None and `leverage` as int.
    """
    if not isinstance(tiers, list) or len(tiers) == 0:
        _emit_error('--tiers must be a non-empty JSON list', exit_code=EXIT_INVALID_ARGS)

    normalized: list[dict[str, Any]] = []
    last_upper: int | None = 0
    for idx, raw in enumerate(tiers):
        if not isinstance(raw, dict):
            _emit_error(
                f"--tiers[{idx}] must be an object with 'upper' and 'leverage' keys",
                exit_code=EXIT_INVALID_ARGS,
            )
        raw_dict = cast('dict[str, Any]', raw)
        if 'upper' not in raw_dict or 'leverage' not in raw_dict:
            _emit_error(
                f"--tiers[{idx}] missing 'upper' or 'leverage' key",
                exit_code=EXIT_INVALID_ARGS,
            )
        upper_raw = raw_dict['upper']
        leverage_raw = raw_dict['leverage']
        is_last = idx == len(tiers) - 1

        if upper_raw is None:
            if not is_last:
                _emit_error(
                    f"--tiers[{idx}] has 'upper': null but is not the final tier",
                    exit_code=EXIT_LOGIC_ERROR,
                )
            upper: int | None = None
        else:
            if not isinstance(upper_raw, int) or isinstance(upper_raw, bool):
                _emit_error(
                    f"--tiers[{idx}] 'upper' must be an integer or null, got {type(upper_raw).__name__}",
                    exit_code=EXIT_INVALID_ARGS,
                )
            if upper_raw <= 0:
                _emit_error(
                    f"--tiers[{idx}] 'upper' must be > 0 when not null",
                    exit_code=EXIT_INVALID_ARGS,
                )
            if last_upper is not None and upper_raw <= last_upper:
                _emit_error(
                    f"--tiers[{idx}] 'upper' must be strictly greater than previous tier's upper",
                    exit_code=EXIT_LOGIC_ERROR,
                )
            upper = upper_raw
            last_upper = upper

        if not isinstance(leverage_raw, int) or isinstance(leverage_raw, bool):
            _emit_error(
                f"--tiers[{idx}] 'leverage' must be an integer, got {type(leverage_raw).__name__}",
                exit_code=EXIT_INVALID_ARGS,
            )
        if leverage_raw <= 0:
            _emit_error(
                f"--tiers[{idx}] 'leverage' must be > 0",
                exit_code=EXIT_INVALID_ARGS,
            )

        normalized.append({'upper': upper, 'leverage': leverage_raw})

    if normalized[-1]['upper'] is not None:
        _emit_error(
            "final tier must have 'upper': null (covers all exposure above the last finite bound)",
            exit_code=EXIT_LOGIC_ERROR,
        )

    return normalized


def compute_margin(
    volume_base_units: int,
    quote_rate_usd: Decimal,
    tiers: list[dict[str, Any]],
    account_currency: str,
    account_currency_rate_vs_usd: Decimal,
) -> dict[str, Any]:
    """Compute required margin in USD and account currency across the tier curve.

    Args:
        volume_base_units: Position size in base-asset units (positive integer).
        quote_rate_usd: Conversion factor: 1 base-asset unit = quote_rate_usd USD.
                        For symbols quoted in USD this equals the spot price.
        tiers: Validated tier list, ordered ascending by upper, final upper=None.
        account_currency: ISO code for the account currency (e.g., "JPY", "EUR", "USD").
        account_currency_rate_vs_usd: Rate is the multiplier from USD to account
                                       currency (1 USD = <rate> account-ccy units).
                                       For a USD account, rate=1.0. For a JPY account,
                                       rate is the USDJPY spot (~149.25).

    Returns:
        Dict with margin_usd, margin_account_ccy, account_currency,
        account_currency_rate_vs_usd, per_tier_breakdown, notional_usd.

    Algorithm:
        notional_usd = volume_base_units * quote_rate_usd
        Iterate tiers in order. Each tier has a capacity = upper - cursor (or remaining
        if upper is None). Absorb min(capacity, remaining) of the notional into that tier
        and add absorbed / leverage to the running margin total (in USD).
        Finally, margin_account_ccy = margin_usd * account_currency_rate_vs_usd.
    """
    notional_usd = Decimal(volume_base_units) * quote_rate_usd
    remaining = notional_usd
    cursor = Decimal(0)
    margin_total = Decimal(0)
    breakdown: list[dict[str, Any]] = []

    for tier in tiers:
        upper = tier['upper']
        leverage = Decimal(tier['leverage'])
        if upper is None:
            absorbed = remaining
        else:
            tier_capacity = Decimal(upper) - cursor
            absorbed = min(tier_capacity, remaining)
        if absorbed < 0:
            absorbed = Decimal(0)
        tier_margin = absorbed / leverage
        margin_total += tier_margin
        breakdown.append(
            {
                'upper': upper,
                'leverage': int(leverage),
                'absorbed_usd': float(absorbed),
                'tier_margin_usd': float(tier_margin),
            },
        )
        remaining -= absorbed
        if upper is not None:
            cursor = Decimal(upper)
        if remaining <= 0:
            break

    margin_account_ccy = margin_total * account_currency_rate_vs_usd

    return {
        'margin_usd': float(margin_total),
        'margin_account_ccy': float(margin_account_ccy),
        'account_currency': account_currency,
        'account_currency_rate_vs_usd': float(account_currency_rate_vs_usd),
        'per_tier_breakdown': breakdown,
        'notional_usd': float(notional_usd),
    }


def _build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argparse.ArgumentParser with the `compute` subparser."""
    parser = argparse.ArgumentParser(
        prog='tiered_margin.py',
        description='Compute dynamic-leverage required margin in USD across a per-tier leverage curve.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python tiered_margin.py compute --volume-base-units 1000000 --quote-rate-usd 1.21345 \\\n"
            "      --tiers '[{\"upper\":1000000,\"leverage\":500},"
            "{\"upper\":5000000,\"leverage\":200},{\"upper\":null,\"leverage\":100}]'\n"
            "  python tiered_margin.py compute --volume-base-units 1000000 --quote-rate-usd 1.21345 \\\n"
            "      --account-currency JPY --account-currency-rate-vs-usd 149.25 \\\n"
            "      --tiers '[{\"upper\":null,\"leverage\":100}]'\n"
            "  python tiered_margin.py --self-test\n"
            "\n"
            "--account-currency-rate-vs-usd convention: rate is the multiplier from USD to\n"
            "account currency (i.e., 1 USD = <rate> account-ccy units). For a USD account,\n"
            "rate=1.0 (the default). For a JPY account, rate is the USDJPY spot (~149).\n"
            "Output includes both margin_usd AND margin_account_ccy = margin_usd * rate.\n"
            "\n"
            "Exit codes:\n"
            "  0  success\n"
            "  2  invalid arguments (malformed --tiers JSON, --account-currency-rate-vs-usd <= 0)\n"
            "  3  numeric error (--quote-rate-usd <= 0)\n"
            "  4  logic error (tiers not strictly ascending or final tier upper != null)\n"
        ),
    )
    parser.add_argument(
        '--self-test',
        action='store_true',
        help='Run built-in self-test cases and exit 0 if all pass.',
    )

    subparsers = parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND')
    p1 = subparsers.add_parser(
        'compute',
        help='Compute required margin across a tiered leverage curve.',
    )
    p1.add_argument('--volume-base-units', required=True, type=int)
    p1.add_argument('--quote-rate-usd', required=True, type=float)
    p1.add_argument('--tiers', required=True, type=str)
    p1.add_argument('--account-currency', default='USD')
    p1.add_argument('--account-currency-rate-vs-usd', type=float, default=1.0)

    return parser


def _handle_compute(args: argparse.Namespace) -> dict[str, Any]:
    """Dispatch handler for the `compute` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
    """
    if args.volume_base_units <= 0:
        _emit_error('--volume-base-units must be > 0', exit_code=EXIT_INVALID_ARGS)
    if not math.isfinite(args.quote_rate_usd) or args.quote_rate_usd <= 0:
        _emit_error('--quote-rate-usd must be a positive finite number', exit_code=EXIT_NUMERIC_ERROR)
    if not math.isfinite(args.account_currency_rate_vs_usd) or args.account_currency_rate_vs_usd <= 0:
        _emit_error(
            f'--account-currency-rate-vs-usd must be a positive finite number, got {args.account_currency_rate_vs_usd}',
            exit_code=EXIT_INVALID_ARGS,
        )
    try:
        tiers_raw = json.loads(args.tiers)
    except json.JSONDecodeError as exc:
        _emit_error(f'--tiers value is not valid JSON: {exc}', exit_code=EXIT_INVALID_ARGS)
    tiers = _validate_tiers(tiers_raw)
    quote_rate = Decimal(str(args.quote_rate_usd))
    account_rate = Decimal(str(args.account_currency_rate_vs_usd))
    return compute_margin(
        volume_base_units=args.volume_base_units,
        quote_rate_usd=quote_rate,
        tiers=tiers,
        account_currency=args.account_currency,
        account_currency_rate_vs_usd=account_rate,
    )


def _self_test() -> int:
    """Run canonical self-test cases.

    Returns:
        0 if all cases pass, 1 otherwise.
    """
    parser = _build_parser()
    cases: list[tuple[str, list[str], dict[str, Any], int]] = [
        (
            'EURUSD 1 000 000 @ 1.21345 across 3 tiers (SKILL.md §4 example)',
            [
                'compute',
                '--volume-base-units', '1000000',
                '--quote-rate-usd', '1.21345',
                '--tiers',
                (
                    '[{"upper":1000000,"leverage":500},'
                    '{"upper":5000000,"leverage":200},'
                    '{"upper":null,"leverage":100}]'
                ),
            ],
            {
                'margin_usd': 3067.25,
                'margin_account_ccy': 3067.25,
                'account_currency': 'USD',
                'account_currency_rate_vs_usd': 1.0,
                'notional_usd': 1213450.0,
            },
            0,
        ),
        (
            'XAUUSD 100 units @ 1900.50 spot, single-tier 1:100',
            [
                'compute',
                '--volume-base-units', '100',
                '--quote-rate-usd', '1900.50',
                '--tiers', '[{"upper":null,"leverage":100}]',
            ],
            {'margin_usd': 1900.5, 'notional_usd': 190050.0},
            0,
        ),
        (
            'US500 cash index 10 units @ 5000.0 spot, 2-tier curve',
            [
                'compute',
                '--volume-base-units', '10',
                '--quote-rate-usd', '5000.0',
                '--tiers', '[{"upper":100000,"leverage":20},{"upper":null,"leverage":10}]',
            ],
            {'margin_usd': 2500.0, 'notional_usd': 50000.0},
            0,
        ),
        (
            'edge: notional exactly equals first tier upper',
            [
                'compute',
                '--volume-base-units', '1000000',
                '--quote-rate-usd', '1.0',
                '--tiers', '[{"upper":1000000,"leverage":500},{"upper":null,"leverage":200}]',
            ],
            {'margin_usd': 2000.0, 'notional_usd': 1000000.0},
            0,
        ),
        (
            'edge: tier crossings 5 000 000 USD position',
            [
                'compute',
                '--volume-base-units', '5000000',
                '--quote-rate-usd', '1.0',
                '--tiers',
                (
                    '[{"upper":1000000,"leverage":500},'
                    '{"upper":5000000,"leverage":200},'
                    '{"upper":null,"leverage":100}]'
                ),
            ],
            {'margin_usd': 22000.0},
            0,
        ),
        (
            'edge: empty tiers rejected',
            [
                'compute',
                '--volume-base-units', '1000',
                '--quote-rate-usd', '1.0',
                '--tiers', '[]',
            ],
            {},
            EXIT_INVALID_ARGS,
        ),
        (
            'edge: malformed JSON rejected',
            [
                'compute',
                '--volume-base-units', '1000',
                '--quote-rate-usd', '1.0',
                '--tiers', '[{not-json',
            ],
            {},
            EXIT_INVALID_ARGS,
        ),
        (
            'edge: final tier upper != null rejected',
            [
                'compute',
                '--volume-base-units', '1000',
                '--quote-rate-usd', '1.0',
                '--tiers', '[{"upper":1000,"leverage":100}]',
            ],
            {},
            EXIT_LOGIC_ERROR,
        ),
        (
            'JPY account: EURUSD 1M @ 1.21345 * USDJPY=149.25 -> margin_jpy',
            [
                'compute',
                '--volume-base-units', '1000000',
                '--quote-rate-usd', '1.21345',
                '--account-currency', 'JPY',
                '--account-currency-rate-vs-usd', '149.25',
                '--tiers',
                (
                    '[{"upper":1000000,"leverage":500},'
                    '{"upper":5000000,"leverage":200},'
                    '{"upper":null,"leverage":100}]'
                ),
            ],
            {
                'margin_usd': 3067.25,
                'margin_account_ccy': 457787.0625,
                'account_currency': 'JPY',
                'account_currency_rate_vs_usd': 149.25,
            },
            0,
        ),
        (
            'EUR account: USD margin 2000 * EURUSD-inverse=0.92166 -> margin_eur',
            [
                'compute',
                '--volume-base-units', '1000000',
                '--quote-rate-usd', '1.0',
                '--account-currency', 'EUR',
                '--account-currency-rate-vs-usd', '0.92166',
                '--tiers',
                '[{"upper":1000000,"leverage":500},{"upper":null,"leverage":200}]',
            ],
            {
                'margin_usd': 2000.0,
                'margin_account_ccy': 1843.32,
                'account_currency': 'EUR',
            },
            0,
        ),
        (
            'edge: --account-currency-rate-vs-usd zero rejected',
            [
                'compute',
                '--volume-base-units', '1000',
                '--quote-rate-usd', '1.0',
                '--account-currency-rate-vs-usd', '0',
                '--tiers', '[{"upper":null,"leverage":100}]',
            ],
            {},
            EXIT_INVALID_ARGS,
        ),
        (
            'edge: --account-currency-rate-vs-usd negative rejected',
            [
                'compute',
                '--volume-base-units', '1000',
                '--quote-rate-usd', '1.0',
                '--account-currency-rate-vs-usd', '-1.5',
                '--tiers', '[{"upper":null,"leverage":100}]',
            ],
            {},
            EXIT_INVALID_ARGS,
        ),
    ]

    failures = 0
    for label, argv, expected, expected_exit in cases:
        try:
            args = parser.parse_args(argv)
            actual = _handle_compute(args)
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
                    float(act_val), exp_val, rel_tol=1e-6, abs_tol=1e-6,
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
    if args.subcommand == 'compute':
        payload = _handle_compute(args)
    else:
        parser.print_help(sys.stderr)
        return EXIT_INVALID_ARGS
    _emit_json(payload)
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
