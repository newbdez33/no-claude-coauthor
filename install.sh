#!/bin/sh
set -eu

project_dir=$(CDPATH= cd "$(dirname "$0")" && pwd -P)
hooks_dir="$project_dir/hooks"
status=0
current=$(git config --global --get-all core.hooksPath) || status=$?
case "$status" in
    0)
        if [ "$current" != "$hooks_dir" ]; then
            echo "no-claude-coauthor: an existing global core.hooksPath must be kept." >&2
            echo "Use the existing-hook integration in README.md. No settings were changed." >&2
            exit 1
        fi
        ;;
    1) ;;
    *) exit "$status" ;;
esac

for file in "$project_dir/bin/check-message" "$hooks_dir"/*; do
    if [ ! -x "$file" ]; then
        echo "no-claude-coauthor: hook files must be executable: $file" >&2
        exit 1
    fi
done

git config --global core.hooksPath "$hooks_dir"
printf 'Global hooks enabled: %s\n' "$hooks_dir"
echo "Keep this checkout at this path. Local core.hooksPath settings can override it."
