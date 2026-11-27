#!/bin/bash

# Install cTrader Skills for Claude Code or Deep Agents Code.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default values
TARGET="claude"  # claude or deepagents
GLOBAL=false
FORCE=false
YES=false
TARGET_DIR=""

usage() {
    cat <<'EOF'
Usage: install.sh [OPTIONS] [DIRECTORY]

Install cTrader Skills for Claude Code or Deep Agents Code.

Arguments:
  DIRECTORY           Target project directory (default: current directory)
                      Ignored when --global is used

Options:
  --claude            Install for Claude Code (default)
  --deepagents        Install for Deep Agents Code
  --global, -g        Install globally (~/.claude or ~/.deepagents/agent)
                      Default: install in current directory
  --force, -f         Overwrite skills with same names as this package
  --yes, -y           Skip confirmation prompts
  --help, -h          Show this help message

Examples:
  ./install.sh                          # Claude Code, current directory (default)
  ./install.sh ~/my-project             # Claude Code, ~/my-project
  ./install.sh --global                 # Claude Code, ~/.claude
  ./install.sh --deepagents ~/my-project  # Deep Agents Code, ~/my-project
  ./install.sh -f -y                    # Force reinstall, no prompts
EOF
}

# Report wrong arguments with the usage text on stderr and stop before installing anything.
usage_error() {
    echo "$1" >&2
    usage >&2
    exit 2
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --claude)
            TARGET="claude"
            shift
            ;;
        --deepagents)
            TARGET="deepagents"
            shift
            ;;
        --global|-g)
            GLOBAL=true
            shift
            ;;
        --force|-f)
            FORCE=true
            shift
            ;;
        --yes|-y)
            YES=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        -*)
            usage_error "Unknown option: $1"
            ;;
        *)
            if [ -n "$TARGET_DIR" ]; then
                usage_error "Error: multiple directories specified: '$TARGET_DIR' and '$1'"
            fi
            TARGET_DIR="$1"
            shift
            ;;
    esac
done

if [ -z "$TARGET_DIR" ]; then
    TARGET_DIR="$(pwd)"
fi

if [ "$TARGET" = "claude" ]; then
    if [ "$GLOBAL" = true ]; then
        INSTALL_DIR="$HOME/.claude"
    else
        INSTALL_DIR="$TARGET_DIR/.claude"
    fi
    TOOL_NAME="Claude Code"
else
    if [ "$GLOBAL" = true ]; then
        INSTALL_DIR="$HOME/.deepagents/agent"
    else
        INSTALL_DIR="$TARGET_DIR/.deepagents"
    fi
    TOOL_NAME="Deep Agents Code"
fi

echo "------------------------------------------------------------"
echo "cTrader Skills Installer"
echo "------------------------------------------------------------"
echo ""
echo "Target:    $TOOL_NAME"
echo "Location:  $INSTALL_DIR"
if [ "$GLOBAL" = true ]; then
    echo "Scope:     Global (all projects)"
else
    echo "Scope:     Local (current directory)"
fi
echo ""

if [ "$YES" != true ]; then
    read -r -p "Proceed with installation? (y/n): " REPLY
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
fi

echo ""
echo "Installing..."

# The install folder may hold the user's own files, such as an agent's AGENTS.md and memories/ or other skills, so
# only the package's own skill folders are written, and --force replaces only those.
mkdir -p "$INSTALL_DIR"

if [ -d "$SCRIPT_DIR/skills" ]; then
    mkdir -p "$INSTALL_DIR/skills"
    for skill in "$SCRIPT_DIR/skills"/*; do
        [ -d "$skill" ] || continue
        skill_name=$(basename "$skill")
        if [ -d "$INSTALL_DIR/skills/$skill_name" ]; then
            if [ "$FORCE" = true ]; then
                rm -rf "$INSTALL_DIR/skills/$skill_name"
            else
                echo "Skipping $skill_name (already exists, use --force to overwrite)"
                continue
            fi
        fi
        cp -r "$skill" "$INSTALL_DIR/skills/$skill_name"
        echo "Installed $skill_name"
    done
else
    echo "ERROR: skills directory not found at $SCRIPT_DIR/skills" >&2
    exit 1
fi

echo ""
echo "------------------------------------------------------------"
echo "Installation complete."
echo "------------------------------------------------------------"
echo ""
echo "Skills installed to $TOOL_NAME at: $INSTALL_DIR"
echo ""
echo "To see installed skills:"
echo "  ls '$INSTALL_DIR/skills/'"
echo ""
if [ "$TARGET" = "deepagents" ]; then
    if [ "$GLOBAL" = true ]; then
        echo "A dcode run finds the skills, since they are installed for the default agent."
        echo ""
    fi
    echo "For usage and configuration, see:"
    echo "  https://docs.langchain.com/oss/deepagents/code/overview"
else
    echo "For usage and configuration, see:"
    echo "  https://code.claude.com/docs/en/overview"
fi
echo ""
