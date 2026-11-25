# /// script
# requires-python = ">=3.11"
# ///

"""Find the shortest chain of quotes that converts an amount from one currency to another, and its rate.

The script converts amounts computed from prices, such as a pip value or a notional. Money the cTrader servers return
(balance, equity, profit, commission, swap) is already in the account currency and needs no conversion.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections import deque
from collections.abc import Mapping
from contextlib import redirect_stderr
from contextlib import redirect_stdout
from decimal import Decimal
from decimal import getcontext
from typing import NoReturn
from typing import TypeAlias
from typing import cast

getcontext().prec = 28

EXIT_OK = 0
EXIT_INVALID_ARGS = 2
EXIT_NUMERIC_ERROR = 3
EXIT_LOGIC_ERROR = 4

SIDES = ('bid', 'ask', 'mid')

SelfTestCase: TypeAlias = (
    tuple[str, list[str], Mapping[str, object], int] | tuple[str, list[str], Mapping[str, object], int, Mapping[str, object]]
)
"""One case of the case table: label, arguments, expected values, exit code and, optionally, checks."""

SELF_TEST_CASES: tuple[SelfTestCase, ...] = (
    (
        'USD to EUR from a EURUSD quote of 1.0961 is 0.91232',
        ['compute-chain', '--from-asset', 'USD', '--to-asset', 'EUR', '--quotes', '{"EURUSD":1.0961}'],
        {'rate': 0.91232, 'chain': ['EURUSD'], 'hops': 1, 'warnings': []},
        0,
        {'tolerance': 1e-05},
    ),
    (
        'a quote object with bid and ask, as the Local server answers: EUR to GBP from EURGBP at 0.83785 is 0.83785',
        ['compute-chain', '--from-asset', 'EUR', '--to-asset', 'GBP', '--quotes', '{"EURGBP":{"bid":0.83785,"ask":0.83785}}'],
        {'rate': 0.83785, 'chain': ['EURGBP'], 'hops': 1},
        0,
    ),
    (
        'no chain is a refusal: JPY to EUR with only EURGBP exits 4 and prints no rate',
        ['compute-chain', '--from-asset', 'JPY', '--to-asset', 'EUR', '--quotes', '{"EURGBP":0.83785}'],
        {'error': 'no chain from JPY to EUR within --max-hops 3'},
        4,
        {'absent': ['rate']},
    ),
    (
        'the rate from the EURUSD quote of the minute of a close estimates its grossProfit -74 for a -0.81 move within 0.01',
        ['compute-chain', '--from-asset', 'USD', '--to-asset', 'EUR', '--quotes', '{"EURUSD":{"bid":1.09729,"ask":1.09731}}'],
        {'rate': 0.9136, 'chain': ['EURUSD']},
        0,
        {'tolerance': 0.0123},
    ),
    (
        'two hops: EUR to JPY through EURUSD 1.085 and USDJPY 150.3 is 163.0755',
        ['compute-chain', '--from-asset', 'EUR', '--to-asset', 'JPY', '--quotes', '{"EURUSD":1.0850,"USDJPY":150.3}'],
        {'rate': 163.0755, 'chain': ['EURUSD', 'USDJPY'], 'hops': 2},
        0,
    ),
    (
        'the inverse of a quote: JPY to USD through USDJPY 125 is 0.008',
        ['compute-chain', '--from-asset', 'JPY', '--to-asset', 'USD', '--quotes', '{"USDJPY":125}'],
        {'rate': 0.008, 'chain': ['USDJPY'], 'hops': 1},
        0,
    ),
    (
        'one currency needs no quote: USD to USD is 1',
        ['compute-chain', '--from-asset', 'USD', '--to-asset', 'USD', '--quotes', '{"EURUSD":1.085}'],
        {'rate': 1, 'chain': [], 'hops': 0},
        0,
    ),
    (
        'the mid of bid and ask is the default: EUR to USD with bid 1.0848 and ask 1.0852 is 1.085',
        ['compute-chain', '--from-asset', 'EUR', '--to-asset', 'USD', '--quotes', '{"EURUSD":{"bid":1.0848,"ask":1.0852}}'],
        {'rate': 1.085},
        0,
    ),
    (
        '--side ask takes the ask: EUR to USD with bid 1.0848 and ask 1.0852 is 1.0852',
        [
            'compute-chain', '--from-asset', 'EUR', '--to-asset', 'USD',
            '--quotes', '{"EURUSD":{"bid":1.0848,"ask":1.0852}}', '--side', 'ask',
        ],
        {'rate': 1.0852},
        0,
    ),
    (
        '--max-hops limits the chain: EUR to JPY needs two hops',
        [
            'compute-chain', '--from-asset', 'EUR', '--to-asset', 'JPY',
            '--quotes', '{"EURUSD":1.0850,"USDJPY":150.3}', '--max-hops', '1',
        ],
        {'error': 'no chain from EUR to JPY within --max-hops 1'},
        4,
        {'absent': ['rate']},
    ),
    (
        'a currency code is three capital letters',
        ['compute-chain', '--from-asset', 'eur', '--to-asset', 'USD', '--quotes', '{"EURUSD":1.0850}'],
        {'error': "--from-asset must be a 3-letter uppercase ISO code, got 'eur'"},
        2,
    ),
    (
        'a symbol written with a separator is read as its six letters: USD/ZAR is USDZAR',
        ['compute-chain', '--from-asset', 'USD', '--to-asset', 'ZAR', '--quotes', '{"USD/ZAR":18.50}'],
        {'rate': 18.5, 'chain': ['USDZAR'], 'hops': 1, 'warnings': ["normalized 'USD/ZAR' -> 'USDZAR'"]},
        0,
    ),
    (
        'a symbol in lower case with an underscore is read as its six letters: usd_zar is USDZAR',
        ['compute-chain', '--from-asset', 'USD', '--to-asset', 'ZAR', '--quotes', '{"usd_zar":18.50}'],
        {'rate': 18.5, 'chain': ['USDZAR']},
        0,
    ),
    (
        'a key that is no currency pair is skipped with a warning, and the chain is still found',
        ['compute-chain', '--from-asset', 'EUR', '--to-asset', 'USD', '--quotes', '{"EURUSD":1.0850,"EURO":2.0}'],
        {
            'rate': 1.085,
            'chain': ['EURUSD'],
            'warnings': ["skipped 'EURO': after stripping separators, expected 6 alpha chars, got 4 ('EURO')"],
        },
        0,
    ),
    (
        '--strict-symbols takes only six capital letters and refuses USD/ZAR',
        ['compute-chain', '--from-asset', 'USD', '--to-asset', 'ZAR', '--quotes', '{"USD/ZAR":18.50}', '--strict-symbols'],
        {'error': "--quotes symbol 'USD/ZAR' must be 6 uppercase letters (BASE+QUOTE) with --strict-symbols"},
        2,
    ),
    (
        '--side bid takes the bid: EUR to USD with bid 1.0848 and ask 1.0852 is 1.0848',
        [
            'compute-chain', '--from-asset', 'EUR', '--to-asset', 'USD',
            '--quotes', '{"EURUSD":{"bid":1.0848,"ask":1.0852}}', '--side', 'bid',
        ],
        {'rate': 1.0848},
        0,
    ),
    (
        'a key whose two currencies are the same is skipped with a warning',
        ['compute-chain', '--from-asset', 'EUR', '--to-asset', 'USD', '--quotes', '{"EURUSD":1.0850,"EUR/EUR":1.0}'],
        {
            'rate': 1.085,
            'chain': ['EURUSD'],
            'warnings': ["skipped 'EUR/EUR': normalized 'EUR/EUR' -> 'EUREUR' has identical base and quote currencies"],
        },
        0,
    ),
    (
        '--strict-symbols refuses a key whose two currencies are the same',
        [
            'compute-chain', '--from-asset', 'EUR', '--to-asset', 'USD',
            '--quotes', '{"EURUSD":1.0850,"EUREUR":1.0}', '--strict-symbols',
        ],
        {'error': "--quotes symbol 'EUREUR' has identical base and quote currencies"},
        2,
    ),
    (
        'an empty quote object is refused',
        ['compute-chain', '--from-asset', 'EUR', '--to-asset', 'USD', '--quotes', '{}'],
        {'error': '--quotes must be a non-empty JSON object'},
        2,
    ),
    (
        'quotes that are not JSON are refused',
        ['compute-chain', '--from-asset', 'EUR', '--to-asset', 'USD', '--quotes', '{EURUSD'],
        {},
        2,
    ),
    (
        'a quote object without both bid and ask is refused',
        ['compute-chain', '--from-asset', 'EUR', '--to-asset', 'USD', '--quotes', '{"EURUSD":{"bid":1.0848}}'],
        {'error': "--quotes[EURUSD] object form must contain 'bid' and 'ask' keys"},
        2,
    ),
    (
        'a quote that is neither a number nor an object is refused',
        ['compute-chain', '--from-asset', 'EUR', '--to-asset', 'USD', '--quotes', '{"EURUSD":"1.0850"}'],
        {'error': '--quotes[EURUSD] must be a number or an object with bid/ask keys'},
        2,
    ),
    (
        'a price that is not above 0 is refused',
        ['compute-chain', '--from-asset', 'EUR', '--to-asset', 'USD', '--quotes', '{"EURUSD":0}'],
        {'error': '--quotes[EURUSD] prices must be > 0'},
        3,
    ),
    (
        '--max-hops must be above 0',
        ['compute-chain', '--from-asset', 'EUR', '--to-asset', 'USD', '--quotes', '{"EURUSD":1.0850}', '--max-hops', '0'],
        {'error': '--max-hops must be > 0'},
        2,
    ),
    (
        '--max-hops takes a whole number, with the usage on stderr only',
        ['compute-chain', '--from-asset', 'EUR', '--to-asset', 'USD', '--quotes', '{"EURUSD":1.0850}', '--max-hops', 'two'],
        {},
        2,
        {'absent': ['error']},
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


def _validate_currency_code(code: str, *, flag_name: str) -> str:
    """Refuse a currency code that is not three capital letters.

    Args:
        code: The code.
        flag_name: The flag that gave it.

    Returns:
        The code.
    """
    if len(code) != 3 or not code.isalpha() or not code.isupper():
        _emit_error(f'{flag_name} must be a 3-letter uppercase ISO code, got {code!r}', exit_code=EXIT_INVALID_ARGS)
    return code


def _normalize_symbol(raw: str) -> tuple[str, str | None]:
    """Read a symbol name as its six capital letters, the base currency then the quote currency.

    Every character that is not a letter (``/``, ``_``, ``-``, ``.``, a space) is dropped and the rest is upper-cased.

    Args:
        raw: The symbol name, such as ``USD/ZAR``, ``usd_zar``, ``EUR.USD`` or ``EURUSD``.

    Returns:
        The six letters and ``None``, or an empty string and the reason the name is no currency pair.
    """
    canonical = ''.join(ch for ch in raw if ch.isalpha()).upper()
    if len(canonical) != 6:
        return '', f'after stripping separators, expected 6 alpha chars, got {len(canonical)} ({canonical!r})'
    if canonical[:3] == canonical[3:]:
        return '', f'normalized {raw!r} -> {canonical!r} has identical base and quote currencies'
    return canonical, None


def _parse_quotes(
    quotes_raw: object,
    side: str,
    *,
    strict: bool,
) -> tuple[dict[str, tuple[str, str, Decimal]], list[str]]:
    """Read the quotes of ``--quotes`` as edges between currencies.

    Args:
        quotes_raw: The parsed JSON value.
        side: ``bid``, ``ask`` or ``mid``, the price taken from a quote object.
        strict: Whether every key must already be six capital letters; otherwise a key is read as its six letters, and
            a key that is no currency pair is skipped with a warning.

    Returns:
        The base currency, the quote currency and the price of each symbol, and the warnings.
    """
    if not isinstance(quotes_raw, dict) or len(quotes_raw) == 0:
        _emit_error('--quotes must be a non-empty JSON object', exit_code=EXIT_INVALID_ARGS)

    normalized: dict[str, tuple[str, str, Decimal]] = {}
    warnings: list[str] = []

    for symbol_raw, value in cast('dict[str, object]', quotes_raw).items():
        if strict:
            if len(symbol_raw) != 6 or not symbol_raw.isalpha() or not symbol_raw.isupper():
                _emit_error(
                    f'--quotes symbol {symbol_raw!r} must be 6 uppercase letters (BASE+QUOTE) with --strict-symbols',
                    exit_code=EXIT_INVALID_ARGS,
                )
            canonical = symbol_raw
            if canonical[:3] == canonical[3:]:
                _emit_error(
                    f'--quotes symbol {symbol_raw!r} has identical base and quote currencies',
                    exit_code=EXIT_INVALID_ARGS,
                )
        else:
            canonical, reason = _normalize_symbol(symbol_raw)
            if reason is not None:
                warnings.append(f'skipped {symbol_raw!r}: {reason}')
                continue
            if canonical != symbol_raw:
                warnings.append(f'normalized {symbol_raw!r} -> {canonical!r}')
        normalized[canonical] = (canonical[:3], canonical[3:], _quote_price(symbol_raw, value, side))

    return normalized, warnings


def _quote_price(symbol: str, value: object, side: str) -> Decimal:
    """Read the price of one quote of ``--quotes``.

    Args:
        symbol: The key of the quote.
        value: A number, or an object with ``bid`` and ``ask``.
        side: ``bid``, ``ask`` or ``mid``, the price taken from an object.

    Returns:
        The price.
    """
    if isinstance(value, dict):
        prices = cast('dict[str, object]', value)
        if 'bid' not in prices or 'ask' not in prices:
            _emit_error(f"--quotes[{symbol}] object form must contain 'bid' and 'ask' keys", exit_code=EXIT_INVALID_ARGS)
        bid = _price(symbol, prices['bid'])
        ask = _price(symbol, prices['ask'])
        if side == 'bid':
            return bid
        return ask if side == 'ask' else (bid + ask) / 2
    return _price(symbol, value)


def _price(symbol: str, value: object) -> Decimal:
    """Read one price of a quote, refusing anything but a number above 0.

    Args:
        symbol: The key of the quote.
        value: The value.

    Returns:
        The price.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        _emit_error(f'--quotes[{symbol}] must be a number or an object with bid/ask keys', exit_code=EXIT_INVALID_ARGS)
    price = Decimal(str(value))
    if not price.is_finite() or price <= 0:
        _emit_error(f'--quotes[{symbol}] prices must be > 0', exit_code=EXIT_NUMERIC_ERROR)
    return price


