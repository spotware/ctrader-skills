# /// script
# requires-python = ">=3.12"
# ///

"""Build the shortest spot-rate chain to convert an amount from one currency to another using available quotes."""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
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

SIDES = ('bid', 'ask', 'mid')


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


def _validate_currency_code(code: str, *, flag_name: str) -> str:
    """Validate that a currency code is 3 uppercase letters.

    Args:
        code: Candidate ISO code.
        flag_name: Name of the CLI flag for error reporting.

    Returns:
        The validated code (unchanged).
    """
    if len(code) != 3 or not code.isalpha() or not code.isupper():
        _emit_error(
            f'{flag_name} must be a 3-letter uppercase ISO code, got {code!r}',
            exit_code=EXIT_INVALID_ARGS,
        )
    return code


def _normalize_symbol(raw: object) -> tuple[str, str | None]:
    """Normalize a broker symbol display variant to canonical 6-uppercase form.

    Strategy:
        1. Strip any non-alpha character (separators: '/', '_', '-', '.', ' ', etc.).
        2. Uppercase the result.
        3. Verify exactly 6 alpha characters remain and base != quote.

    Args:
        raw: Raw symbol string (e.g., "USD/ZAR", "usd_zar", "EUR.USD", "EURUSD").

    Returns:
        Tuple of (canonical_symbol, reason_if_invalid). If invalid, canonical_symbol
        is "" and reason is a human-readable explanation. If valid, reason is None.
    """
    if not isinstance(raw, str):
        return '', f'symbol must be a string, got {type(raw).__name__}'
    stripped = ''.join(ch for ch in raw if ch.isalpha())
    canonical = stripped.upper()
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
    """Validate and normalize the --quotes JSON into a symbol->edge map.

    Args:
        quotes_raw: Parsed JSON object.
        side: 'bid', 'ask', or 'mid'.
        strict: If True, restore legacy strict 6-uppercase-letter validation
                (any non-matching symbol is rejected with EXIT_INVALID_ARGS).
                If False (default), invalid symbols emit warnings and are
                skipped from the adjacency graph.

    Returns:
        Tuple of:
        - Dict keyed by canonical symbol -> (base, quote, effective_rate as Decimal).
        - List of warning strings for skipped/normalized symbols.
    """
    if not isinstance(quotes_raw, dict) or len(quotes_raw) == 0:
        _emit_error('--quotes must be a non-empty JSON object', exit_code=EXIT_INVALID_ARGS)

    normalized: dict[str, tuple[str, str, Decimal]] = {}
    warnings: list[str] = []

    for symbol_raw, value in quotes_raw.items():
        if strict:
            if (
                not isinstance(symbol_raw, str)
                or len(symbol_raw) != 6
                or not symbol_raw.isalpha()
                or not symbol_raw.isupper()
            ):
                _emit_error(
                    f'--quotes symbol {symbol_raw!r} must be 6 uppercase letters (BASE+QUOTE) in strict mode',
                    exit_code=EXIT_INVALID_ARGS,
                )
            canonical = symbol_raw
            base = canonical[:3]
            quote = canonical[3:]
            if base == quote:
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
            base = canonical[:3]
            quote = canonical[3:]

        if isinstance(value, dict):
            value_dict = cast('dict[str, Any]', value)
            if 'bid' not in value_dict or 'ask' not in value_dict:
                _emit_error(
                    f"--quotes[{symbol_raw}] object form must contain 'bid' and 'ask' keys",
                    exit_code=EXIT_INVALID_ARGS,
                )
            try:
                bid = Decimal(str(value_dict['bid']))
                ask = Decimal(str(value_dict['ask']))
            except (ValueError, ArithmeticError) as exc:
                _emit_error(
                    f'--quotes[{symbol_raw}] bid/ask must be numeric, got error {exc}',
                    exit_code=EXIT_INVALID_ARGS,
                )
            if bid <= 0 or ask <= 0:
                _emit_error(
                    f'--quotes[{symbol_raw}] bid and ask must be > 0',
                    exit_code=EXIT_NUMERIC_ERROR,
                )
            if side == 'bid':
                rate = bid
            elif side == 'ask':
                rate = ask
            else:
                rate = (bid + ask) / Decimal(2)
        elif isinstance(value, (int, float)):
            try:
                rate = Decimal(str(value))
            except (ValueError, ArithmeticError) as exc:
                _emit_error(
                    f'--quotes[{symbol_raw}] rate must be numeric, got error {exc}',
                    exit_code=EXIT_INVALID_ARGS,
                )
            if rate <= 0:
                _emit_error(
                    f'--quotes[{symbol_raw}] rate must be > 0',
                    exit_code=EXIT_NUMERIC_ERROR,
                )
        else:
            _emit_error(
                f'--quotes[{symbol_raw}] must be a number or an object with bid/ask keys',
                exit_code=EXIT_INVALID_ARGS,
            )
        normalized[canonical] = (base, quote, rate)

    return normalized, warnings


