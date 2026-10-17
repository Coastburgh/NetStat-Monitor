# General Rules

## Communication

- Use formal language. Be concise and direct; no embellishments, filler, or casual phrasing.
- Reply in the language used by the user.
- When discussing or comparing options, answer point by point, each point with a bold label.
- State uncertainty explicitly. Do not claim that code was run, tested, or verified unless it was.
- Do not ask for confirmation on trivial choices; apply the conventional option and mention it in one line.

## Scope and edits

- Make the minimal change that satisfies the request. Do not modify files, functions, or lines outside the request.
- Do not refactor, reformat, rename, reindent, or reorder unrelated code.
- Preserve existing blank lines, trailing newlines, and indentation style unless the request concerns them.
- Do not add dependencies, files, or new entry points unless requested.
- Do not modify README, LICENSE, or other documentation unless requested.
- Reuse existing functions and helpers. Do not reimplement logic that already exists in the project.
- If a requirement is ambiguous or contradicts existing code or documented decisions, state the conflict and ask one question before proceeding.

## Output format

- After editing, list every file changed and confirm that no lines outside the requested change were added or removed.
- End with a brief summary (at most one short paragraph) of what changed and any limitation.

## Verification

- Before concluding, run the relevant tests or the module's manual entry point whenever the environment allows it.
- Check for duplicated output, unreachable code, and unintended whitespace changes in the final diff.
- A passing test is not sufficient evidence of correctness. Consider inputs the test does not cover.
- When code depends on the operating system, tool output, or locale, identify every supported platform (Windows, Linux, macOS) and reason about each output format before finishing. Add a test case for each format affected.
- Add a unit test for each new behavior or fixed defect, including edge cases (empty input, `None`, missing values).
- Report anything that could not be verified.

## Code conventions

- Follow the language and style of the surrounding code, including the language of comments and docstrings.
- Write docstrings that explain the purpose and the reason for non-obvious decisions, not a restatement of the code.
- Handle edge cases without raising unhandled exceptions: empty data, missing values, unreachable hosts, missing files.
- Keep functions small and single-purpose. Prefer simple solutions; defer complexity until it is needed.
- Avoid unreachable branches and redundant guards.
- Prefer robust operations over positional assumptions (for example, `min()`/`max()` instead of first/last row when order is not guaranteed).
- Never hard-code credentials, absolute personal paths, or machine-specific values.

## Git

- Before editing, check the current branch with `git branch --show-current`.
  - If the request continues the topic of the current branch, stay on it.
  - Otherwise, create a new branch from the main branch with one of these prefixes:
    - `fix/<short-description>` for bug fixes
    - `feat/<short-description>` for new features
    - `refactor/<short-description>` for refactoring
    - `test/<short-description>` for new tests
    - `docs/<short-description>` for documentation changes
    - `perf/<short-description>` for performance improvements
    - `chore/<short-description>` for other changes
- Use lowercase, hyphen-separated descriptions, such as `fix/parser-empty-input`.
- Before committing, run `git diff` and `git status`, and confirm that only the requested files and lines changed.
- Stage only the files for the requested change with `git add <file>`. Do not use `git add .` unless explicitly authorized by the user.
- Verify the staged content with `git diff --staged` before committing.
- Never make one big commit with multiple unrelated changes. Each commit should be focused on a single change or fix.
- Commit with a message in the imperative mood for English, use the present tense in the third person singular for Portuguese, that states the change and its purpose, for example: "Fix bug in data parser for empty input" / "Corrige bug no parser de dados para entrada vazia".
- Do not push, rebase, reset, amend, or otherwise rewrite history unless the user asks.
- Keep unrelated changes out of the same commit. If an unrelated change appears, leave it unstaged and mention it in the response.

## Testing instructions

- Add focused regression tests for every bug fix and behavior change.