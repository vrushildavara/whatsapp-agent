SUMMARY_PROMPT = """
You are maintaining a running conversation summary.

GOAL:
- Update the summary using the new conversation
- Max 150 words (STRICT)
- Keep important facts, user intent, preferences, decisions
- Remove outdated or redundant information

RULES:
- Do NOT repeat greetings
- Do NOT add assumptions
- Use third-person
- Preserve technical details
- Be concise

CURRENT SUMMARY:
{existing_summary}

LATEST CONVERSATION (last 25 messages):
{conversation}

OUTPUT:
Updated summary (≤100 words)
"""
