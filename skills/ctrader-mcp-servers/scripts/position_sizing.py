# /// script
# requires-python = ">=3.11"
# ///

"""Size an order from a risk target and the distance to its stop.

The size follows from the price distance alone: ``units = risk / (stop distance x conversion rate)``, because the profit
or loss in the quote currency is the price move times the units. The lot size only expresses the result in lots. Nothing
is rounded to the volume step or clipped to the limits: given the grid, the answer reports where the size lies on it.
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
        'the size follows from the stop distance: 2 percent of a made-up 5000 over 100 pips of 0.01 is 100 units, 1 lot',
        [
            'from-risk-percent', '--balance', '5000', '--risk-pct', '2',
            '--sl-pips', '100', '--pip-size', '0.01', '--conversion-rate', '1', '--lot-size', '100',
        ],
        {'units': 100, 'lots': 1, 'cents': 10000, 'cents_rounded_down': False, 'risk_currency_amount': 100},
        0,
        {'absent': ['warnings', 'on_grid', 'below', 'above']},
    ),
    (
        'a stop distance in price gives the same size: 1.00 in place of 100 pips of 0.01',
        [
            'from-risk-percent', '--balance', '5000', '--risk-pct', '2', '--price-distance', '1.00',
            '--conversion-rate', '1', '--lot-size', '100',
        ],
        {'units': 100, 'lots': 1, 'cents': 10000},
        0,
    ),
    (
        'the lot size is required: no default stands in for it',
        [
            'from-risk-percent', '--balance', '5000', '--risk-pct', '2', '--sl-pips', '100', '--pip-size', '0.01',
            '--conversion-rate', '1',
        ],
        {},
        2,
    ),
    (
        'the conversion rate is required: no default stands in for it',
        [
            'from-risk-percent', '--balance', '5000', '--risk-pct', '2', '--sl-pips', '100', '--pip-size', '0.01',
            '--lot-size', '100',
        ],
        {},
        2,
        {'absent': ['error']},
    ),
    (
        'the conversion rate is required by from-risk-amount as well',
        ['from-risk-amount', '--risk-amount', '100', '--price-distance', '1.00', '--lot-size', '100'],
        {},
        2,
        {'absent': ['error']},
    ),
    (
        'with the grid it reports the nearest grid sizes with their risk and rounds nothing: 1 percent of 10000 over 30 pips',
        [
            'from-risk-percent', '--balance', '10000', '--risk-pct', '1', '--sl-pips', '30', '--pip-size', '0.0001',
            '--conversion-rate', '1', '--lot-size', '100000',
            '--min-volume', '1000', '--max-volume', '10000000', '--volume-step', '1000',
        ],
        {
            'units': 33333.333,
            'lots': 0.3333,
            'cents': 3333333,
            'cents_rounded_down': True,
            'risk_currency_amount': 100,
            'on_grid': False,
            'within_limits': True,
            'below': {'units': 33000, 'lots': 0.33, 'risk_currency_amount': 99},
            'above': {'units': 34000, 'lots': 0.34, 'risk_currency_amount': 102},
        },
        0,
        {'tolerance': 0.001},
    ),
    (
        'without the grid the same call gives the same units, lots and cents',
        [
            'from-risk-percent', '--balance', '10000', '--risk-pct', '1', '--sl-pips', '30', '--pip-size', '0.0001',
            '--conversion-rate', '1', '--lot-size', '100000',
        ],
        {'units': 33333.333, 'lots': 0.3333, 'cents': 3333333, 'cents_rounded_down': True},
        0,
        {'tolerance': 0.001, 'absent': ['on_grid', 'within_limits', 'below', 'above']},
    ),
    (
        'decimal pips enter the formula: a risk of 0.328 over 32.8 pips of 0.0001 is 100 units',
        [
            'from-risk-amount', '--risk-amount', '0.328', '--sl-pips', '32.8', '--pip-size', '0.0001',
            '--conversion-rate', '1', '--lot-size', '100000',
        ],
        {'units': 100, 'lots': 0.001, 'cents': 10000, 'cents_rounded_down': False},
        0,
    ),
    (
        'a size below the minimum stays as computed: outside the limits, no grid size below it, the minimum above it',
        [
            'from-risk-amount', '--risk-amount', '0.3', '--sl-pips', '30', '--pip-size', '0.0001',
            '--conversion-rate', '1', '--lot-size', '100000',
            '--min-volume', '1000', '--max-volume', '10000000', '--volume-step', '1000',
        ],
        {
            'units': 100,
            'within_limits': False,
            'below': None,
            'above': {'units': 1000, 'lots': 0.01, 'risk_currency_amount': 3},
        },
        0,
    ),
    (
        'a cross-currency risk divides by the conversion rate: 100 over 30 pips of 0.0001 at 0.91075 (1/1.098) is 36599.87',
        [
            'from-risk-amount', '--risk-amount', '100', '--sl-pips', '30', '--pip-size', '0.0001',
            '--conversion-rate', '0.91075', '--lot-size', '100000',
        ],
        {'units': 36599.87},
        0,
        {'tolerance': 0.01},
    ),
    (
        'the stop distance is given in pips or in price, not both',
        [
            'from-risk-amount', '--risk-amount', '100', '--sl-pips', '30', '--pip-size', '0.0001',
            '--price-distance', '0.003', '--conversion-rate', '1', '--lot-size', '100000',
        ],
        {},
        2,
    ),
    (
        '--sl-pips needs --pip-size',
        ['from-risk-amount', '--risk-amount', '100', '--sl-pips', '30', '--conversion-rate', '1', '--lot-size', '100000'],
        {'error': '--sl-pips needs --pip-size'},
        2,
    ),
    (
        'a pip size goes with --sl-pips only',
        [
            'from-risk-amount', '--risk-amount', '100', '--price-distance', '0.003', '--pip-size', '0.0001',
            '--conversion-rate', '1', '--lot-size', '100000',
        ],
        {'error': '--pip-size goes with --sl-pips only'},
        2,
    ),
    (
        'the grid is given whole or not at all',
        [
            'from-risk-amount', '--risk-amount', '100', '--price-distance', '0.003',
            '--conversion-rate', '1', '--lot-size', '100000', '--min-volume', '1000', '--volume-step', '1000',
        ],
        {'error': '--min-volume, --max-volume and --volume-step go together'},
        2,
    ),
    (
        'a grid minimum below 0 is refused',
        [
            'from-risk-amount', '--risk-amount', '100', '--price-distance', '0.003',
            '--conversion-rate', '1', '--lot-size', '100000', '--min-volume', '-1', '--max-volume', '10000000',
            '--volume-step', '1000',
        ],
        {'error': '--min-volume must be 0 or more, got -1'},
        2,
    ),
    (
        'a grid maximum below its minimum is refused',
        [
            'from-risk-amount', '--risk-amount', '100', '--price-distance', '0.003',
            '--conversion-rate', '1', '--lot-size', '100000', '--min-volume', '2000', '--max-volume', '1000',
            '--volume-step', '1000',
        ],
        {'error': '--max-volume must not be below --min-volume'},
        2,
    ),
    (
        'a balance that is not above 0 is refused',
        [
            'from-risk-percent', '--balance', '0', '--risk-pct', '1', '--price-distance', '0.003',
            '--conversion-rate', '1', '--lot-size', '100000',
        ],
        {'error': '--balance must be above 0, got 0'},
        2,
    ),
    (
        'a balance that is not a number is refused, with the usage on stderr only',
        [
            'from-risk-percent', '--balance', 'abc', '--risk-pct', '1', '--price-distance', '0.003',
            '--conversion-rate', '1', '--lot-size', '100000',
        ],
        {},
        2,
        {'absent': ['error']},
    ),
    (
        'a risk percent of 100 or more is refused',
        [
            'from-risk-percent', '--balance', '5000', '--risk-pct', '100', '--price-distance', '0.003',
            '--conversion-rate', '1', '--lot-size', '100000',
        ],
        {'error': '--risk-pct must be above 0 and below 100, got 100'},
        2,
    ),
    (
        'a risk amount that is not finite is refused',
        [
            'from-risk-amount', '--risk-amount', 'inf', '--price-distance', '0.003',
            '--conversion-rate', '1', '--lot-size', '100000',
        ],
        {'error': '--risk-amount must be finite'},
        3,
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


def size_from_risk(risk: Decimal, stop_distance: Decimal, conversion_rate: Decimal) -> Decimal:
    """Return the size that loses the risk amount when the price moves by the stop distance.

    Args:
        risk: The risk amount, in the account currency.
        stop_distance: The distance between the entry price and the stop price, in display price.
        conversion_rate: The price of one unit of the quote currency in the account currency.

    Returns:
        The size in units of the base asset.
    """
    return risk / (stop_distance * conversion_rate)


def risk_at(units: Decimal, stop_distance: Decimal, conversion_rate: Decimal) -> Decimal:
    """Return what a size loses when the price moves by the stop distance.

    Args:
        units: The size in units of the base asset.
        stop_distance: The distance between the entry price and the stop price, in display price.
        conversion_rate: The price of one unit of the quote currency in the account currency.

    Returns:
        The loss, in the account currency.
    """
    return units * stop_distance * conversion_rate


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


def size_order(
    risk: Decimal,
    stop_distance: Decimal,
    conversion_rate: Decimal,
    lot_size: Decimal,
    grid: tuple[Decimal, Decimal, Decimal] | None,
) -> Answer:
    """Size an order and, given the grid, report where the size lies on it.

    Args:
        risk: The risk amount, in the account currency.
        stop_distance: The distance between the entry price and the stop price, in display price.
        conversion_rate: The price of one unit of the quote currency in the account currency.
        lot_size: The units in one lot.
        grid: The smallest size, the largest size and the step, in units, or ``None``.

    Returns:
        The exact size in units and lots, the Remote volume rounded down to a whole number, whether that rounding
        changed it, and the risk at the size; with the grid also whether the size lies on it and within the limits, and
        the nearest grid sizes below and above it with their risk.
    """
    units = size_from_risk(risk, stop_distance, conversion_rate)
    exact_cents = units * 100
    cents = exact_cents.to_integral_value(rounding=ROUND_FLOOR)
    answer: Answer = {
        'units': units,
        'lots': units / lot_size,
        'cents': cents,
        'cents_rounded_down': cents != exact_cents,
        'risk_currency_amount': risk_at(units, stop_distance, conversion_rate),
    }
    if grid is None:
        return answer
    minimum, maximum, step = grid
    on_grid = units % step == 0
    neighbors = (None, None) if on_grid else grid_neighbors(units, minimum, maximum, step)
    answer['on_grid'] = on_grid
    answer['within_limits'] = minimum <= units <= maximum
    for key, size in zip(('below', 'above'), neighbors, strict=True):
        if size is None:
            answer[key] = None
        else:
            answer[key] = {
                'units': size,
                'lots': size / lot_size,
                'risk_currency_amount': risk_at(size, stop_distance, conversion_rate),
            }
    return answer


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
        value: The value: an object, a decimal, an integer, a boolean, a string or ``None``.

    Returns:
        The JSON text, ASCII only, with no space after a separator.
    """
    if isinstance(value, dict):
        return '{' + ','.join(f'{json.dumps(key)}:{_json(item)}' for key, item in value.items()) + '}'
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