def compute_chain(
    from_asset: str,
    to_asset: str,
    quotes: dict[str, tuple[str, str, Decimal]],
    max_hops: int,
) -> dict[str, Any]:
    """Find the shortest spot-rate chain from from_asset to to_asset.

    Args:
        from_asset: Source currency (3-letter ISO).
        to_asset: Target currency (3-letter ISO).
        quotes: Normalized quotes map (symbol -> (base, quote, rate)).
        max_hops: Maximum BFS depth.

    Returns:
        Dict with rate, chain, hops, warnings.

    Graph construction:
        For each symbol BASEQUOTE with effective rate r:
            Edge base -> quote with rate r (1 BASE = r QUOTE).
            Edge quote -> base with rate 1/r (1 QUOTE = 1/r BASE).

    Search:
        BFS from from_asset. First path to to_asset within max_hops wins.
        Composite rate is the product of all edge rates along the chain.
    """
    if from_asset == to_asset:
        return {
            'rate': 1.0,
            'chain': [],
            'hops': 0,
            'warnings': [],
        }

    adjacency: dict[str, list[tuple[str, Decimal, str]]] = {}
    for symbol, (base, quote, rate) in quotes.items():
        adjacency.setdefault(base, []).append((quote, rate, symbol))
        adjacency.setdefault(quote, []).append((base, Decimal(1) / rate, symbol))

    if from_asset not in adjacency:
        return {
            'rate': 0.0,
            'chain': [],
            'hops': 0,
            'warnings': [f'no chain found from {from_asset} to {to_asset} within {max_hops} hops'],
        }

    queue: deque[tuple[str, list[str], Decimal]] = deque()
    queue.append((from_asset, [], Decimal(1)))
    visited: set[str] = {from_asset}

    while queue:
        current, chain_so_far, rate_so_far = queue.popleft()
        if len(chain_so_far) >= max_hops:
            continue
        for neighbor, edge_rate, edge_symbol in adjacency.get(current, []):
            if neighbor in visited:
                continue
            new_chain = chain_so_far + [edge_symbol]
            new_rate = rate_so_far * edge_rate
            if neighbor == to_asset:
                return {
                    'rate': float(new_rate),
                    'chain': new_chain,
                    'hops': len(new_chain),
                    'warnings': [],
                }
            visited.add(neighbor)
            queue.append((neighbor, new_chain, new_rate))

    return {
        'rate': 0.0,
        'chain': [],
        'hops': 0,
        'warnings': [f'no chain found from {from_asset} to {to_asset} within {max_hops} hops'],
    }


