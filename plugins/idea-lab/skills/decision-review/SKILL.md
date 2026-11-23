---
name: decision-review
description: Review past logged decisions against what actually happened, grade the predictions and improve the protocol. Use when the user wants to check how earlier evaluations or debates turned out, calibrate confidence, backtest the system, or asks "were we right".
---

# Decision review

Reads `idea-lab/decisions.md`. This is the only check on whether the debates are worth trusting, so be honest about small samples. Do not use agents for this; do it yourself.

1. Run `bash ${CLAUDE_PLUGIN_ROOT}/scripts/lab-session.sh start` and `end` at the finish.
2. List entries whose outcome is pending. Ask the user, one entry at a time, what actually happened (and any evidence), then update the entry's outcome field.
3. For each decided entry compare: the verdict and confidence, the kill criteria (were they hit?), the strongest case against (did that risk materialise?), and which agent's memo was closest to the outcome.
4. Summarise: how many decisions, hit rate by confidence level (say plainly when the sample is too small to conclude), recurring blind spots, and agents whose advice proved weakest or strongest.
5. Propose at most three concrete changes to prompts, agents or protocol, and write the review to `idea-lab/reviews/<date>.md`.