def compute_chain(
    from_asset: str,
    to_asset: str,
    quotes: dict[str, tuple[str, str, Decimal]],
    max_hops: int,
) -> dict[str, object] | None:
    """Find the shortest chain of quotes from one currency to another.

    A symbol BASEQUOTE at price r links BASE to QUOTE at rate r and QUOTE to BASE at rate 1/r. A breadth-first search
    from ``from_asset`` takes the first chain that reaches ``to_asset``; its rate is the product of the rates on the way.

    Args:
        from_asset: The currency of the amount.
        to_asset: The currency to convert it to.
        quotes: The base currency, the quote currency and the price of each symbol.
        max_hops: The most quotes a chain may use.

    Returns:
        The rate, the symbols of the chain, their number and an empty list of warnings, or ``None`` when no chain
        within ``max_hops`` exists.
    """
    if from_asset == to_asset:
        return {'rate': 1.0, 'chain': [], 'hops': 0, 'warnings': []}

    adjacency: dict[str, list[tuple[str, Decimal, str]]] = {}
    for symbol, (base, quote, rate) in quotes.items():
        adjacency.setdefault(base, []).append((quote, rate, symbol))
        adjacency.setdefault(quote, []).append((base, 1 / rate, symbol))

    queue: deque[tuple[str, list[str], Decimal]] = deque([(from_asset, [], Decimal(1))])
    visited: set[str] = {from_asset}
    while queue:
        current, chain_so_far, rate_so_far = queue.popleft()
        if len(chain_so_far) >= max_hops:
            continue
        for neighbor, edge_rate, edge_symbol in adjacency.get(current, []):
            if neighbor in visited:
                continue
            new_chain = [*chain_so_far, edge_symbol]
            new_rate = rate_so_far * edge_rate
            if neighbor == to_asset:
                return {'rate': float(new_rate), 'chain': new_chain, 'hops': len(new_chain), 'warnings': []}
            visited.add(neighbor)
            queue.append((neighbor, new_chain, new_rate))
    return None