def _build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argparse.ArgumentParser with the `compute-chain` subparser."""
    parser = argparse.ArgumentParser(
        prog='conversion_rate.py',
        description='Build the shortest spot-rate chain between two currencies using available quotes.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python conversion_rate.py compute-chain --from-asset EUR --to-asset USD \\\n"
            "      --quotes '{\"EURUSD\":1.0850}'\n"
            "  python conversion_rate.py compute-chain --from-asset USD --to-asset ZAR \\\n"
            "      --quotes '{\"USD/ZAR\":18.50}'  # broker display variant normalized to USDZAR\n"
            "  python conversion_rate.py compute-chain --from-asset USD --to-asset ZAR \\\n"
            "      --quotes '{\"USD/ZAR\":18.50}' --strict-symbols  # rejects display variants\n"
            "  python conversion_rate.py compute-chain --from-asset EUR --to-asset JPY \\\n"
            "      --quotes '{\"EURUSD\":1.0850,\"USDJPY\":150.3}'\n"
            "  python conversion_rate.py --self-test\n"
            "\n"
            "Default: symbol matching is LOOSE -- broker display variants like 'USD/ZAR',\n"
            "'usd_zar', 'EUR.USD' are accepted (non-alpha separators stripped, then case-\n"
            "normalized). Invalid symbols emit warnings in output.warnings[] but do not\n"
            "fail the call. Use --strict-symbols to restore legacy 6-uppercase-letter\n"
            "validation (rejects display variants).\n"
            "\n"
            "Exit codes:\n"
            "  0  success (chain found OR same-asset OR no chain found with warning)\n"
            "  2  invalid arguments (malformed quotes, non-ISO codes, strict-mode symbol violations)\n"
            "  3  numeric error (zero or negative rate in quotes)\n"
            "  4  logic error (malformed graph)\n"
        ),
    )
    parser.add_argument(
        '--self-test',
        action='store_true',
        help='Run built-in self-test cases and exit 0 if all pass.',
    )
    subparsers = parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND')
    p1 = subparsers.add_parser(
        'compute-chain',
        help='Compute the shortest spot-rate chain from one currency to another.',
    )
    p1.add_argument('--from-asset', required=True, type=str)
    p1.add_argument('--to-asset', required=True, type=str)
    p1.add_argument('--quotes', required=True, type=str)
    p1.add_argument('--side', default='mid', choices=SIDES)
    p1.add_argument('--max-hops', default=3, type=int)
    p1.add_argument(
        '--strict-symbols',
        action='store_true',
        help='Restore strict 6-uppercase-letter symbol validation (default: loose with warnings).',
    )
    return parser


def _handle_compute_chain(args: argparse.Namespace) -> dict[str, Any]:
    """Dispatch handler for the `compute-chain` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Output payload to emit as JSON.
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
    payload = compute_chain(
        from_asset=from_asset,
        to_asset=to_asset,
        quotes=quotes,
        max_hops=args.max_hops,
    )
    payload['warnings'] = parse_warnings + payload.get('warnings', [])
    return payload


