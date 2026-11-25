# /// script
# requires-python = ">=3.11"
# ///

"""Estimate the margin of a position across a tiered leverage curve, in USD and in the account currency.

The tiers come from the broker's leverage table; no tool of the cTrader servers serves them, so the result is an
estimate. On the Local server ``calculate_margin`` returns the margin the product itself computes, in the account
currency, and that figure outranks this estimate.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections.abc import Mapping
from contextlib import redirect_stderr
from contextlib import redirect_stdout
from decimal import Decimal
from decimal import InvalidOperation
from decimal import getcontext
from typing import NoReturn
from typing import TypeAlias
from typing import cast

getcontext().prec = 28

EXIT_OK = 0
EXIT_INVALID_ARGS = 2
EXIT_NUMERIC_ERROR = 3
EXIT_LOGIC_ERROR = 4

Tier: TypeAlias = tuple[int | None, int]
"""The upper bound of a tier's notional in USD, ``None`` for the last tier, and the tier's leverage."""

SelfTestCase: TypeAlias = (
    tuple[str, list[str], Mapping[str, object], int] | tuple[str, list[str], Mapping[str, object], int, Mapping[str, object]]
)
"""One case of the case table: label, arguments, expected values, exit code and, optionally, checks."""

SELF_TEST_CASES: tuple[SelfTestCase, ...] = (
    (
        'one tier: 1000 units at 1.098 and leverage 100 in a EUR account at 0.91075 (1/1.098) is a margin of 10',
        [
            'compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.098',
            '--tiers', '[{"upper":null,"leverage":100}]',
            '--account-currency', 'EUR', '--account-currency-rate-vs-usd', '0.91075',
        ],
        {'margin_usd': 10.98, 'margin_account_ccy': 10, 'account_currency': 'EUR'},
        0,
        {'tolerance': 0.005},
    ),
    (
        'a decimal volume: 0.01 unit at 61981.59 with one made-up tier at leverage 2 is a margin of 309.90795',
        ['compute', '--volume-base-units', '0.01', '--quote-rate-usd', '61981.59', '--tiers', '[{"upper":null,"leverage":2}]'],
        {'margin_usd': 309.90795, 'notional_usd': 619.8159},
        0,
    ),
    (
        'three tiers: 1000000 units at 1.21345 absorb the notional tier by tier into a margin of 3067.25',
        [
            'compute', '--volume-base-units', '1000000', '--quote-rate-usd', '1.21345', '--tiers',
            '[{"upper":1000000,"leverage":500},{"upper":5000000,"leverage":200},{"upper":null,"leverage":100}]',
        ],
        {
            'margin_usd': 3067.25,
            'margin_account_ccy': 3067.25,
            'account_currency': 'USD',
            'account_currency_rate_vs_usd': 1,
            'notional_usd': 1213450,
        },
        0,
    ),
    (
        'a notional equal to the bound of the first tier stays in that tier',
        [
            'compute', '--volume-base-units', '1000000', '--quote-rate-usd', '1.0', '--tiers',
            '[{"upper":1000000,"leverage":500},{"upper":null,"leverage":200}]',
        ],
        {
            'margin_usd': 2000,
            'notional_usd': 1000000,
            'per_tier_breakdown': [{'upper': 1000000, 'leverage': 500, 'absorbed_usd': 1000000, 'tier_margin_usd': 2000}],
        },
        0,
    ),
    (
        'a notional across every tier: 5000000 at 1.0 is a margin of 22000',
        [
            'compute', '--volume-base-units', '5000000', '--quote-rate-usd', '1.0', '--tiers',
            '[{"upper":1000000,"leverage":500},{"upper":5000000,"leverage":200},{"upper":null,"leverage":100}]',
        ],
        {'margin_usd': 22000},
        0,
    ),
    (
        'a volume that is not above 0 is refused',
        ['compute', '--volume-base-units', '0', '--quote-rate-usd', '1.0', '--tiers', '[{"upper":null,"leverage":100}]'],
        {'error': '--volume-base-units must be > 0'},
        2,
    ),
    (
        'an empty tier list is refused',
        ['compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.0', '--tiers', '[]'],
        {'error': '--tiers must be a non-empty JSON list'},
        2,
    ),
    (
        'tiers that are not JSON are refused',
        ['compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.0', '--tiers', '[{not-json'],
        {},
        2,
    ),
    (
        'a last tier with an upper bound is refused',
        ['compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.0', '--tiers', '[{"upper":1000,"leverage":100}]'],
        {'error': "final tier must have 'upper': null (covers all exposure above the last finite bound)"},
        4,
    ),
    (
        'an account rate that is not above 0 is refused',
        [
            'compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.0', '--account-currency-rate-vs-usd', '0',
            '--tiers', '[{"upper":null,"leverage":100}]',
        ],
        {},
        2,
    ),
    (
        'an account currency other than USD without its rate is refused',
        [
            'compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.098', '--account-currency', 'EUR',
            '--tiers', '[{"upper":null,"leverage":100}]',
        ],
        {'error': '--account-currency-rate-vs-usd is required when --account-currency is not USD'},
        2,
    ),
    (
        'a rate other than 1 with a USD account given as such is refused',
        [
            'compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.098', '--account-currency', 'USD',
            '--account-currency-rate-vs-usd', '0.91075', '--tiers', '[{"upper":null,"leverage":100}]',
        ],
        {'error': '--account-currency-rate-vs-usd must be 1 when --account-currency is USD, got 0.91075'},
        2,
    ),
    (
        'a rate other than 1 with the default USD account is refused',
        [
            'compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.098', '--account-currency-rate-vs-usd', '0.91075',
            '--tiers', '[{"upper":null,"leverage":100}]',
        ],
        {'error': '--account-currency-rate-vs-usd must be 1 when --account-currency is USD, got 0.91075'},
        2,
    ),
    (
        'a rate of 1 with a USD account is accepted: the margin in the account currency is the margin in USD',
        [
            'compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.098', '--account-currency', 'USD',
            '--account-currency-rate-vs-usd', '1.0', '--tiers', '[{"upper":null,"leverage":100}]',
        ],
        {'margin_usd': 10.98, 'margin_account_ccy': 10.98, 'account_currency': 'USD', 'account_currency_rate_vs_usd': 1},
        0,
    ),
    (
        'a volume that is not a number is refused, with the usage on stderr only',
        ['compute', '--volume-base-units', 'abc', '--quote-rate-usd', '1.0', '--tiers', '[{"upper":null,"leverage":100}]'],
        {},
        2,
        {'absent': ['error']},
    ),
    (
        'a volume that is not finite is refused',
        ['compute', '--volume-base-units', 'inf', '--quote-rate-usd', '1.0', '--tiers', '[{"upper":null,"leverage":100}]'],
        {'error': '--volume-base-units must be finite'},
        3,
    ),
    (
        'a quote rate that is not above 0 is refused',
        ['compute', '--volume-base-units', '1000', '--quote-rate-usd', '0', '--tiers', '[{"upper":null,"leverage":100}]'],
        {'error': '--quote-rate-usd must be a positive finite number'},
        3,
    ),
    (
        'a tier that is not an object is refused',
        ['compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.0', '--tiers', '[100]'],
        {'error': "--tiers[0] must be an object with 'upper' and 'leverage' keys"},
        2,
    ),
    (
        'a tier without an upper bound is refused',
        ['compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.0', '--tiers', '[{"leverage":100}]'],
        {'error': "--tiers[0] missing 'upper' or 'leverage' key"},
        2,
    ),
    (
        'an open tier before the last is refused',
        [
            'compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.0',
            '--tiers', '[{"upper":null,"leverage":100},{"upper":null,"leverage":50}]',
        ],
        {'error': "--tiers[0] has 'upper': null but is not the final tier"},
        4,
    ),
    (
        'an upper bound that is not a whole number is refused',
        [
            'compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.0',
            '--tiers', '[{"upper":1000.5,"leverage":100},{"upper":null,"leverage":50}]',
        ],
        {'error': "--tiers[0] 'upper' must be an integer or null, got float"},
        2,
    ),
    (
        'an upper bound that is not above 0 is refused',
        [
            'compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.0',
            '--tiers', '[{"upper":0,"leverage":100},{"upper":null,"leverage":50}]',
        ],
        {'error': "--tiers[0] 'upper' must be > 0 when not null"},
        2,
    ),
    (
        'an upper bound equal to the one before is refused: the bounds rise strictly',
        [
            'compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.0',
            '--tiers', '[{"upper":1000,"leverage":500},{"upper":1000,"leverage":200},{"upper":null,"leverage":100}]',
        ],
        {'error': "--tiers[1] 'upper' must be strictly greater than previous tier's upper"},
        4,
    ),
    (
        'a leverage that is not a whole number is refused',
        ['compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.0', '--tiers', '[{"upper":null,"leverage":2.5}]'],
        {'error': "--tiers[0] 'leverage' must be an integer, got float"},
        2,
    ),
    (
        'a leverage that is not above 0 is refused',
        ['compute', '--volume-base-units', '1000', '--quote-rate-usd', '1.0', '--tiers', '[{"upper":null,"leverage":0}]'],
        {'error': "--tiers[0] 'leverage' must be > 0"},
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


def _emit_json(payload: dict[str, object]) -> None:
    """Write an answer to stdout as one line of JSON.

    Args:
        payload: The answer.
    """
    json.dump(payload, sys.stdout, separators=(',', ':'), ensure_ascii=True)
    sys.stdout.write('\n')
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
    json.dump({'error': message}, sys.stdout, separators=(',', ':'), ensure_ascii=True)
    sys.stdout.write('\n')
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


def _validate_tiers(tiers: object) -> list[Tier]:
    """Read the tiers of ``--tiers``, refusing a list out of order or without an open last tier.

    Args:
        tiers: The parsed JSON value.

    Returns:
        The upper bound and the leverage of each tier, in order.
    """
    if not isinstance(tiers, list) or len(tiers) == 0:
        _emit_error('--tiers must be a non-empty JSON list', exit_code=EXIT_INVALID_ARGS)
    rows = cast('list[object]', tiers)
    normalized: list[Tier] = []
    last_upper = 0
    for idx, raw in enumerate(rows):
        if not isinstance(raw, dict):
            _emit_error(f"--tiers[{idx}] must be an object with 'upper' and 'leverage' keys", exit_code=EXIT_INVALID_ARGS)
        tier = cast('dict[str, object]', raw)
        if 'upper' not in tier or 'leverage' not in tier:
            _emit_error(f"--tiers[{idx}] missing 'upper' or 'leverage' key", exit_code=EXIT_INVALID_ARGS)
        upper_raw = tier['upper']
        leverage = tier['leverage']
        if upper_raw is None:
            if idx != len(rows) - 1:
                _emit_error(f"--tiers[{idx}] has 'upper': null but is not the final tier", exit_code=EXIT_LOGIC_ERROR)
            upper = None
        else:
            if not isinstance(upper_raw, int) or isinstance(upper_raw, bool):
                _emit_error(
                    f"--tiers[{idx}] 'upper' must be an integer or null, got {type(upper_raw).__name__}",
                    exit_code=EXIT_INVALID_ARGS,
                )
            if upper_raw <= 0:
                _emit_error(f"--tiers[{idx}] 'upper' must be > 0 when not null", exit_code=EXIT_INVALID_ARGS)
            if upper_raw <= last_upper:
                _emit_error(
                    f"--tiers[{idx}] 'upper' must be strictly greater than previous tier's upper",
                    exit_code=EXIT_LOGIC_ERROR,
                )
            upper = last_upper = upper_raw
        if not isinstance(leverage, int) or isinstance(leverage, bool):
            _emit_error(
                f"--tiers[{idx}] 'leverage' must be an integer, got {type(leverage).__name__}",
                exit_code=EXIT_INVALID_ARGS,
            )
        if leverage <= 0:
            _emit_error(f"--tiers[{idx}] 'leverage' must be > 0", exit_code=EXIT_INVALID_ARGS)
        normalized.append((upper, leverage))
    if normalized[-1][0] is not None:
        _emit_error(
            "final tier must have 'upper': null (covers all exposure above the last finite bound)",
            exit_code=EXIT_LOGIC_ERROR,
        )
    return normalized


def compute_margin(
    volume_base_units: Decimal,
    quote_rate_usd: Decimal,
    tiers: list[Tier],
    account_currency: str,
    account_currency_rate_vs_usd: Decimal,
) -> dict[str, object]:
    """Estimate the margin of a position across the tiers, in USD and in the account currency.

    The notional in USD is the volume times the USD price of one unit. Each tier in turn absorbs the part of the
    notional up to its upper bound and adds that part divided by its leverage to the margin.

    Args:
        volume_base_units: The size in units of the base asset; decimals are allowed.
        quote_rate_usd: The price of one unit of the base asset in USD, a display price.
        tiers: The upper bound and the leverage of each tier, in order, the last one open.
        account_currency: The currency of the account, such as EUR.
        account_currency_rate_vs_usd: The amount of the account currency one USD buys.

    Returns:
        The margin in USD and in the account currency, the account currency and its rate, the margin of each tier
        reached, and the notional in USD.
    """
    notional_usd = volume_base_units * quote_rate_usd
    remaining = notional_usd
    cursor = Decimal(0)
    margin_total = Decimal(0)
    breakdown: list[dict[str, object]] = []
    for upper, leverage in tiers:
        absorbed = remaining if upper is None else max(min(Decimal(upper) - cursor, remaining), Decimal(0))
        tier_margin = absorbed / leverage
        margin_total += tier_margin
        breakdown.append(
            {'upper': upper, 'leverage': leverage, 'absorbed_usd': float(absorbed), 'tier_margin_usd': float(tier_margin)}
        )
        remaining -= absorbed
        if upper is not None:
            cursor = Decimal(upper)
        if remaining <= 0:
            break
    return {
        'margin_usd': float(margin_total),
        'margin_account_ccy': float(margin_total * account_currency_rate_vs_usd),
        'account_currency': account_currency,
        'account_currency_rate_vs_usd': float(account_currency_rate_vs_usd),
        'per_tier_breakdown': breakdown,
        'notional_usd': float(notional_usd),
    }


EPILOG = """\
Run it as python3 <skill folder>/scripts/tiered_margin.py on macOS and Linux, and as
python <skill folder>/scripts/tiered_margin.py on Windows (py in place of python where python is not on the path).