def _stop_distance(args: argparse.Namespace) -> Decimal:
    """Read the stop distance from either of its two forms.

    Args:
        args: The parsed arguments.

    Returns:
        The distance in display price.
    """
    if args.sl_pips is not None:
        if args.pip_size is None:
            _emit_error('--sl-pips needs --pip-size', exit_code=EXIT_INVALID_ARGS)
        return _positive(args.sl_pips, '--sl-pips') * _positive(args.pip_size, '--pip-size')
    if args.pip_size is not None:
        _emit_error('--pip-size goes with --sl-pips only', exit_code=EXIT_INVALID_ARGS)
    return _positive(args.price_distance, '--price-distance')


def _grid(args: argparse.Namespace) -> tuple[Decimal, Decimal, Decimal] | None:
    """Read the volume grid, given whole or not at all.

    Args:
        args: The parsed arguments.

    Returns:
        The smallest size, the largest size and the step, or ``None`` when none of the three is given.
    """
    given = [args.min_volume, args.max_volume, args.volume_step]
    if all(value is None for value in given):
        return None
    if any(value is None for value in given):
        _emit_error('--min-volume, --max-volume and --volume-step go together', exit_code=EXIT_INVALID_ARGS)
    minimum = _finite(args.min_volume, '--min-volume')
    if minimum < 0:
        _emit_error(f'--min-volume must be 0 or more, got {_plain(minimum)}', exit_code=EXIT_INVALID_ARGS)
    maximum = _positive(args.max_volume, '--max-volume')
    if maximum < minimum:
        _emit_error('--max-volume must not be below --min-volume', exit_code=EXIT_INVALID_ARGS)
    return minimum, maximum, _positive(args.volume_step, '--volume-step')


