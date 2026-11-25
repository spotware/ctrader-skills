# /// script
# requires-python = ">=3.11"
# ///

"""Convert between pip distances and display prices, and express a distance in the units the order fields take.

Every price here is a display price, the number a trader reads, on both cTrader servers. The quotes of the Remote server
are integers in 1/100000 of the price: convert them with ``units_encoding.py quote-to-price`` first.
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
from decimal import ROUND_FLOOR
from decimal import ROUND_HALF_UP
from decimal import Decimal
from decimal import InvalidOperation
from decimal import getcontext
from typing import NoReturn
from typing import TypeAlias

getcontext().prec = 28

EXIT_OK = 0
EXIT_INVALID_ARGS = 2
EXIT_NUMERIC_ERROR = 3

SIDES = ('buy', 'sell')
DIRECTIONS = ('sl', 'tp')

Answer: TypeAlias = dict[str, object]
"""The object a subcommand prints."""

SelfTestCase: TypeAlias = (
    tuple[str, list[str], Mapping[str, object], int] | tuple[str, list[str], Mapping[str, object], int, Mapping[str, object]]
)
"""One case of the case table: label, arguments, expected values, exit code and, optionally, checks."""

SELF_TEST_CASES: tuple[SelfTestCase, ...] = (
    (
        'pips-to-price takes decimal pips and shows a changed level: a sell stop 32.8 pips above 3588.25 rounds to 3588.58',
        [
            'pips-to-price', '--reference-price', '3588.25', '--pips', '32.8', '--pip-size', '0.01', '--digits', '2',
            '--side', 'sell', '--direction', 'sl',
        ],
        {
            'absolute_price': 3588.58,
            'pip_size_used': 0.01,
            'rounded_to_digits': 2,
            'rounded': True,
            'unrounded_price': 3588.578,
        },
        0,
    ),
    (
        'pips-to-price prints no unrounded_price when rounding changes nothing: 30 pips above 158.837 is 159.137',
        [
            'pips-to-price', '--reference-price', '158.837', '--pips', '30', '--pip-size', '0.01', '--digits', '3',
            '--side', 'buy', '--direction', 'tp',
        ],
        {'absolute_price': 159.137, 'rounded': False},
        0,
        {'absent': ['unrounded_price']},
    ),
    (
        'pips-to-price places a buy stop below the reference: 30 pips below 1.085 at pip size 0.0001 is 1.082',
        [
            'pips-to-price', '--reference-price', '1.0850', '--pips', '30', '--pip-size', '0.0001', '--digits', '5',
            '--side', 'buy', '--direction', 'sl',
        ],
        {'absolute_price': 1.082, 'rounded': False},
        0,
    ),
    (
        'pips-to-price places a sell take profit below the reference: 50 pips below 150.3 at pip size 0.01 is 149.8',
        [
            'pips-to-price', '--reference-price', '150.3', '--pips', '50', '--pip-size', '0.01', '--digits', '3',
            '--side', 'sell', '--direction', 'tp',
        ],
        {'absolute_price': 149.8, 'rounded': False},
        0,
    ),
    (
        'pips-to-price defaults to a buy take profit',
        ['pips-to-price', '--reference-price', '1.0850', '--pips', '30', '--pip-size', '0.0001', '--digits', '5'],
        {'absolute_price': 1.088},
        0,
    ),
    (
        'pips-to-price refuses a pip size that is not above 0',
        ['pips-to-price', '--reference-price', '1.0850', '--pips', '30', '--pip-size', '0', '--digits', '5'],
        {'error': '--pip-size must be above 0, got 0'},
        3,
    ),
    (
        'pips-to-price refuses negative digits',
        ['pips-to-price', '--reference-price', '1.0850', '--pips', '30', '--pip-size', '0.0001', '--digits', '-1'],
        {'error': '--digits must be 0 or more, got -1'},
        2,
    ),
    (
        'pips-to-price refuses a reference price that is not finite',
        ['pips-to-price', '--reference-price', 'inf', '--pips', '30', '--pip-size', '0.0001', '--digits', '5'],
        {'error': '--reference-price must be finite'},
        3,
    ),
    (
        'pips-to-price refuses a distance that is not a number, with the usage on stderr only',
        ['pips-to-price', '--reference-price', '1.0850', '--pips', 'abc', '--pip-size', '0.0001', '--digits', '5'],
        {},
        2,
        {'absent': ['error']},
    ),
    (
        'price-to-pips gives the exact decimal distance: 1.08172 lies 32.8 pips from 1.085 at pip size 0.0001',
        ['price-to-pips', '--reference-price', '1.0850', '--price', '1.08172', '--pip-size', '0.0001', '--digits', '5'],
        {'pip_distance': 32.8, 'pip_size_used': 0.0001},
        0,
        {'absent': ['pip_distance_raw']},
    ),
    (
        'price-to-pips needs no --digits: the reference price, the price and the pip size give the distance',
        ['price-to-pips', '--reference-price', '1.0850', '--price', '1.08172', '--pip-size', '0.0001'],
        {'pip_distance': 32.8, 'pip_size_used': 0.0001},
        0,
    ),
    (
        'price-to-pips measures a level above the reference as well: 1.088 lies 30 pips from 1.085',
        ['price-to-pips', '--reference-price', '1.0850', '--price', '1.088', '--pip-size', '0.0001', '--digits', '5'],
        {'pip_distance': 30},
        0,
    ),
    (
        'distance: 30 pips at pip size 0.0001 and digits 5 are 300 in 1/100000 of the price and 300 points',
        ['distance', '--pips', '30', '--pip-size', '0.0001', '--digits', '5'],
        {'price_distance': 0.003, 'relative': 300, 'points': 300},
        0,
    ),
    (
        'distance: a stop 5.00 away at digits 2 is the served example 500000, and 500 points',
        ['distance', '--price-distance', '5.00', '--digits', '2'],
        {'price_distance': 5, 'relative': 500000, 'points': 500},
        0,
    ),
    (
        'distance: 0.3 at digits 3 is 30000 and 300 points',
        ['distance', '--price-distance', '0.3', '--digits', '3'],
        {'relative': 30000, 'points': 300},
        0,
    ),
    (
        'distance: 2.00 at digits 2 is 200000, a relative distance the server accepts',
        ['distance', '--price-distance', '2.00', '--digits', '2'],
        {'relative': 200000, 'points': 200},
        0,
    ),
    (
        'distance: 0.002 at digits 5 is 200, a relative distance the server accepts',
        ['distance', '--price-distance', '0.002', '--digits', '5'],
        {'relative': 200, 'points': 200},
        0,
    ),
    (
        'distance: 0.004 at digits 5 is 400, a relative distance the server accepts',
        ['distance', '--price-distance', '0.004', '--digits', '5'],
        {'relative': 400, 'points': 400},
        0,
    ),
    (
        'distance refuses a value off the multiples of 10^(5 - digits) and names the two nearest: 12.5 pips at digits 2',
        ['distance', '--pips', '12.5', '--pip-size', '0.01', '--digits', '2'],
        {'error': 'relative distance 12500 is not a multiple of 1000 at digits 2; the nearest are 12000 and 13000'},
        2,
    ),
    (
        'distance needs the pip size with --pips',
        ['distance', '--pips', '30', '--digits', '5'],
        {'error': '--pips needs --pip-size'},
        2,
    ),
    (
        'distance takes no pip size beside a price distance',
        ['distance', '--price-distance', '0.003', '--pip-size', '0.0001', '--digits', '5'],
        {'error': '--pip-size goes with --pips only'},
        2,
    ),
    (
        'distance takes --pips or --price-distance, not both',
        ['distance', '--pips', '30', '--price-distance', '0.003', '--pip-size', '0.0001', '--digits', '5'],
        {},
        2,
    ),
    (
        'distance refuses a distance that is not above 0',
        ['distance', '--price-distance', '0', '--digits', '5'],
        {'error': '--price-distance must be above 0, got 0'},
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


def polarity(side: str, direction: str) -> int:
    """Return the sign a protection's distance takes from the reference price.

    Args:
        side: ``buy`` or ``sell``.
        direction: ``sl`` for a stop loss, ``tp`` for a take profit.

    Returns:
        1 when the level lies above the reference (a buy's take profit, a sell's stop loss), -1 when it lies below.
    """
    return 1 if (side == 'buy') == (direction == 'tp') else -1


def round_to_digits(price: Decimal, digits: int) -> Decimal:
    """Round a price half up to a number of decimals.

    Args:
        price: The price.
        digits: The decimals the symbol's prices carry.

    Returns:
        The rounded price.
    """
    return price.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)


def pips_to_price(reference: Decimal, pips: Decimal, pip_size: Decimal, side: str, direction: str) -> Decimal:
    """Return the level that lies a pip distance from a reference price.

    Args:
        reference: The reference price, as the entry price.
        pips: The distance in pips; decimals are allowed.
        pip_size: The price of one pip.
        side: ``buy`` or ``sell``.
        direction: ``sl`` or ``tp``.

    Returns:
        The level, not yet rounded.
    """
    return reference + polarity(side, direction) * pips * pip_size


def price_to_pips(reference: Decimal, price: Decimal, pip_size: Decimal) -> Decimal:
    """Return the distance between two prices in pips.

    Args:
        reference: The reference price.
        price: The other price.
        pip_size: The price of one pip.

    Returns:
        The exact distance, never rounded to a whole pip.
    """
    return abs(price - reference) / pip_size


def distance(price_distance: Decimal, digits: int) -> tuple[Decimal, Decimal]:
    """Express a price distance in the units of the relative and the slippage fields of an order.

    Args:
        price_distance: The distance in display price.
        digits: The decimals the symbol's prices carry.

    Returns:
        The distance in 1/100000 of the price, as ``relativeStopLoss`` and ``relativeTakeProfit`` take it, and in points
        of 1/10^digits, as ``slippageInPoints`` takes it.
    """
    return price_distance.scaleb(5), price_distance.scaleb(digits)


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


def _pip_size(value: Decimal) -> Decimal:
    """Refuse a pip size that is not finite or not above 0.

    Args:
        value: The pip size.

    Returns:
        The pip size.
    """
    if _finite(value, '--pip-size') <= 0:
        _emit_error(f'--pip-size must be above 0, got {_plain(value)}', exit_code=EXIT_NUMERIC_ERROR)
    return value


def _digits(value: int) -> int:
    """Refuse a negative number of digits.

    Args:
        value: The digits.

    Returns:
        The digits.
    """
    if value < 0:
        _emit_error(f'--digits must be 0 or more, got {value}', exit_code=EXIT_INVALID_ARGS)
    return value


def _handle_pips_to_price(args: argparse.Namespace) -> Answer:
    """Answer ``pips-to-price``.

    Args:
        args: The parsed arguments.

    Returns:
        The level rounded to the digits, and the unrounded level when rounding changed it.
    """
    pip_size = _pip_size(args.pip_size)
    digits = _digits(args.digits)
    level = pips_to_price(
        _finite(args.reference_price, '--reference-price'), _finite(args.pips, '--pips'), pip_size, args.side, args.direction
    )
    rounded = round_to_digits(level, digits)
    answer: Answer = {'absolute_price': rounded, 'pip_size_used': pip_size, 'rounded_to_digits': digits}
    answer['rounded'] = rounded != level
    if rounded != level:
        answer['unrounded_price'] = level
    return answer


def _handle_price_to_pips(args: argparse.Namespace) -> Answer:
    """Answer ``price-to-pips``.

    Args:
        args: The parsed arguments.

    Returns:
        The exact distance in pips.
    """
    pip_size = _pip_size(args.pip_size)
    reference = _finite(args.reference_price, '--reference-price')
    return {'pip_distance': price_to_pips(reference, _finite(args.price, '--price'), pip_size), 'pip_size_used': pip_size}


def _handle_distance(args: argparse.Namespace) -> Answer:
    """Answer ``distance``.

    Args:
        args: The parsed arguments.

    Returns:
        The distance in display price, in 1/100000 of the price and in points.
    """
    digits = _digits(args.digits)
    if args.pips is not None:
        if args.pip_size is None:
            _emit_error('--pips needs --pip-size', exit_code=EXIT_INVALID_ARGS)
        flag, price_distance = '--pips', _finite(args.pips, '--pips') * _pip_size(args.pip_size)
    else:
        if args.pip_size is not None:
            _emit_error('--pip-size goes with --pips only', exit_code=EXIT_INVALID_ARGS)
        flag, price_distance = '--price-distance', _finite(args.price_distance, '--price-distance')
    if price_distance <= 0:
        _emit_error(f'{flag} must be above 0, got {_plain(price_distance)}', exit_code=EXIT_INVALID_ARGS)
    relative, points = distance(price_distance, digits)
    step = Decimal(1).scaleb(5 - digits)
    if relative % step != 0:
        lower = (relative / step).to_integral_value(rounding=ROUND_FLOOR) * step
        _emit_error(
            f'relative distance {_plain(relative)} is not a multiple of {_plain(step)} at digits {digits}; '
            f'the nearest are {_plain(lower)} and {_plain(lower + step)}',
            exit_code=EXIT_INVALID_ARGS,
        )
    return {'price_distance': price_distance, 'relative': relative, 'points': points}


PIP_SIZE_HELP = 'Price of one pip: pipSize of get_symbol_details on the Local server.'
DIGITS_HELP = "Decimals of the symbol's prices: digits of get_symbol_details (Local) or of get_symbols (Remote)."

EPILOG = """\
Run it as python3 <skill folder>/scripts/pip_math.py on macOS and Linux, and as
python <skill folder>/scripts/pip_math.py on Windows (py in place of python where python is not on the path).

