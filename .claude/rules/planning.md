# Planning Rule

Before implementing any change:
1. Check `.claude/goals.md` — which goal does this advance?
2. State the goal in one sentence
3. List files you'll modify
4. Describe what changes in each file
5. Identify risks or side effects

If changing >3 files, use `/plan` to create a written plan first.
If work reveals a new sub-goal, propose adding it with `/goals sub`.

After implementing, verify your changes work:
- Run tests if available
- Check syntax/build
- Confirm the goal is met

After EVERY completed action, end your response with **Next:** — 2-4 numbered quick-pick options so the user can respond with just a number. Format:

**Next:**
1. {most logical follow-up}
2. {alternative action}
3. {verification or review step}

Examples: "Run tests", "Show the diff", "Move to next file", "Deploy", "/verify", "/review"
