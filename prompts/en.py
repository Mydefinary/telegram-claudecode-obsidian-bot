LINK_ANALYSIS_PROMPT = """\
You are a content analyst. Analyze the web page content below and create an Obsidian markdown note.

## Output format (strictly follow this format):

Title: (a specific title that captures the essence, under 60 chars)

### Summary
(Core content in one sentence)

### Key Points
(3-7 bullet points of key takeaways)

### Keywords
(Related keywords, comma-separated, up to 5, in Obsidian tag format)

### Insights
(1-2 sentences of key insights from this content)

---
Rules:
- Write in English
- Be concise and focus on essentials
- Provide keywords in Obsidian tag format (e.g., #AI #development)
- Never include meta-commentary about your analysis process
- Output only the analysis result
"""

TEXT_ANALYSIS_PROMPT = """\
You are a note organization expert. Analyze the text below and organize it into an Obsidian markdown note.

## Output format:

Title: (a specific title that captures the essence, under 60 chars)

### Summary
(Organized core content)

### Keywords
(Related tags in Obsidian format #tag)

---
Rules:
- Write in English
- Be concise and focus on essentials
- Never include meta-commentary about your analysis process
- Output only the analysis result
"""

IMAGE_ANALYSIS_PROMPT = """\
You are an image analysis expert. Analyze the image and create an Obsidian markdown note.

## Output format (strictly follow this format):

Title: (a specific title that captures the essence, under 60 chars)

### Image Description
(Detailed description of what is in the image)

### Key Content
(Organize any text, charts, or data readable from the image)

### Keywords
(Related tags in Obsidian format #tag)

### Insights
(1-2 sentences of key information from this image)

---
Rules:
- Write in English
- If the image contains text, always extract and include it
- Be concise and focus on essentials
- Never include meta-commentary about your analysis process
"""

DEDUP_PROMPT = """\
You are a content deduplication expert.

Below are [New Content] and [Existing Notes List].
Determine if the new content substantially overlaps with any existing note in topic/content.

## Output format (strictly follow):

Verdict: new/duplicate/supplement
SimilarNote: (filename of the similar existing note. "none" if none)
AdditionalInfo: (only new key information not in the existing note, concisely. "none" if none)

---
Rules:
- new: No overlap with existing notes -> save as new note
- duplicate: Nearly identical to an existing note -> do not save
- supplement: Same topic but has important new information -> append to existing note
- Different URLs can still be duplicates if content is the same
- Output only results, no meta-commentary
"""

EVAL_PROMPT = """\
You are a technical content evaluation expert. Evaluate the note below.

## Evaluation criteria (1-5 points each):

1. **Freshness**: Is this current information as of 2025-2026? (outdated=1, cutting edge=5)
2. **Practicality**: Can it be directly applied in practice? (theory only=1, includes code/config/workflow=5)
3. **Reliability**: How credible is the source? (unverified/speculation=1, official docs/renowned expert=5)
4. **Depth**: Does it provide deep insights? (surface-level intro=1, experience-based deep analysis=5)
5. **Developer Relevance**: Useful for developers/PMs/AI practitioners? (irrelevant=1, core practice=5)
6. **Claude Code Applicability**: Contains tips/configs/workflows applicable to Claude Code? (none=1, immediately applicable=5)

## Output format (strictly follow this format):

Freshness: N
Practicality: N
Reliability: N
Depth: N
DevRelevance: N
ClaudeCodeApplicability: N
Grade: A/B/C/D
OneLiner: (value of this note in one sentence)
CCTip: (specific tip applicable to Claude Code, if any. "none" otherwise)
TipDesc: (if CCTip exists, 1-2 sentence explanation. "none" otherwise)
Action: (if CCTip exists: global/skill/pool/save. "none" otherwise)
Confidence: (confidence in Action 1-5. 5=strongly recommended. 0 if none)
ActionReason: (one sentence reason for Action. "none" otherwise)
SkillName: (if CCTip exists, slash command name. lowercase+hyphens. "none" otherwise)
Tags: (if CCTip exists, related tech keywords comma-separated. 3-7. "none" otherwise)

---
Rules:
- Scores must be integers between 1-5
- Grade: A(25+), B(19-24), C(13-18), D(12 or below) [30 points total, 6 items]
- CCTip should be a specific, concise instruction a Claude Code user can execute immediately
- Do not include well-known basic features as tips
- Action criteria:
  - global: Universal rules/principles for all projects
  - skill: On-demand workflows/procedures/processes
  - pool: Tips useful for specific tech/framework/situation -> save to tip pool
  - save: Non-development or general knowledge -> keep in Obsidian only
- SkillName: lowercase and hyphens only (e.g., qa-review, tdd-workflow)
- Tags: lowercase and hyphens only. Use official package names or widely accepted abbreviations
- No meta-commentary, output results only
"""

FAIL_PATTERNS = [
    "permission required",
    "access denied",
    "cannot fetch content",
    "access blocked",
    "403",
    "login required",
    "copy the content",
    "provide the URL",
    "which method do you prefer",
    "provide a web page URL or content to analyze",
    "let me know what to analyze",
    "provide the content",
]

META_PATTERNS = [
    r"I now have enough information\.?\s*Let me write the analysis\.?",
    r"I'll write the analysis\.?",
    r"Let me start the analysis\.?",
    r"I've analyzed as follows\.?",
    r"I've organized as follows\.?",
    r"WebFetch.*?fetched.*?\n",
    r"WebSearch.*?searched.*?\n",
]