Examples:
  python3 <skill folder>/scripts/tiered_margin.py compute --volume-base-units 1000 --quote-rate-usd 1.098 \\
      --tiers '[{"upper":null,"leverage":100}]'
  python3 <skill folder>/scripts/tiered_margin.py compute --volume-base-units 0.01 --quote-rate-usd 61981.59 \\
      --account-currency EUR --account-currency-rate-vs-usd 0.91075 --tiers '[{"upper":null,"leverage":2}]'
  python3 <skill folder>/scripts/tiered_margin.py --self-test

--volume-base-units is the size in units of the base asset; decimals are allowed.
--quote-rate-usd is a display price: the price of one unit of the base asset in USD, which for a symbol quoted in
USD is its price.
--tiers is the broker's leverage table as a JSON list of {"upper": <USD notional or null>, "leverage": <int>}, in
ascending order, the last tier open with "upper": null. No tool of either server serves it.
--account-currency-rate-vs-usd is the amount of the account currency one USD buys. It is required when
--account-currency is not USD, and is 1 for a USD account: a USD account takes no other rate.

The result is an estimate: on the Local server, calculate_margin returns the product's own margin in the account
currency, and that figure outranks this one.

Every answer is one line of JSON on stdout. A refusal writes "error: <reason>" on stderr and {"error": "<reason>"} on
stdout. Exit codes: 0 success, 2 invalid input, 3 a value that is not finite or a quote rate that is not above 0,
4 tiers out of order or without an open last tier. --self-test runs the script's own cases and exits 0 when every case
holds, 1 otherwise.
"""


def _build_parser() -> argparse.ArgumentParser:
    """Build the parser of the command line.

    Returns:
        The parser, with the subparser of ``compute``.
    """
    parser = argparse.ArgumentParser(
        prog='tiered_margin.py',
        description='Estimate the margin of a position across a tiered leverage curve.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument('--self-test', action='store_true', help="Run the script's own cases; exit 0 when all hold.")
    subparsers = parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND')
    compute = subparsers.add_parser('compute', help='Margin across the tiers, in USD and in the account currency.')
    compute.add_argument('--volume-base-units', type=_number, required=True, help='The size in units of the base asset.')
    compute.add_argument('--quote-rate-usd', type=_number, required=True, help='The USD price of one unit, a display price.')
    compute.add_argument('--tiers', required=True, type=str, help="The broker's leverage table, as JSON.")
    compute.add_argument('--account-currency', default='USD', help='The currency of the account (default: USD).')
    compute.add_argument(
        '--account-currency-rate-vs-usd',
        type=_number,
        default=None,
        help='The amount of the account currency one USD buys; required when the account currency is not USD, 1 when it is.',
    )
    return parser


def _handle_compute(args: argparse.Namespace) -> dict[str, object]:
    """Answer ``compute``.

    Args:
        args: The parsed arguments.

    Returns:
        The estimate.
    """
    volume = args.volume_base_units
    if not volume.is_finite():
        _emit_error('--volume-base-units must be finite', exit_code=EXIT_NUMERIC_ERROR)
    if volume <= 0:
        _emit_error('--volume-base-units must be > 0', exit_code=EXIT_INVALID_ARGS)
    if not args.quote_rate_usd.is_finite() or args.quote_rate_usd <= 0:
        _emit_error('--quote-rate-usd must be a positive finite number', exit_code=EXIT_NUMERIC_ERROR)
    account_rate: Decimal | None = args.account_currency_rate_vs_usd
    usd_account = args.account_currency.upper() == 'USD'
    if account_rate is None:
        if not usd_account:
            _emit_error(
                '--account-currency-rate-vs-usd is required when --account-currency is not USD',
                exit_code=EXIT_INVALID_ARGS,
            )
        account_rate = Decimal(1)
    if not account_rate.is_finite() or account_rate <= 0:
        _emit_error(
            f'--account-currency-rate-vs-usd must be a positive finite number, got {account_rate}',
            exit_code=EXIT_INVALID_ARGS,
        )
    if usd_account and account_rate != 1:
        _emit_error(
            f'--account-currency-rate-vs-usd must be 1 when --account-currency is USD, got {account_rate}',
            exit_code=EXIT_INVALID_ARGS,
        )
    try:
        tiers_raw = json.loads(args.tiers)
    except json.JSONDecodeError as exc:
        _emit_error(f'--tiers value is not valid JSON: {exc}', exit_code=EXIT_INVALID_ARGS)
    return compute_margin(
        volume_base_units=volume,
        quote_rate_usd=args.quote_rate_usd,
        tiers=_validate_tiers(tiers_raw),
        account_currency=args.account_currency,
        account_currency_rate_vs_usd=account_rate,
    )


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
    _emit_json(_handle_compute(args))
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