def _size(args: argparse.Namespace, risk: Decimal) -> Answer:
    """Size an order for a risk amount from the shared arguments.

    Args:
        args: The parsed arguments.
        risk: The risk amount, in the account currency.

    Returns:
        The answer.
    """
    return size_order(
        risk,
        _stop_distance(args),
        _positive(args.conversion_rate, '--conversion-rate'),
        _positive(args.lot_size, '--lot-size'),
        _grid(args),
    )


def _handle_from_risk_percent(args: argparse.Namespace) -> Answer:
    """Answer ``from-risk-percent``.

    Args:
        args: The parsed arguments.

    Returns:
        The answer.
    """
    balance = _positive(args.balance, '--balance')
    percent = _finite(args.risk_pct, '--risk-pct')
    if not 0 < percent < 100:
        _emit_error(f'--risk-pct must be above 0 and below 100, got {_plain(percent)}', exit_code=EXIT_INVALID_ARGS)
    return _size(args, balance * percent / 100)


def _handle_from_risk_amount(args: argparse.Namespace) -> Answer:
    """Answer ``from-risk-amount``.

    Args:
        args: The parsed arguments.

    Returns:
        The answer.
    """
    return _size(args, _positive(args.risk_amount, '--risk-amount'))


EPILOG = """\
Run it as python3 <skill folder>/scripts/position_sizing.py on macOS and Linux, and as
python <skill folder>/scripts/position_sizing.py on Windows (py in place of python where python is not on the path).

Examples:
  python3 <skill folder>/scripts/position_sizing.py from-risk-percent --balance 5000 --risk-pct 2 \\
      --sl-pips 100 --pip-size 0.01 --conversion-rate 1 --lot-size 100
  python3 <skill folder>/scripts/position_sizing.py from-risk-amount --risk-amount 100 --price-distance 1.00 \\
      --conversion-rate 1 --lot-size 100
  python3 <skill folder>/scripts/position_sizing.py --self-test

Inputs:
  --balance and --risk-amount are in the account currency. On the Remote server, scale the balance of get_balance
  first: balance / 10^moneyDigits. The Local server returns the balance in the account currency.
  The stop distance takes one of two forms: --sl-pips with --pip-size (pipSize of get_symbol_details on the Local
  server), or --price-distance, the distance between the entry price and the stop price in display price.
  --conversion-rate is required: the price of one unit of the quote currency in the account currency, 1 when the two are
  the same currency.
  --lot-size, in units, only expresses the size in lots.
  --min-volume, --max-volume and --volume-step (get_symbol_details, in units) go together or not at all.
  Every price is a display price.

Outputs: units and lots, exact; cents, the Remote volume (units x 100) rounded down to a whole number so that the
risk stays at or below the target, with cents_rounded_down; risk_currency_amount, the risk at units. With the grid
also on_grid, within_limits, and below and above, the nearest grid sizes within the limits with their risk.
Nothing is rounded to the step or clipped to the limits: ask the user about a size off the grid or outside them.

Every answer is one line of JSON on stdout. A refusal writes "error: <reason>" on stderr and {"error": "<reason>"} on
stdout. Exit codes: 0 success, 2 invalid input, 3 a value that is not finite. --self-test runs the script's own cases
and exits 0 when every case holds, 1 otherwise.
"""


