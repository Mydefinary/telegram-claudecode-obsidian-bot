from config import LANGUAGE


def get_prompts() -> dict:
    """Load prompts for the configured language."""
    if LANGUAGE == "en":
        from prompts import en as mod
    else:
        from prompts import ko as mod

    return {
        "link_analysis": mod.LINK_ANALYSIS_PROMPT,
        "text_analysis": mod.TEXT_ANALYSIS_PROMPT,
        "image_analysis": mod.IMAGE_ANALYSIS_PROMPT,
        "github_analysis": mod.GITHUB_ANALYSIS_PROMPT,
        "dedup": mod.DEDUP_PROMPT,
        "eval": mod.EVAL_PROMPT,
        "content_summary": mod.CONTENT_SUMMARY_PROMPT,
        "fail_patterns": mod.FAIL_PATTERNS,
        "meta_patterns": mod.META_PATTERNS,
    }
