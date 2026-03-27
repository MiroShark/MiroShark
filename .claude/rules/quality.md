# Quality Rule

## Forbidden Patterns
- `console.log` / `console.debug` / `debugger` (JS/TS)
- `breakpoint()` / `import pdb` / `print("DEBUG` (Python)
- Empty catch/except blocks that swallow errors
- Commented-out code blocks (>3 lines)
- `TODO` / `FIXME` / `HACK` left in committed code
- Stub functions that return fake data
- Hardcoded secrets, passwords, or API keys

## Required Patterns
- Error handling at system boundaries (user input, APIs, file I/O)
- No code duplication — extract shared logic
- Clean imports — no unused imports
- Functions under 50 lines; files under 500 lines (for new code)
- Meaningful variable names — no single-letter names except loop indices