def _self_test() -> int:
    """Run canonical self-test cases.

    Returns:
        0 if all cases pass, 1 otherwise.
    """
    parser = _build_parser()
    cases: list[tuple[str, list[str], dict[str, Any], int]] = [
        (
            'JPY -> USD via USDJPY (SKILL.md row 4)',
            [
                'compute-chain',
                '--from-asset', 'JPY',
                '--to-asset', 'USD',
                '--quotes', '{"USDJPY":150.3}',
                '--side', 'mid',
            ],
            {'chain': ['USDJPY'], 'hops': 1, 'rate': 0.0066533599},
            0,
        ),
        (
            'EUR -> USD direct',
            [
                'compute-chain',
                '--from-asset', 'EUR',
                '--to-asset', 'USD',
                '--quotes', '{"EURUSD":1.0850}',
            ],
            {'chain': ['EURUSD'], 'hops': 1, 'rate': 1.085},
            0,
        ),
        (
            'EUR -> JPY two-hop',
            [
                'compute-chain',
                '--from-asset', 'EUR',
                '--to-asset', 'JPY',
                '--quotes', '{"EURUSD":1.0850,"USDJPY":150.3}',
            ],
            {'chain': ['EURUSD', 'USDJPY'], 'hops': 2, 'rate': 163.0755},
            0,
        ),
        (
            'XAU (gold) -> EUR via XAUUSD + EURUSD',
            [
                'compute-chain',
                '--from-asset', 'XAU',
                '--to-asset', 'EUR',
                '--quotes', '{"XAUUSD":1900.5,"EURUSD":1.0850}',
            ],
            {'chain': ['XAUUSD', 'EURUSD'], 'hops': 2},
            0,
        ),
        (
            'Same-asset USD -> USD',
            [
                'compute-chain',
                '--from-asset', 'USD',
                '--to-asset', 'USD',
                '--quotes', '{"EURUSD":1.085}',
            ],
            {'chain': [], 'hops': 0, 'rate': 1.0},
            0,
        ),
        (
            'edge: no chain found',
            [
                'compute-chain',
                '--from-asset', 'NZD',
                '--to-asset', 'BRL',
                '--quotes', '{"EURUSD":1.0850}',
            ],
            {'chain': [], 'hops': 0, 'rate': 0.0},
            0,
        ),
        (
            'edge: bid/ask map with --side=ask',
            [
                'compute-chain',
                '--from-asset', 'EUR',
                '--to-asset', 'USD',
                '--quotes', '{"EURUSD":{"bid":1.0848,"ask":1.0852}}',
                '--side', 'ask',
            ],
            {'chain': ['EURUSD'], 'hops': 1, 'rate': 1.0852},
            0,
        ),
        (
            'edge: malformed currency rejected',
            [
                'compute-chain',
                '--from-asset', 'eur',
                '--to-asset', 'USD',
                '--quotes', '{"EURUSD":1.0850}',
            ],
            {},
            EXIT_INVALID_ARGS,
        ),
        (
            'loose: USD/ZAR normalizes to USDZAR (one-hop)',
            [
                'compute-chain',
                '--from-asset', 'USD',
                '--to-asset', 'ZAR',
                '--quotes', '{"USD/ZAR":18.50}',
            ],
            {'chain': ['USDZAR'], 'hops': 1, 'rate': 18.50},
            0,
        ),
        (
            'loose: usd_zar normalizes (case + separator)',
            [
                'compute-chain',
                '--from-asset', 'USD',
                '--to-asset', 'ZAR',
                '--quotes', '{"usd_zar":18.50}',
            ],
            {'chain': ['USDZAR'], 'hops': 1, 'rate': 18.50},
            0,
        ),
        (
            'loose: malformed symbol skipped with warning, chain still computed',
            [
                'compute-chain',
                '--from-asset', 'EUR',
                '--to-asset', 'USD',
                '--quotes', '{"EURUSD":1.0850,"BADSYM!":2.0}',
            ],
            {'chain': ['EURUSD'], 'hops': 1, 'rate': 1.0850},
            0,
        ),
        (
            'strict: USD/ZAR rejected when --strict-symbols set',
            [
                'compute-chain',
                '--from-asset', 'USD',
                '--to-asset', 'ZAR',
                '--quotes', '{"USD/ZAR":18.50}',
                '--strict-symbols',
            ],
            {},
            EXIT_INVALID_ARGS,
        ),
    ]

    failures = 0
    for label, argv, expected, expected_exit in cases:
        try:
            args = parser.parse_args(argv)
            actual = _handle_compute_chain(args)
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
                import math

                ok = isinstance(act_val, (int, float)) and math.isclose(
                    float(act_val), exp_val, rel_tol=1e-4, abs_tol=1e-4,
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
    if args.subcommand == 'compute-chain':
        payload = _handle_compute_chain(args)
    else:
        parser.print_help(sys.stderr)
        return EXIT_INVALID_ARGS
    _emit_json(payload)
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