Examples:
  python3 <skill folder>/scripts/pip_math.py pips-to-price --reference-price 1.0850 --pips 30 \\
      --pip-size 0.0001 --digits 5 --side buy --direction tp
  python3 <skill folder>/scripts/pip_math.py price-to-pips --reference-price 1.0850 --price 1.08172 \\
      --pip-size 0.0001
  python3 <skill folder>/scripts/pip_math.py distance --price-distance 0.3 --digits 3
  python3 <skill folder>/scripts/pip_math.py --self-test

Every price is a display price on both servers. The quotes of the Remote server are integers in 1/100000 of the
price: convert them with units_encoding.py quote-to-price first.

pips-to-price rounds the level to --digits and prints rounded true with the unrounded level when that changed it:
a price with more decimals than the symbol's digits is refused, so send the rounded level.
price-to-pips prints the exact distance in pips, decimals included.
distance prints the distance in display price, as relative (1/100000 of the price, the unit of relativeStopLoss and
relativeTakeProfit) and as points (1/10^digits, the unit of slippageInPoints). A relative distance is a multiple of
10^(5 - digits); for any other distance it exits 2 and names the two nearest.

Every answer is one line of JSON on stdout. A refusal writes "error: <reason>" on stderr and {"error": "<reason>"} on
stdout. Exit codes: 0 success, 2 invalid input, 3 a value that is not finite or a pip size that is not above 0.
--self-test runs the script's own cases and exits 0 when every case holds, 1 otherwise.
"""


def _build_parser() -> argparse.ArgumentParser:
    """Build the parser of the command line.

    Returns:
        The parser, with one subparser per subcommand.
    """
    parser = argparse.ArgumentParser(
        prog='pip_math.py',
        description='Convert between pip distances and display prices, and express a distance in order-field units.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument('--self-test', action='store_true', help="Run the script's own cases; exit 0 when all hold.")
    subparsers = parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND')

    level = subparsers.add_parser('pips-to-price', help='Level a pip distance away from a reference price.')
    level.add_argument('--reference-price', type=_number, required=True, help='The reference price, as the entry.')
    level.add_argument('--pips', type=_number, required=True, help='The distance in pips; decimals are allowed.')
    level.add_argument('--pip-size', type=_number, required=True, help=PIP_SIZE_HELP)
    level.add_argument('--digits', type=int, required=True, help=DIGITS_HELP)
    level.add_argument('--side', default='buy', choices=SIDES, help='The side of the position (default: buy).')
    level.add_argument('--direction', default='tp', choices=DIRECTIONS, help='sl or tp (default: tp).')
    level.set_defaults(handler=_handle_pips_to_price)

    pips = subparsers.add_parser('price-to-pips', help='Distance in pips between a reference price and a price.')
    pips.add_argument('--reference-price', type=_number, required=True, help='The reference price.')
    pips.add_argument('--price', type=_number, required=True, help='The other price.')
    pips.add_argument('--pip-size', type=_number, required=True, help=PIP_SIZE_HELP)
    pips.add_argument('--digits', type=int, help='Accepted and not used.')
    pips.add_argument('--side', default='buy', choices=SIDES, help='Accepted and not used.')
    pips.add_argument('--direction', default='tp', choices=DIRECTIONS, help='Accepted and not used.')
    pips.set_defaults(handler=_handle_price_to_pips)

    span = subparsers.add_parser(
        'distance', help='A distance as relative (1/100000 of the price) and as points (1/10^digits).'
    )
    given = span.add_mutually_exclusive_group(required=True)
    given.add_argument('--pips', type=_number, help='The distance in pips; needs --pip-size.')
    given.add_argument('--price-distance', type=_number, help='The distance in display price.')
    span.add_argument('--pip-size', type=_number, help=PIP_SIZE_HELP)
    span.add_argument('--digits', type=int, required=True, help=DIGITS_HELP)
    span.set_defaults(handler=_handle_distance)
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
