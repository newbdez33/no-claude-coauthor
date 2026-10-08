# no-claude-coauthor

Global Git hooks that reject unwanted Claude Code attribution before a commit is created.

**Claude Code can add itself as a co-author even after you explicitly tell it not to.** Users have reported ignored settings and repeated violations of explicit `CLAUDE.md` instructions in [anthropics/claude-code#4287](https://github.com/anthropics/claude-code/issues/4287). [Issue #11135](https://github.com/anthropics/claude-code/issues/11135) reports attribution with the opt-out setting enabled. These are reports of real failures, not a claim that every release or session ignores the setting.

A written instruction expresses your preference. A Git hook checks the actual commit message. Attribution should be your decision.

## Install with an agent

Copy this prompt into your coding agent. It authorizes installation on your machine, including integration with existing global hooks.

```text
Install https://github.com/newbdez33/no-claude-coauthor on this machine to
prevent unwanted Claude Code attribution in future Git commits.

Read its README and shell scripts first. Use a persistent checkout at
~/.local/share/no-claude-coauthor. Reuse an existing checkout without
discarding local changes.

Inspect the global core.hooksPath and the effective setting in the current
repository. If no global hooks path exists, run install.sh. If one already
exists, preserve it and follow the README's existing-hook integration:
run bin/check-message before and after the existing prepare-commit-msg,
commit-msg, and applypatch-msg logic. Preserve existing hook behavior,
arguments, standard input, and failure status. Use the hook manager's
supported configuration, and avoid duplicate checks on repeat runs.

Also merge the README's Claude Code attribution settings into
~/.claude/settings.json, preserving unrelated settings.

Run the project tests if Python 3 is available. Then verify the installed
hooks in a temporary repository that inherits the actual global Git config.
Set a test identity only in that repository. Confirm that clean commits and
an unrelated human co-author pass, and a message containing
Co-Authored-By: Claude <noreply@anthropic.com> fails, including when supplied
with git commit --no-verify. Keep test commits out of my project repositories.

Do not rewrite existing history or push anything. Report the installed path,
configuration changes, actual test results, and any repository-local hooks
path that still overrides the global guard. Explain any incomplete step.
```

## Install

Requires Git, a Unix shell, and `grep` on macOS or Linux. Python 3 is only needed for tests.

```sh
git clone https://github.com/newbdez33/no-claude-coauthor.git "$HOME/.local/share/no-claude-coauthor"
cd "$HOME/.local/share/no-claude-coauthor"
./install.sh
```

The installer sets `git config --global core.hooksPath` to this checkout's `hooks` directory. Keep the checkout at that path. This applies to existing and future repositories that do not override the setting. See [Git's `core.hooksPath` reference](https://git-scm.com/docs/git-config#Documentation/git-config.txt-corehooksPath).

The installer refuses to replace an existing global hooks path. It does not change Claude settings or repository history. Re-running it at the same path is safe.

Inspect the effective setting inside each repository:

```sh
git config --show-origin --show-scope --get-all core.hooksPath
```

## What it blocks

The check is case-insensitive and allows leading whitespace. It rejects:

- A `Co-Authored-By:` line that contains `Claude` or `Anthropic`.
- A `Generated with Claude Code` line, including the usual Markdown link and robot prefix.
- A `Claude-Session:` line.

Unrelated human co-author trailers and ordinary text about Claude Code pass unchanged. The match is deliberately conservative: a human co-author whose name or address contains `Claude` or `Anthropic` also matches. Review `bin/check-message` if that applies to your team.

The hook returns an error and leaves the message intact. Remove the unwanted line and retry the commit.

```text
no-claude-coauthor: commit rejected: Claude attribution is not allowed.
```

## How it works

`prepare-commit-msg` checks the prepared message before the editor opens. `commit-msg` checks it after editing. `applypatch-msg` checks messages used by `git am`. Each checks both before and after the repository's own hook. All supplied hook names forward to executable hooks in the repository's usual `hooks` directory, preserving arguments, standard input, and failures.

Git skips `commit-msg` with `--no-verify`, but still runs `prepare-commit-msg`. Thus a forbidden line already present at the prepare stage is rejected even with `--no-verify`. See the [Git hooks reference](https://git-scm.com/docs/githooks).

### Existing hook managers

If `core.hooksPath` already points to another directory, keep it. Integrate the checker into that manager's `prepare-commit-msg` and `commit-msg` hooks, and optionally `applypatch-msg`:

```sh
"$HOME/.local/share/no-claude-coauthor/bin/check-message" "$1" || exit $?
```

Run this check before and after existing message-hook logic. If that logic uses `exec`, change the integration so that the final check can run, and preserve its failure status. Do not replace existing hooks with the snippet. Hook managers such as Husky or pre-commit can also set a repository-local hooks path; the global setting does not override it.

### Limits

This is a local guard, not a security boundary against an agent with shell access.

- Local or command-line `core.hooksPath` settings can bypass it. A process that can edit the hook can disable it.
- `--no-verify` skips the final check. Attribution added by an editor after the prepare check can then pass.
- Existing commits, fetched commits, fast-forward merges, low-level commit creation, and history-copying operations are not comprehensively checked.
- Web commits, GitHub squash merges, PR descriptions, and commits made on another machine do not run these local hooks.
- A line format or identity outside the documented patterns can pass. This is not a detector for all AI-written code.

For a team policy, also validate incoming commit messages on a trusted server or in a required CI check, and review generated merge messages.

## Also disable Claude Code attribution

Merge these keys into your existing `~/.claude/settings.json`; do not overwrite unrelated settings:

```json
{
  "attribution": {
    "commit": "",
    "pr": "",
    "sessionUrl": false
  }
}
```

The [official settings reference](https://code.claude.com/docs/en/settings-reference#attribution) documents these controls. It also documents `"attribution": false` for v2.1.281 and later; older versions reject that Boolean form. The old `includeCoAuthoredBy` setting is deprecated. Settings reduce unwanted output; the Git hooks provide a separate check.

## If your repository already contains unwanted attribution

**Installing a hook does not repair old commits or remove an existing GitHub contributor entry.** Once an unwanted trailer is pushed, cleanup can extend beyond the visible Git history.

First inspect the history available in your clone:

```sh
git log --all --regexp-ignore-case --extended-regexp \
  --grep='^[[:space:]]*Co-Authored-By[[:space:]]*:.*(claude|anthropic)' \
  --format='%h %s'
```

This checks local refs, not every remote PR ref, fork, cache, or clone.

There are two separate problems:

1. **The commit message.** It can be corrected. An unpublished latest commit can be amended; older or published commits require coordinated history changes. Commit IDs change. Follow [GitHub's commit-message guide](https://docs.github.com/en/pull-requests/how-tos/commit-changes/changing-a-commit-message), back up first, and agree on the impact before rewriting shared history. This project never rewrites history for you.
2. **GitHub's contributor display and retained objects.** Editing reachable history does not guarantee immediate removal from the website. Repository owners have [reported stale Claude contributor entries after cleanup](https://github.com/orgs/community/discussions/197389). That same discussion includes reports of recovery without recreating the repository, so **“an affected repository can only be fixed by rebuilding it” is not a general fact**. These are user reports, not a documented cache-reset API or guaranteed refresh schedule.

GitHub separately documents that old commits can remain in forks, cached views, and PR references after a history rewrite. Its sensitive-data removal process explicitly excludes non-sensitive data, so do not assume support will purge attribution through that process. See [GitHub's history-removal limits](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

**Rebuilding remains a fallback when a fresh repository is preferable to further cleanup.** Create a separate repository from a reviewed source snapshot or verified clean history. Do not push the unwanted history into it again. Keep the old repository until you have checked the migration. Issues, PRs, stars, releases, settings, and integrations do not automatically move with the source. A new repository also cannot erase existing forks or clones.

Preventing the first unwanted commit is much cheaper than repairing its effects after publication.

## Uninstall

Run this from the checkout used for installation. It removes only the matching global setting and keeps the files and repository hooks:

```sh
git config --global --fixed-value --unset-all core.hooksPath "$(pwd -P)/hooks"
```

If you integrated the checker into another hook manager, remove those calls there instead.

## Test

```sh
python3 -m unittest discover -s tests -v
```

Tests use temporary repositories and an isolated global Git config. They do not change your Git settings. CI runs on macOS and Linux.

## License

MIT. See [LICENSE](LICENSE).
