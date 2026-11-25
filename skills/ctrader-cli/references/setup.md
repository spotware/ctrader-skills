# Setup and session preflight

Each step reports presence and length only: never print or log the value of `CTID` or `PWD-FILE`, and never echo the contents of the password file.

## Install routes

The executable name and the way the CLI is started differ by route. Builds differ in their options and in some commands, so read the `--help` of the build you run.

- Windows, winget: `winget install Spotware.cTrader.CLI` installs `ctrader-cli.exe`.
- Windows, the copy bundled with the cTrader desktop application: the application ships a copy of the CLI, usually in `C:\Users\<you>\AppData\Local\Spotware\cTrader\<installation id>\`. Add that folder to `PATH` to call it by name, or call it by its full path.
- macOS and Linux, Homebrew: `brew tap spotware/tap https://github.com/spotware/homebrew-tap`, then `brew install spotware/tap/ctrader-cli`, installs `ctrader-cli`.
- Any OS with Docker, the container image: the CLI is also published as a Linux container image, which also runs on Windows through Docker Desktop with WSL. Pull it with `docker pull ghcr.io/spotware/ctrader-console:latest` and run it with `docker run --rm ghcr.io/spotware/ctrader-console:latest <arguments>`; the arguments after the image name go to the CLI.

In the container, a host file, such as the password file or an `.algo`, reaches the CLI only through a mount (`--mount type=bind,src=<host folder>,dst=<container folder>`), and every path argument is the path inside the container. Pass the credentials as options after the image name, with the password file mounted: `--ctid=<ctid> --pwd-file=<path inside the container>`. The container's `--help` names the program `dotnet` in its examples: type the `docker run` form instead. Header timestamps carry the container's clock.

## Step 1: the executable answers

Windows, winget or the bundled copy:

```bash
command -v ctrader-cli.exe
timeout 30 ctrader-cli.exe --version </dev/null
```

`command -v` exits 0 with the full path to the executable, for example `C:\Users\<you>\AppData\Local\Programs\cTrader CLI\ctrader-cli.exe`. The bundled copy answers only when its folder is on `PATH`; otherwise call it by its full path.

macOS and Linux, Homebrew:

```bash
command -v ctrader-cli
timeout 30 ctrader-cli --version </dev/null
```

The container image:

```bash
docker run --rm ghcr.io/spotware/ctrader-console:latest --version
```

`--version` exits 0 with a line `Version: <build>`, which can follow a line that repeats the command. On Windows the output uses CRLF line endings, so a parser that strips only `\n` leaves a trailing `\r` in the version string; strip both. If no form answers, the CLI is not reachable yet.

On macOS, GNU `timeout` is not preinstalled; it comes with coreutils (`brew install coreutils`). For these short read-only checks, running without the `timeout` wrapper is an acceptable fallback until coreutils is installed.

## Step 2: credential presence and length

Check for `CTID` and `PWD-FILE` with a quoted argument to `printenv`, captured through command substitution. A hyphenated name such as `PWD-FILE` is not a valid shell variable name, so `$` expansion cannot read it, and it gives no error to signal the mistake. A raw `printenv "PWD-FILE" | wc -c` pipe over-counts the length by one, because `printenv` appends a newline. Capture the value first, then measure it with the shell's own length operator:

```bash
val="$(printenv 'CTID')"; echo "CTID: ${#val} characters"
val="$(printenv 'PWD-FILE')"; echo "PWD-FILE: ${#val} characters"
```

These lines work alike in Git Bash on Windows and in any POSIX shell on macOS or Linux. `0 characters` means the variable is not set in this session. Report presence and length only, for example "CTID: present, 22 characters" or "CTID: absent", never the value.

On macOS and Linux, `PWD-FILE` is often absent even in a correct setup, because plain `export` cannot assign a hyphenated name. That absence is no failure: the Step 4 call passes the password-file path on each call instead. On those platforms, Step 2 checks `CTID` only, and Step 3 checks the password file at the path the user keeps it.

## Step 3: the password file

Confirm that the file exists and that its first line is not empty, reporting the length only, never the content:

```bash
val="$(printenv 'PWD-FILE')"
if [ -f "$val" ]; then
  first_line_len=$(head -n 1 "$val" | tr -d '\r\n' | wc -c)
  echo "Password file exists; first line length: $first_line_len"
else
  echo "Password file not found at the PWD-FILE path"
fi
```

Where `PWD-FILE` is not set, as is usual on macOS and Linux, write the path of the password file in place of `$(printenv 'PWD-FILE')`.

Put the password on the first line of the file and nothing else in it.

## Step 4: the go/no-go call

Run one call with standard input redirected and both streams captured, and read the exit code directly rather than through a pipe.

Windows:

```bash
timeout 30 ctrader-cli.exe accounts -e </dev/null 1>out.txt 2>err.txt; echo "EXIT:$?"
```

macOS and Linux, with `-e` reading `CTID` from the environment and the password-file path passed on the call (an option on the command line wins over the matching variable):