EPILOG = """\
Run it as python3 <skill folder>/scripts/conversion_rate.py on macOS and Linux, and as
python <skill folder>/scripts/conversion_rate.py on Windows (py in place of python where python is not on the path).

Examples:
  python3 <skill folder>/scripts/conversion_rate.py compute-chain --from-asset USD --to-asset EUR \\
      --quotes '{"EURUSD":1.0961}'
  python3 <skill folder>/scripts/conversion_rate.py compute-chain --from-asset EUR --to-asset JPY \\
      --quotes '{"EURUSD":1.0850,"USDJPY":150.3}'
  python3 <skill folder>/scripts/conversion_rate.py --self-test

--quotes is a JSON object of display prices keyed by symbol name: a number, or an object with bid and ask, from
which --side takes the bid, the ask or their mid (the default). The quotes of the Remote server are integers in
1/100000 of the price and their rows carry a symbolId and no name: convert each with units_encoding.py
quote-to-price and key it by the symbol's name before passing it here.

A key is read as its six letters, so USD/ZAR, usd_zar and USDZAR are the same pair; a key that is no currency pair
is skipped with a warning in warnings. With --strict-symbols every key must already be six capital letters.

Convert only amounts computed from prices, such as a pip value or a notional. Money the servers return is already
in the account currency.

Every answer is one line of JSON on stdout. A refusal writes "error: <reason>" on stderr and {"error": "<reason>"} on
stdout. Exit codes: 0 success, 2 invalid input, 3 a price that is not above 0, 4 no chain within --max-hops.
--self-test runs the script's own cases and exits 0 when every case holds, 1 otherwise.
"""


