STAGE_LABELING_PROMPT = """You are a stage classifier. Analyze the conversation and determine the current stage based on the stage flow.

**Stage Flow:**
{stage_flow}

**Conversation:**
{conversation}

**Instructions:**
- Read the conversation carefully
- Identify which stage the conversation is currently in based on the stage flow
- Return ONLY the stage name (e.g., "greeting", "qualification", "closing")
- Do not include any explanation or additional text
- If uncertain, return the most likely stage

**Output (stage name only):**"""