```bash
timeout 30 ctrader-cli accounts -e --pwd-file="<path to the password file>" </dev/null 1>out.txt 2>err.txt; echo "EXIT:$?"
```

The same call through `env`, which accepts the hyphenated name that plain `export` cannot set, keeps the command line equal to the Windows one:

```bash
env "PWD-FILE=<path to the password file>" timeout 30 ctrader-cli accounts -e </dev/null 1>out.txt 2>err.txt; echo "EXIT:$?"
```

The container image, with the folder of the password file mounted:

```bash
docker run --rm --mount type=bind,src=<host folder>,dst=<container folder> ghcr.io/spotware/ctrader-console:latest accounts --ctid=<ctid> --pwd-file=<container folder>/<password file> </dev/null 1>out.txt 2>err.txt; echo "EXIT:$?"
```

Read the outcome from the exit code and from lines anywhere in the output, never from the first byte: the output can hold log lines, a line that repeats the command and the result printed twice.

- **Exit 0 and a JSON array whose entries carry `"Live":`.** The CLI is ready for authenticated calls. Find the array by that key, or run `scripts/extract_result.py --file=out.txt --key=Live` from the skill's folder. Report each account's `Number` and its `Live` value (demo or live) to the user; never assume an account is a demo account without reading `Live`.
- **Exit 81 and a line `Invalid ctid or password`.** The cTrader ID or the password is wrong. Tell the user their credentials were rejected and ask them to check the email address in `CTID` and the password in the file at `PWD-FILE`: first line only, with no extra spaces.
- **Exit 1 and a line `Error: Password file not found`, with a usage block.** The password-file path points at no file. Ask the user to confirm that the path in `PWD-FILE`, or the one passed to `--pwd-file`, names an existing file.
- **Exit 1 and a missing-parameter line, such as `Error: Should be specified parameter: --pwd-file`, with a usage block.** `-e` is missing from the command line, or the variables are absent from this terminal's environment. Re-run Step 2.
- **Exit 1 and a `Missing ... in non-interactive mode.` line on standard error.** The call reached the CLI without a cTrader ID or a password file. Pass `--ctid` and `--pwd-file` as options.

Always redirect standard input, bound the call with `timeout`, and read `$?` directly, so a session with a wrong setup fails fast instead of waiting for a prompt nobody answers.

## User-facing remediation text

Use this wording, adjusting only the account details and paths, when a step above shows that the user needs to act. Each command below can be pasted as written; give the user the block for their OS.

If Step 1 fails on Windows:

> cTrader CLI is not installed or not on PATH. Install it with `winget install Spotware.cTrader.CLI`, then open a new terminal so the PATH change takes effect. If you use the copy that comes with the cTrader desktop application, add its folder to PATH or call it by its full path.

If Step 1 fails on macOS or Linux:

> Install the cTrader CLI with Homebrew:
>
> ```text
> brew tap spotware/tap https://github.com/spotware/homebrew-tap
> brew install spotware/tap/ctrader-cli
> ```
>
> This puts the `ctrader-cli` executable on your PATH; it is the same CLI with the same commands.

If Step 1 fails for the container image:

> Pull the cTrader CLI image with `docker pull ghcr.io/spotware/ctrader-console:latest`. On Windows, Docker Desktop with WSL runs it.

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

> Create a plain text file whose first line is your cTrader password and nothing else, for example `C:\Users\<you>\.ctrader\pass.pwd`, then set:
>
> ```text
> setx PWD-FILE "C:\Users\<you>\.ctrader\pass.pwd"
> ```
>
> Then open a new terminal.

If Step 3 reports the file missing, on macOS or Linux:

> Create a plain text file whose first line is your cTrader password and nothing else, for example `~/.ctrader/pass.pwd`. It needs no environment variable: plain `export` cannot set a hyphenated name like `PWD-FILE`, so pass the path on each call instead, with `--pwd-file=<path to the file>` on the command line or an `env "PWD-FILE=<path to the file>"` prefix.

If Step 4 returns exit 81:

> Your credentials were rejected. Check the email address in `CTID` and the password in the file at `PWD-FILE`: first line only, with no extra spaces.

If Step 4 returns the missing-parameter branch after Steps 2 and 3 both looked correct:

> Open a fresh terminal (variables set with `setx` on Windows, or added to a shell profile on macOS and Linux, take effect only in sessions started afterwards) and run the check in Step 4 again.

The credential option is `--pwd-file`. No longer spelling of it exists: a call that spells the name out in full gets a usage message, so never suggest one to a user or use one in a scripted call. `--password` belongs to interactive use and has no place in a scripted call either.

## Why a new terminal is required

Persistent environment variables take effect only in sessions started after they were written: `setx` on Windows updates the stored value without touching any running terminal, and a shell reads a profile `export` on macOS or Linux only when it starts or when the profile is sourced.

Every open shell keeps the environment it started with until it is closed, which is why each remediation message above that sets a persistent variable ends with "open a new terminal" before the retry. A Step 4 call in the same terminal where the user just set the variable fails as before, although the value is now set for future sessions; the fix is a new terminal, not a different call.