def _build_parser() -> argparse.ArgumentParser:
    """Build the parser of the command line.

    Returns:
        The parser, with the subparser of ``compute-chain``.
    """
    parser = argparse.ArgumentParser(
        prog='conversion_rate.py',
        description='Find the shortest chain of quotes between two currencies, and its rate.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument('--self-test', action='store_true', help="Run the script's own cases; exit 0 when all hold.")
    subparsers = parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND')
    chain = subparsers.add_parser('compute-chain', help='Rate of the shortest chain from one currency to another.')
    chain.add_argument('--from-asset', required=True, type=str, help='The currency of the amount, such as USD.')
    chain.add_argument('--to-asset', required=True, type=str, help='The currency to convert it to, such as EUR.')
    chain.add_argument('--quotes', required=True, type=str, help='Display prices keyed by symbol name, as JSON.')
    chain.add_argument('--side', default='mid', choices=SIDES, help='The price of a quote object (default: mid).')
    chain.add_argument('--max-hops', default=3, type=int, help='The most quotes a chain may use (default: 3).')
    chain.add_argument('--strict-symbols', action='store_true', help='Take only keys of six capital letters.')
    return parser


def _handle_compute_chain(args: argparse.Namespace) -> dict[str, object]:
    """Answer ``compute-chain``.

    Args:
        args: The parsed arguments.

    Returns:
        The rate, the chain, its length and the warnings.
    """
    from_asset = _validate_currency_code(args.from_asset, flag_name='--from-asset')
    to_asset = _validate_currency_code(args.to_asset, flag_name='--to-asset')
    if args.max_hops <= 0:
        _emit_error('--max-hops must be > 0', exit_code=EXIT_INVALID_ARGS)
    try:
        quotes_raw = json.loads(args.quotes)
    except json.JSONDecodeError as exc:
        _emit_error(f'--quotes value is not valid JSON: {exc}', exit_code=EXIT_INVALID_ARGS)
    quotes, parse_warnings = _parse_quotes(quotes_raw, args.side, strict=args.strict_symbols)
    payload = compute_chain(from_asset=from_asset, to_asset=to_asset, quotes=quotes, max_hops=args.max_hops)
    if payload is None:
        _emit_error(f'no chain from {from_asset} to {to_asset} within --max-hops {args.max_hops}', exit_code=EXIT_LOGIC_ERROR)
    payload['warnings'] = parse_warnings
    return payload


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
    _emit_json(_handle_compute_chain(args))
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
