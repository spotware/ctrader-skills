# /// script
# requires-python = ">=3.11"
# ///

"""Find the result in the captured standard output of a cTrader CLI command.

Standard output can hold more than the result: log lines before and after it, a
line that repeats the command, a banner and a header, and the result printed
twice. The result can stand at a different line from one run to the next, so
this script finds it by content, never by position.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any
from typing import NoReturn

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NOT_FOUND = 4

DEFAULT_TOLERANCE = 1e-9

_LOG_LINE = re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?\|')
_OPENERS = ('[', '{')
_EMPTY = '[]'
_PERIOD_WORDS = frozenset({'m1', 'h1'})

SELF_TEST_CASES: list[tuple[Any, ...]] = [
    (
        'key: the plain copy between log lines comes first, after JSON of connection settings and a protocol dump',
        [
            '--key=Live',
            (
                '--text=2000-01-01 23:37:29.7784|INFO|ConnectionStateMachine|Moving state to: AccountsShowing\n'
                '{"clientip": "192.0.2.1","date": 1,"proxies":[]}.\n'
                '2000-01-01 23:37:29.8869|INFO|ReceivedMessageLogHandler|Received: \n'
                'ProtoAccountRes\n{\n\tLive=False\n}\n'
                '[\n  {\n    "Broker": "<broker>",\n    "Live": false,\n    "DepositCurrency": "EUR"\n  }\n]\n'
                '2000-01-01 23:37:29.9009|INFO|TraderCredentials|IsLoggedInWithCtid = True\n'
                '2000-01-01 23:37:29.9318|INFO|UserOutput.NLog.LoggerName|[\n'
                '  {\n    "Broker": "<broker>",\n    "Live": false,\n    "DepositCurrency": "EUR"\n  }\n]\n'
                '2000-01-01 23:37:29.9318|INFO|ConnectionManager|DisconnectFromCId reason: Manually\n'
            ),
        ],
        {'result': [{'Broker': '<broker>', 'Live': False, 'DepositCurrency': 'EUR'}], 'line': 8},
        0,
    ),
    (
        'key: the copy a log line prints comes first, and a log record splits the plain copy after it',
        [
            '--key=Description',
            (
                '--text=2000-01-01 23:37:10.2960|INFO|LightSymbolRepository|LightSymbolRepository is ready\n'
                '2000-01-01 23:37:10.3096|INFO|UserOutput.NLog.LoggerName|[\n'
                '  {\n    "Name": "EURUSD",\n    "Description": "Euro vs US Dollar"\n  },\n'
                '  {\n    "Name": "EURCHF",\n    "Description": "Euro vs Swiss Franc"\n  }\n]\n'
                '[\n  {\n    "Name": "EURUSD",\n    "Description": "Euro vs US Dollar"\n  },\n  {\n'
                '    "Name": "EURCHF",2000-01-01 23:37:10.3096|INFO|ReceivedMessageLogHandler|Received: \n'
                'ProtoReadyAccountRes\n{\n\tBalanceVersion=7\n}\n'
                '    "Description": "Euro vs Swiss Franc"\n  }\n]\n'
                '2000-01-01 23:37:10.3439|INFO|ConnectionManager|DisconnectFromCId reason: Manually\n'
            ),
        ],
        {
            'result': [
                {'Name': 'EURUSD', 'Description': 'Euro vs US Dollar'},
                {'Name': 'EURCHF', 'Description': 'Euro vs Swiss Franc'},
            ],
            'line': 2,
        },
        0,
    ),
    (
        'key: a copy a log record splits does not parse, so the next line that holds the key is read',
        [
            '--key=Description',
            (
                '--text=[\n  {\n    "Name": "EURUSD",\n    "Description": "Euro vs US Dollar"\n  },\n  {\n'
                '    "Name": "EURCHF",2000-01-01 23:37:10.3096|INFO|ReceivedMessageLogHandler|Received: \n'
                'ProtoReadyAccountRes\n{\n\tBalanceVersion=7\n}\n'
                '    "Description": "Euro vs Swiss Franc"\n  }\n]\n'
                '2000-01-01 23:37:10.3096|INFO|UserOutput.NLog.LoggerName|[\n'
                '  {\n    "Name": "EURUSD",\n    "Description": "Euro vs US Dollar"\n  },\n'
                '  {\n    "Name": "EURCHF",\n    "Description": "Euro vs Swiss Franc"\n  }\n]\n'
            ),
        ],
        {
            'result': [
                {'Name': 'EURUSD', 'Description': 'Euro vs US Dollar'},
                {'Name': 'EURCHF', 'Description': 'Euro vs Swiss Franc'},
            ],
            'line': 15,
        },
        0,
    ),
    (
        'key: the result alone, from the first line',
        [
            '--key=Live',
            '--text=[\n  {\n    "Broker": "<broker>",\n    "Live": false,\n    "DepositCurrency": "EUR"\n  }\n]\n',
        ],
        {'result': [{'Broker': '<broker>', 'Live': False, 'DepositCurrency': 'EUR'}], 'line': 1},
        0,
    ),
    (
        'key: a banner and a header before the result of a shell-routed read',
        [
            '--key=alerts',
            (
                '--text=cTrader CLI\n\nConnecting as trader@example.com...\nLogged in.\n\n'
                'Using account: #<account> <broker> EUR <balance> demo\n\n'
                '[2000-01-01 21:30:39 +00:00] alerts\n\n{\n  "alerts": []\n}\n'
            ),
        ],
        {'result': {'alerts': []}, 'line': 10},
        0,
    ),
    (
        'key: windows line ends',
        [
            '--key=Live',
            (
                '--text=2000-01-01 23:37:29.7784|INFO|ConnectionStateMachine|Moving state to: AccountsShowing\r\n'
                '[\r\n  {\r\n    "Broker": "<broker>",\r\n    "Live": false,\r\n    "DepositCurrency": "EUR"\r\n  }\r\n]\r\n'
            ),
        ],
        {'result': [{'Broker': '<broker>', 'Live': False, 'DepositCurrency': 'EUR'}], 'line': 2},
        0,
    ),
    (
        'key: JSON of connection settings is never the result, nor is a copy whose opening line is lost',
        [
            '--key=Live',
            (
                '--text=2000-01-01 23:37:29.7784|INFO|ConnectionStateMachine|Moving state to: AccountsShowing\n'
                '{"clientip": "192.0.2.1","date": 1,"proxies":[]}.\n'
                '    "Live": false,\n'
                '2000-01-01 23:37:29.9318|INFO|ConnectionManager|DisconnectFromCId reason: Manually\n'
            ),
        ],
        {},
        4,
        {'absent': ['result', 'line']},
    ),
    (
        'key: an empty result alone',
        ['--key=Live', '--text=[]\n'],
        {'result': [], 'line': 1},
        0,
    ),
    (
        'key: an empty result as the message of a log line',
        [
            '--key=Live',
            (
                '--text=2000-01-01 23:37:29.7784|INFO|ConnectionStateMachine|Moving state to: AccountsShowing\n'
                '2000-01-01 23:37:29.9318|INFO|UserOutput.NLog.LoggerName|[]\n'
                '2000-01-01 23:37:29.9318|INFO|ConnectionManager|DisconnectFromCId reason: Manually\n'
            ),
        ],
        {'result': [], 'line': 2},
        0,
    ),
    (
        'key: a banner and nothing else finds nothing',
        ['--key=Live', '--text=cTrader CLI\nRun with --help to see all available command-line options.\n'],
        {},
        4,
        {'absent': ['result', 'line']},
    ),
    (
        'periods: the plain token line after the line that repeats the command',
        ['--periods', '--text=dotnet periods\nt1 t2 m1 m5 h1 h4 D1 W1 Month1 Re10 Ra10 Hm1 HMonth1\n'],
        {'result': ['t1', 't2', 'm1', 'm5', 'h1', 'h4', 'D1', 'W1', 'Month1', 'Re10', 'Ra10', 'Hm1', 'HMonth1'], 'line': 2},
        0,
    ),
    (
        'periods: the plain token line wins over a log line that holds the same tokens first',
        [
            '--periods',
            (
                '--text=ctrader-cli.exe periods\n'
                '2000-01-01 23:35:39.9513|INFO|ConsoleApplicationLifecycleStateMachine|Entering state: FramePeriodsShowing\n'
                '2000-01-01 23:35:39.9719|INFO|UserOutput.NLog.LoggerName|'
                't1 t2 m1 m5 h1 h4 D1 W1 Month1 Re10 Ra10 Hm1 HMonth1\n'
                '2000-01-01 23:35:39.9758|INFO|ConnectionManager|DisconnectFromCId reason: Manually\n'
                't1 t2 m1 m5 h1 h4 D1 W1 Month1 Re10 Ra10 Hm1 HMonth1\n'
                '2000-01-01 23:35:39.9916|INFO|CIdConnection|Pipeline Disposed. Reason: Manually\n'
            ),
        ],
        {'result': ['t1', 't2', 'm1', 'm5', 'h1', 'h4', 'D1', 'W1', 'Month1', 'Re10', 'Ra10', 'Hm1', 'HMonth1'], 'line': 5},
        0,
    ),
    (
        'periods: the tokens only as the message of a log line',
        [
            '--periods',
            (
                '--text=2000-01-01 23:31:16.0501|INFO|ConsoleApplicationLifecycleStateMachine|'
                'Entering state: FramePeriodsShowing\n'
                '2000-01-01 23:31:16.0648|INFO|UserOutput.NLog.LoggerName|'
                't1 t2 m1 m5 h1 h4 D1 W1 Month1 Re10 Ra10 Hm1 HMonth1\n'
                '2000-01-01 23:31:16.0648|INFO|ConnectionManager|DisconnectFromCId reason: Manually\n'
            ),
        ],
        {'result': ['t1', 't2', 'm1', 'm5', 'h1', 'h4', 'D1', 'W1', 'Month1', 'Re10', 'Ra10', 'Hm1', 'HMonth1'], 'line': 2},
        0,
    ),
    (
        'periods: usage text holds no token line',
        ['--periods', '--text=dotnet periods -e\nError: Parameter e is not allowed\nUsage:\n  dotnet periods\n'],
        {},
        4,
        {'absent': ['result', 'line']},
    ),
    (
        'periods: a parameter table row that names m1 without h1 is no token line',
        [
            '--periods',
            (
                '--text=Backtesting cBot with parameters:\n'
                '| Symbol               | EURUSD                    | cmd arg              |\n'
                '| Period               | m1                        | cmd arg              |\n'
            ),
        ],
        {},
        4,
        {'absent': ['result', 'line']},
    ),
    (
        'message: windows line ends stay out of the text',
        [
            '--message=Error:',
            (
                '--text=cTrader CLI\r\n[2000-01-01 21:31:23 +00:00] build /nope/project\r\n\r\n'
                "Error: Project not found: '/nope/project'.\r\n"
            ),
        ],
        {'text': "Error: Project not found: '/nope/project'.", 'line': 4},
        0,
    ),
    (
        'message: a plain line, after the banner and the header',
        [
            '--message=Error:',
            (
                '--text=cTrader CLI\n[2000-01-01 21:31:23 +00:00] build /nope/project\n\n'
                "Error: Project not found: '/nope/project'.\n"
            ),
        ],
        {'text': "Error: Project not found: '/nope/project'.", 'line': 4},
        0,
    ),
    (
        'message: inside a log line only',
        [
            '--message=Error:',
            (
                '--text=2000-01-01 23:35:41.1094|INFO|ConsoleApplicationLifecycleStateMachine|Entering state: UsageShowing\n'
                '2000-01-01 23:35:41.1094|INFO|UserOutput.NLog.LoggerName|Error: Parameter no-such-flag is not allowed\n'
            ),
        ],
        {'text': 'Error: Parameter no-such-flag is not allowed', 'line': 2},
        0,
    ),
    (
        'message: the plain line wins over a log line that holds the same message first',
        [
            '--message=Error:',
            (
                '--text=2000-01-01 23:35:41.1094|INFO|UserOutput.NLog.LoggerName|'
                'Error: Parameter no-such-flag is not allowed\n'
                'Error: Parameter no-such-flag is not allowed\n'
                'Usage:\n'
            ),
        ],
        {'text': 'Error: Parameter no-such-flag is not allowed', 'line': 2},
        0,
    ),
    (
        'message: a line that does not start with Error',
        ['--message=Invalid ctid', '--text=Invalid ctid or password\n'],
        {'text': 'Invalid ctid or password', 'line': 1},
        0,
    ),
    (
        'message: no line starts with the text',
        ['--message=Error:', '--text=cTrader CLI\n'],
        {},
        4,
        {'absent': ['text', 'line']},
    ),
    ('usage: two modes at once', ['--key=Live', '--periods', '--text=[]'], {}, 2),
    ('usage: no mode', ['--text=[]'], {}, 2),
]


def _build_parser() -> argparse.ArgumentParser:
    """Build the command line parser.

    Returns:
        The parser.
    """
    parser = argparse.ArgumentParser(
        prog='extract_result.py',
        description=(
            'Find the result in the captured standard output of a cTrader CLI command. Give the output with --file or '
            '--text and one mode: --key, --periods or --message. A result prints one line of JSON, '
            '{"result": <value>, "line": <n>} ({"text": <message>, "line": <n>} for --message), where <n> is the '
            'line the result starts on, counted from 1, and the script exits 0. When nothing is found it prints '
            '{"error": <reason>}, writes "error: <reason>" on standard error and exits 4. A call it cannot read '
            'exits 2.'
        ),
        epilog=(
            'With --key, a line or the message of a log line that is exactly [] is the empty result when no JSON '
            'value holds the key. It is an empty result only when the command itself ended with exit code 0, which '
            'this script is not given.\n\n'
            'Examples:\n'
            '  python3 <skill folder>/scripts/extract_result.py --file=out.txt --key=Live\n'
            '  python <skill folder>/scripts/extract_result.py --file=out.txt --periods\n'
            '  py <skill folder>/scripts/extract_result.py --file=out.txt --message=Error:\n'
            '  python3 <skill folder>/scripts/extract_result.py --self-test'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--file', metavar='PATH', help='The file that holds the captured standard output.')
    source.add_argument('--text', metavar='TEXT', help='The captured standard output itself.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        '--key',
        metavar='NAME',
        help=(
            'The name of a key only the result carries, without quotes or colon, such as Live for batch accounts. '
            'Prints the JSON value that holds "NAME": and the line of its opening bracket.'
        ),
    )
    mode.add_argument(
        '--periods',
        action='store_true',
        help='Prints the tokens of the periods command, in the order printed.',
    )
    mode.add_argument(
        '--message',
        metavar='TEXT',
        help=(
            'Prints the first plain line that starts with TEXT, such as Error:, or else the message of the first '
            'log line that starts with it.'
        ),
    )
    parser.add_argument('--self-test', action='store_true', help='Run the built-in cases and exit 0 when all pass.')
    return parser


def _message(line: str) -> str | None:
    """Return the message of a log line, the text after its third ``|``.

    Args:
        line: A line of the output.

    Returns:
        The message, or ``None`` when the line is no log line.
    """
    if not _LOG_LINE.match(line):
        return None
    parts = line.split('|', 3)
    return parts[3] if len(parts) == 4 else None


def _opening_bracket(line: str) -> int | None:
    """Return where a JSON value can open on a line.

    Args:
        line: A line of the output.

    Returns:
        The column of the bracket when the line starts with ``[`` or ``{``, or when it is a log line whose message
        does, else ``None``.
    """
    if line.startswith(_OPENERS):
        return 0
    message = _message(line)
    if message is not None and message.startswith(_OPENERS):
        return len(line) - len(message)
    return None


def _holds(value: object, key: str) -> bool:
    """Tell whether a JSON value carries a key, at any depth.

    Args:
        value: The parsed value.
        key: The key.

    Returns:
        Whether an object inside the value, or the value itself, has the key.
    """
    if isinstance(value, dict):
        return key in value or any(_holds(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_holds(item, key) for item in value)
    return False


def _find_key(lines: list[str], key: str) -> tuple[object, int] | None:
    """Find the JSON value that holds a key.

    From each line that holds ``"<key>":``, go up to the nearest line, that line included, where a JSON value can
    open, and read one value from that bracket on. The first value that parses and holds the key is the result.

    Args:
        lines: The lines of the output.
        key: The key.

    Returns:
        The value and the 1-based line it opens on, or ``None``.
    """
    needle = f'"{key}":'
    text = '\n'.join(lines)
    decoder = json.JSONDecoder()
    offset = 0
    nearest: tuple[int, int] | None = None
    for index, line in enumerate(lines):
        bracket = _opening_bracket(line)
        if bracket is not None:
            nearest = (index, offset + bracket)
        offset += len(line) + 1
        if needle not in line or nearest is None:
            continue
        try:
            value, _end = decoder.raw_decode(text, nearest[1])
        except json.JSONDecodeError:
            continue
        if _holds(value, key):
            return value, nearest[0] + 1
    return None


def _find_empty(lines: list[str]) -> int | None:
    """Find the empty result: a line, or the message of a log line, that is exactly ``[]``.

    Args:
        lines: The lines of the output.

    Returns:
        The 1-based line of the first one, or ``None``.
    """
    for index, line in enumerate(lines):
        message = _message(line)
        if line.rstrip() == _EMPTY or (message is not None and message.strip() == _EMPTY):
            return index + 1
    return None


def _find_periods(lines: list[str]) -> tuple[list[str], int] | None:
    """Find the tokens of the periods command.

    Args:
        lines: The lines of the output.

    Returns:
        The tokens and their 1-based line: the first line that holds ``m1`` and ``h1`` as separate words and is no
        log line, else the first log line whose message does; ``None`` when neither exists.
    """
    for index, line in enumerate(lines):
        if _message(line) is None and _PERIOD_WORDS.issubset(line.split()):
            return line.split(), index + 1
    for index, line in enumerate(lines):
        message = _message(line)
        if message is not None and _PERIOD_WORDS.issubset(message.split()):
            return message.split(), index + 1
    return None


def _find_message(lines: list[str], start: str) -> tuple[str, int] | None:
    """Find a message such as an ``Error:`` line.

    Args:
        lines: The lines of the output.
        start: The text the message starts with.

    Returns:
        The whole plain line that starts with the text, or else the message of a log line that starts with it, without
        trailing white space, and its 1-based line; ``None`` when neither exists.
    """
    for index, line in enumerate(lines):
        if _message(line) is None and line.startswith(start):
            return line.rstrip(), index + 1
    for index, line in enumerate(lines):
        message = _message(line)
        if message is not None and message.startswith(start):
            return message.rstrip(), index + 1
    return None


def _emit(payload: dict[str, object]) -> None:
    """Write one line of JSON on standard output.

    Args:
        payload: The object to write.
    """
    sys.stdout.write(json.dumps(payload, ensure_ascii=True, separators=(',', ':')) + '\n')


def _refuse(reason: str, exit_code: int) -> int:
    """Report a refusal on both streams.

    Args:
        reason: Why the call has no answer.
        exit_code: The exit code to return.

    Returns:
        The exit code.
    """
    sys.stderr.write(f'error: {reason}\n')
    _emit({'error': reason})
    return exit_code


def _answer(args: argparse.Namespace, text: str) -> int:
    """Find what the mode asks for and print it.

    Args:
        args: The parsed command line.
        text: The captured output.

    Returns:
        The exit code.
    """
    lines = text.split('\n')
    if args.periods:
        periods = _find_periods(lines)
        if periods is None:
            return _refuse('no line holds the period tokens m1 and h1', EXIT_NOT_FOUND)
        _emit({'result': periods[0], 'line': periods[1]})
        return EXIT_OK
    if args.message is not None:
        message = _find_message(lines, args.message)
        if message is None:
            return _refuse(f'no line starts with {args.message!r}', EXIT_NOT_FOUND)
        _emit({'text': message[0], 'line': message[1]})
        return EXIT_OK
    found = _find_key(lines, args.key)
    if found is not None:
        _emit({'result': found[0], 'line': found[1]})
        return EXIT_OK
    empty = _find_empty(lines)
    if empty is None:
        return _refuse(f'no JSON value holds the key "{args.key}" and no line is the empty result []', EXIT_NOT_FOUND)
    _emit({'result': [], 'line': empty})
    return EXIT_OK


def _mismatches(expected: object, printed: object, path: str, tolerance: float) -> list[str]:
    """Compare a printed value with the value a case expects.

    Args:
        expected: The value the case expects.
        printed: The value the script printed.
        path: The key path of the value.
        tolerance: The absolute tolerance of numbers.

    Returns:
        One description per difference.
    """
    difference = [f'{path}: expected {expected!r}, got {printed!r}']
    if expected is None or isinstance(expected, bool | str):
        return [] if type(printed) is type(expected) and printed == expected else difference
    if isinstance(expected, int | float):
        if isinstance(printed, bool) or not isinstance(printed, int | float):
            return difference
        return [] if abs(printed - expected) <= tolerance else difference
    if isinstance(expected, dict):
        if not isinstance(printed, dict):
            return difference
        problems: list[str] = []
        for key, value in expected.items():
            if key in printed:
                problems.extend(_mismatches(value, printed[key], f'{path}.{key}', tolerance))
            else:
                problems.append(f'{path}.{key}: missing')
        return problems
    if not isinstance(expected, list | tuple) or not isinstance(printed, list) or len(printed) != len(expected):
        return difference
    return [
        problem
        for index, (value, item) in enumerate(zip(expected, printed, strict=True))
        for problem in _mismatches(value, item, f'{path}[{index}]', tolerance)
    ]


def _run_case(argv: list[str]) -> tuple[int, object]:
    """Run one call of the script inside the process.

    Args:
        argv: The arguments of the call.

    Returns:
        The exit code and the one JSON value standard output holds, or ``None`` when it does not hold exactly one line:
        every line the script prints on standard output is JSON, and its help is more than one line.
    """
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            exit_code = main(argv)
        except SystemExit as stop:
            exit_code = stop.code if isinstance(stop.code, int) else EXIT_USAGE
    printed = out.getvalue().splitlines()
    if len(printed) != 1:
        return exit_code, None
    answer: object = json.loads(printed[0])
    return exit_code, answer


def _self_test() -> int:
    """Run every case of ``SELF_TEST_CASES`` and name each one that fails on standard error.

    Returns:
        0 when every case passes, else 1.
    """
    failed = 0
    for case in SELF_TEST_CASES:
        label, argv, expected, exit_code = case[:4]
        checks: dict[str, Any] = case[4] if len(case) == 5 else {}
        code, answer = _run_case(list(argv))
        problems = [] if code == exit_code else [f'exit code: expected {exit_code}, got {code}']
        if not isinstance(answer, dict):
            if expected:
                problems.append('printed no JSON object')
        else:
            problems.extend(_mismatches(expected, answer, 'answer', checks.get('tolerance', DEFAULT_TOLERANCE)))
            problems.extend(f'{key}: printed, expected absent' for key in checks.get('absent', ()) if key in answer)
        if problems:
            failed += 1
            sys.stderr.write(f'FAIL {label}: {"; ".join(problems)}\n')
    sys.stderr.write(f'{len(SELF_TEST_CASES) - failed} of {len(SELF_TEST_CASES)} cases passed\n')
    return 1 if failed else 0


def _usage_error(parser: argparse.ArgumentParser, message: str) -> NoReturn:
    """Stop with a usage error, exit 2, writing only to standard error.

    Args:
        parser: The parser.
        message: What is wrong with the call.
    """
    parser.error(message)


def main(argv: list[str] | None = None) -> int:
    """Run the script.

    Args:
        argv: The arguments, else those of the process.

    Returns:
        The exit code.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        return _self_test()
    if args.key is None and not args.periods and args.message is None:
        _usage_error(parser, 'one of --key, --periods or --message is required')
    if args.key == '' or args.message == '':
        _usage_error(parser, 'the value of --key or --message must not be empty')
    file: str | None = args.file
    text: str | None = args.text
    if text is not None:
        return _answer(args, text)
    if file is None:
        _usage_error(parser, 'one of --file or --text is required')
    try:
        captured = Path(file).read_bytes().decode('utf-8', errors='replace')
    except OSError as error:
        return _refuse(f'cannot read {file}: {error.strerror}', EXIT_USAGE)
    return _answer(args, captured)


if __name__ == '__main__':
    sys.exit(main())
