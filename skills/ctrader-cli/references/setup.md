# Session preflight and setup guidance

Run this four-step preflight before the first authenticated call in a session, and whenever an authenticated call fails in a way that looks credential-related rather than usage-related.
Each step reports presence and length only; never print or log the value of `CTID` or `PWD-FILE`, and never echo the contents of the password file.

The CLI runs natively on every platform. On Windows it installs with winget as `ctrader-cli.exe`; on macOS and Linux it installs with Homebrew from the Spotware tap as `ctrader-cli` — the same CLI with identical verbs, flags, and environment variables. Each step below gives both shapes where they differ; where only one shape appears, drop the `.exe` suffix on macOS and Linux.

## Step 1: executable reachability

Confirm the CLI is runnable and report its version.

Windows (native install):

```bash
command -v ctrader-cli.exe
timeout 30 ctrader-cli.exe --version </dev/null
```

`command -v` exits 0 with the full path to the executable (for example `C:\Users\<you>\AppData\Local\Programs\cTrader CLI\ctrader-cli.exe`).
`--version` exits 0 with stdout `Version: 5.9.0.38` (or later); stderr echoes the invoked command line, which is benign and appears on every call this preflight prescribes (all batch-routed), success or failure — interactive-routed invocations and pre-routing argument-parse failures omit the echo.
`--version` accepts `-e` without complaint even though it has no matching option to resolve: it short-circuits before option validation, unlike most other verbs.
On Windows the output uses CRLF line endings, so a parser that strips only `\n` from captured `--version` output leaves a trailing `\r` in the extracted version string; strip both.

macOS and Linux (Homebrew install):

```bash
command -v ctrader-cli
timeout 30 ctrader-cli --version </dev/null
```

If neither shape works, the CLI is not reachable yet.

On macOS, GNU `timeout` is not preinstalled; it comes with coreutils (`brew install coreutils`). For these short read-only probes, running without the `timeout` wrapper is an acceptable fallback until coreutils is installed.

## Step 2: credential presence and length

Check for `CTID` and `PWD-FILE` using a quoted argument to `printenv`, captured through command substitution, never a raw pipe into `wc -c` and never direct `$VARNAME` interpolation.
`PWD-FILE` contains a hyphen, which makes it an illegal bash identifier: `$PWD-FILE` does not raise an error, it silently expands `$PWD` (the current directory) followed by the literal text `-FILE`, with no error to signal the mistake.
A raw `printenv "PWD-FILE" | wc -c` pipe over-counts the true length by one, because `printenv` appends a trailing newline that `wc -c` counts along with the value.
The correct idiom captures the value into a variable first, then measures the shell's own length operator:

```bash
val="$(printenv 'CTID')"; echo "CTID: ${#val} characters"
val="$(printenv 'PWD-FILE')"; echo "PWD-FILE: ${#val} characters"
```

These idioms work identically in Git Bash on Windows and in any POSIX shell on macOS or Linux.
An empty result (`0 characters`, or the variable failing to capture anything) means the variable is not set in this session. Report presence and length only, for example "CTID: present, 22 characters" or "CTID: absent" -- never the value itself.

On macOS and Linux, `PWD-FILE` is commonly absent from the shell environment even in a correctly configured setup, because a hyphenated name cannot be assigned with plain `export` in a POSIX shell. That absence is not a failure: the Step 4 probe supplies the password-file path per invocation instead (an explicit `--pwd-file` flag, or an `env "PWD-FILE=..."` prefix). On those platforms, Step 2 therefore checks `CTID` only, and Step 3 checks the password file at its conventional path.

## Step 3: password-file sanity

Confirm the file at the `PWD-FILE` path exists and that its first line has nonzero length, again reporting presence and length only, never content:

```bash
val="$(printenv 'PWD-FILE')"
val="${val:-$HOME/.ctrader/pass.pwd}"
if [ -f "$val" ]; then
  first_line_len=$(head -n 1 "$val" | tr -d '\r\n' | wc -c)
  echo "Password file exists; first line length: $first_line_len"
else
  echo "Password file not found at the configured PWD-FILE path"
fi
```

The password file's first line is the password itself; the CLI reads only that first line, so trailing lines are not consulted.

## Step 4: the go/no-go probe

Run the single authoritative probe with stdin redirected, and read the exit code directly rather than through a pipe.

Windows (native install):

```bash
timeout 30 ctrader-cli.exe accounts -e </dev/null; echo "EXIT:$?"
```

macOS and Linux — `-e` resolves `CTID` from the environment while the password-file path is passed explicitly (an explicit flag always wins over the matching variable, so the mix is well-defined):

```bash
timeout 30 ctrader-cli accounts -e --pwd-file="$HOME/.ctrader/pass.pwd" </dev/null; echo "EXIT:$?"
```

The alternative shape, which keeps the command line identical to the Windows one, supplies `PWD-FILE` through `env` (which accepts hyphenated names that plain `export` cannot set):