def _add_common(parser: argparse.ArgumentParser) -> None:
    """Add the arguments both subcommands share.

    Args:
        parser: The parser of a subcommand.
    """
    stop = parser.add_mutually_exclusive_group(required=True)
    stop.add_argument('--sl-pips', type=_number, help='The stop distance in pips; needs --pip-size.')
    stop.add_argument('--price-distance', type=_number, help='The stop distance in display price.')
    parser.add_argument('--pip-size', type=_number, help='Price of one pip: pipSize of get_symbol_details (Local).')
    parser.add_argument(
        '--conversion-rate',
        type=_number,
        required=True,
        help='Price of one unit of the quote currency in the account currency; 1 when the two are the same currency.',
    )
    parser.add_argument('--lot-size', type=_number, required=True, help='Units in one lot; expresses the size in lots.')
    parser.add_argument('--min-volume', type=_number, help='minVolume of get_symbol_details, in units.')
    parser.add_argument('--max-volume', type=_number, help='maxVolume of get_symbol_details, in units.')
    parser.add_argument('--volume-step', type=_number, help='volumeStep of get_symbol_details, in units.')


def _build_parser() -> argparse.ArgumentParser:
    """Build the parser of the command line.

    Returns:
        The parser, with one subparser per subcommand.
    """
    parser = argparse.ArgumentParser(
        prog='position_sizing.py',
        description='Size an order from a risk target and the distance to its stop.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument('--self-test', action='store_true', help="Run the script's own cases; exit 0 when all hold.")
    subparsers = parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND')

    percent = subparsers.add_parser('from-risk-percent', help='Size from a percentage of the balance.')
    percent.add_argument('--balance', type=_number, required=True, help='The balance, in the account currency.')
    percent.add_argument('--risk-pct', type=_number, required=True, help='The percentage of the balance to risk.')
    _add_common(percent)
    percent.set_defaults(handler=_handle_from_risk_percent)

    amount = subparsers.add_parser('from-risk-amount', help='Size from a risk amount in the account currency.')
    amount.add_argument('--risk-amount', type=_number, required=True, help='The amount to risk, in the account currency.')
    _add_common(amount)
    amount.set_defaults(handler=_handle_from_risk_amount)
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