```bash
env "PWD-FILE=$HOME/.ctrader/pass.pwd" timeout 30 ctrader-cli accounts -e </dev/null; echo "EXIT:$?"
```

Four outcomes are possible:

- **Exit 0, stdout a JSON array of account objects.** The CLI is ready for authenticated calls. Report the account number(s) and each account's `Live` field (demo vs live) back to the user; never assume a fresh session is a demo account without checking `Live`.
- **Exit 81, stdout `Invalid ctid or password`.** The CTID value or the password file's content is wrong. Tell the user their credentials were rejected and ask them to re-check the email address in `CTID` and the password text in the file at `PWD-FILE` (first line only, no extra whitespace or trailing newline pasted in by an editor).
- **Exit 1, stdout `Error: Password file not found` plus a usage block.** The configured password-file path points at a file that does not exist. Ask the user to confirm the path in `PWD-FILE` (or the one passed to `--pwd-file`) matches an actual file.
- **Exit 1, stdout a missing-parameter message (for example `Error: Should be specified parameter: --pwd-file`) plus a usage block.** A fast, deterministic failure, never a hang: `-e` was omitted from the command line, or the variables are absent from this terminal's environment. A session or license cache can let `accounts -e` succeed even when the two variables are absent, so re-run Step 2 to confirm both variables are actually set in the current terminal before looking further.

Always redirect stdin, bound the call with the `timeout` wrapper, and always read `$?` directly, so a misconfigured session fails fast instead of leaving the agent waiting on a prompt that will never be answered.

## User-facing remediation text

Use this wording verbatim (adjusting only the account details and paths) when a step above indicates the user needs to act. Every command below is copy-pasteable as written; give the user the block that matches their OS.

If Step 1 fails on Windows:

> cTrader CLI is not installed or not on PATH. Install it with `winget install Spotware.cTrader.CLI`, then open a new terminal so PATH updates take effect.

If Step 1 fails on macOS or Linux:

> Install the cTrader CLI with Homebrew:
>
> ```text
> brew tap spotware/tap https://github.com/spotware/homebrew-tap
> brew install spotware/tap/ctrader-cli
> ```
>
> This puts the `ctrader-cli` executable on your PATH; it is the same CLI with the same commands and flags.

If `CTID` is absent in Step 2, on Windows:

> Set your cTrader ID (the email address you log in with) as a persistent environment variable:
>
> ```text
> setx CTID "you@example.com"
> ```
>
> Then open a new terminal.

If `CTID` is absent in Step 2, on macOS or Linux:

> Add your cTrader ID (the email address you log in with) to your shell profile (`~/.zshrc` or `~/.bashrc`):
>
> ```text
> export CTID="you@example.com"
> ```
>
> Then open a new shell, or run `source` on the profile file.

If `PWD-FILE` is absent in Step 2, or Step 3 reports the file missing, on Windows:

> Create a plain text file whose first line is your cTrader password, for example `C:\Users\<you>\.ctrader\pass.pwd`, then set:
>
> ```text
> setx PWD-FILE "C:\Users\<you>\.ctrader\pass.pwd"
> ```
>
> Then open a new terminal.

If Step 3 reports the file missing, on macOS or Linux:

> Create a plain text file whose first line is your cTrader password, at `~/.ctrader/pass.pwd`. No environment variable is needed for it: a hyphenated name like `PWD-FILE` cannot be set with plain `export`, so pass the path per invocation instead — either `--pwd-file="$HOME/.ctrader/pass.pwd"` on the command line, or an `env "PWD-FILE=$HOME/.ctrader/pass.pwd"` prefix (the Step 4 probe shows both shapes).

If Step 4 returns exit 81:

> Your credentials were rejected. Re-check the email address in `CTID` and the password text in the file at `PWD-FILE` (first line only, no extra whitespace).

If Step 4 returns the missing-parameter branch after Steps 2 and 3 both looked correct:

> Open a fresh terminal (variables set with `setx` on Windows, or added to a shell profile on macOS/Linux, only take effect in sessions started afterwards) and re-run the probe in Step 4.

The canonical credential flag is `--pwd-file`; `--password-file` is not part of the option set and returns a usage message rather than being accepted as an alias, so never suggest it to a user or use it in a scripted invocation. `--password` belongs to interactive use and should not appear in a scripted invocation either.

## Why a new terminal is required

Persistent environment variables take effect only in sessions started after they were written: `setx` on Windows updates the registry-backed value without touching any running terminal, and a profile `export` on macOS or Linux is only read when a new shell starts (or the profile is explicitly sourced).
Every existing shell keeps the environment it started with until it is closed and a new one is opened, which is why each remediation message above that sets a persistent variable ends with "open a new terminal" before retrying.
An agent that runs the Step 4 probe in the same terminal session where the user just configured the variable will see the same failure as before, even though the value is now set correctly for future sessions; this is expected, and the fix is a new terminal, not a different probe command.
