# ABOUTME: Dynamic prompt builder for blog refinement with configurable generation
# ABOUTME: Constructs prompts based on TitleGenerationConfig and SocialMediaConfig

from typing import Optional
from backend.models.generation_config import TitleGenerationConfig, SocialMediaConfig
import logging

logger = logging.getLogger(__name__)

def build_title_generation_prompt(blog_draft: str, config: Optional[TitleGenerationConfig] = None) -> str:
    """
    Build dynamic title generation prompt based on configuration.
    Uses XML tags for clear guideline demarcation as recommended by expert analysis.

    Args:
        blog_draft: The blog content to generate titles for
        config: Optional configuration for title generation

    Returns:
        Complete prompt string for title generation
    """
    # Use default config if none provided (backward compatibility)
    if config is None:
        config = TitleGenerationConfig()

    # Base prompt structure
    prompt = f"""You are an expert copywriter and SEO specialist tasked with generating compelling titles and subtitles for a blog post.
The full draft of the blog post is provided below.

Create compelling titles using the Question-Based Comparison Pattern as your PRIMARY approach. This pattern excels at creating immediate curiosity while remaining grounded in technical content that compares approaches, reveals counter-intuitive findings, or challenges conventional wisdom.

**QUESTION-BASED TITLE PHILOSOPHY:**
Your titles should reflect how expert practitioners share insights with peers—through direct questions that reveal technical insights, not marketing copy. Focus on comparison questions that promise specific learning outcomes based on the actual content.

**BLOG POST ANALYSIS:**
```markdown
{blog_draft}
```

<generation_config>
    <counts>
        <num_titles>{config.num_titles}</num_titles>
        <subtitles_per_title>{config.num_subtitles_per_title}</subtitles_per_title>
    </counts>
"""

    # Add mandatory guidelines if provided
    if config.mandatory_guidelines:
        prompt += "    <mandatory_guidelines>\n"
        for guideline in config.mandatory_guidelines:
            prompt += f"        <guideline>{guideline}</guideline>\n"
        prompt += "    </mandatory_guidelines>\n"

    # Add constraints if specified
    if config.max_title_length or config.max_subtitle_length or config.required_keywords:
        prompt += "    <constraints>\n"
        if config.max_title_length:
            prompt += f"        <max_title_length>{config.max_title_length}</max_title_length>\n"
        if config.max_subtitle_length:
            prompt += f"        <max_subtitle_length>{config.max_subtitle_length}</max_subtitle_length>\n"
        if config.required_keywords:
            prompt += f"        <required_keywords>{', '.join(config.required_keywords)}</required_keywords>\n"
        prompt += "    </constraints>\n"

    if config.style_tone:
        prompt += f"    <style_tone>{config.style_tone}</style_tone>\n"

    prompt += "</generation_config>\n\n"

    # Add the rest of the standard prompt
    prompt += """**QUESTION-BASED COMPARISON PATTERN - PRIMARY APPROACH:**

This pattern works exceptionally well for technical content comparing two approaches, revealing a counter-intuitive finding, or challenging conventional wisdom. It creates immediate curiosity while remaining grounded in the actual topic.

**Pattern:** "{Question Word} {Topic A} {Verb} {Topic B}?"
- Question Word: What, When, Can, Why, Does
- Topic A: The subject/technique being discussed
- Verb: Make, Work, Use, Need, Help, Hurt, Replace, Cost
- Topic B: The comparison point or outcome

**Examples for different content types:**
- Performance comparisons: "What Makes X Faster Than Y?"
- Feasibility questions: "Can X Work Without Y?"
- Timing/conditions: "When Does X Hurt More Than Y?"
- Mechanism questions: "Why Does X Need Y?"
- Cost-benefit: "Does X Always Cost More Than Y?"

**Subtitle Formula:** {Technical difference} + {specific metric} + {what's preserved or the trade-off}
- Keep it factual and specific
- Include numbers when available (8% savings, 90% reduction, 3x faster)
- Mention what stays the same or what the benefit is

**REFERENCE EXAMPLES:**

For RMSNorm content:
- Title: "What Makes RMSNorm Faster Than LayerNorm?"
- Subtitle: "Eliminating mean subtraction cuts computation by 8% while preserving the re-scaling benefits"

For MoE routing content:
- Title: "Can MoE Use Single-Expert Routing?"
- Subtitle: "k=1 selection blocks gradient flow, requiring k≥2 to train all experts effectively"

For KV-Cache content:
- Title: "When Does KV-Cache Hurt More Than Help?"
- Subtitle: "Caching costs 3.2GB for 1K tokens—recomputation reduces memory by 60% with 15% latency trade-off"

**TITLE CREATION PRINCIPLES:**

1. **Direct Value Communication**:
   - Promise specific learning outcomes based on actual content
   - Use concrete language over abstract descriptions
   - Lead with the most valuable insight or practical outcome
   - Focus on comparison questions that reveal technical insights

2. **Contextual Specificity**:
   - Include relevant technical context (when appropriate)
   - Specify the scope and application domain
   - Use precise terminology that signals expertise
   - Avoid generic technology labels when specifics matter

3. **Natural Language Patterns**:
   - Use conversational phrasing that sounds natural, not corporate
   - Apply the narrative elements present in the content
   - Reflect any historical context or evolution presented
   - Match the sophistication level of the content

4. **Engagement Through Curiosity**:
   - Pose questions when content compares two approaches
   - Highlight surprising insights or counterintuitive findings
   - Use comparison/contrast when evaluating alternatives
   - Create intrigue about methodology or implementation details

**PRIORITY APPROACHES:**

1. **Question-Based Comparison** (HIGHEST PRIORITY): Use when content compares two approaches, techniques, or reveals counter-intuitive findings
   - Pattern: "{Question} {Topic A} {Verb} {Topic B}?"
   - Creates immediate engagement while staying grounded in content

2. **Insight Revelation**: Use when content uncovers a non-obvious mechanism or failure mode
   - Pattern: "{What/Why} {Topic} {Unexpected Outcome}?"

3. **Problem-Solution**: Use as fallback when content focuses on solving a specific problem
   - Pattern: "{How} {Problem} {Solution}?"

**CRITICAL OUTPUT INSTRUCTIONS:**

You MUST follow ALL guidelines specified in the <generation_config> section above.
"""

    # Build the output format based on configuration
    prompt += f"\nGenerate exactly {config.num_titles} title option(s) as a JSON array.\n"

    if config.num_subtitles_per_title == 1:
        prompt += """Each option should follow this exact structure:

```json
[
  {
    "title": "Your compelling title here",
    "subtitle": "Your informative subtitle that adds context",
    "reasoning": "Brief explanation of why this title works"
  }"""
    else:
        prompt += f"""Each option should have {config.num_subtitles_per_title} subtitle variants:

```json
[
  {{
    "title": "Your compelling title here",
    "subtitles": ["""
        for i in range(config.num_subtitles_per_title):
            if i > 0:
                prompt += ","
            prompt += f"""
      {{
        "subtitle": "Subtitle variant {i+1}",
        "focus": "What aspect this subtitle emphasizes"
      }}"""
        prompt += """
    ],
    "reasoning": "Brief explanation of why this title works"
  }"""

    # Complete the JSON example
    if config.num_titles > 1:
        prompt += ",\n  ... (additional title options)\n"
    prompt += """
]
```

**FINAL INSTRUCTIONS:**
- Output ONLY the JSON array, no other text
- Generate exactly """ + str(config.num_titles) + """ title option(s)
- Each object must have the exact structure shown above
- Ensure proper JSON formatting with double quotes
- Do not include markdown code blocks or any other formatting
- ALL guidelines in <mandatory_guidelines> MUST be followed
- PRIORITIZE the Question-Based Comparison Pattern for your titles
- Use the reference examples as inspiration for your specific topic
"""

    return prompt


def build_social_media_prompt(
    blog_content: str,
    platform: str,
    config: Optional[SocialMediaConfig] = None,
    persona_instructions: str = ""
) -> str:
    """
    Build dynamic social media generation prompt based on configuration.

    Args:
        blog_content: The blog content to create social posts from
        platform: The social media platform ('linkedin', 'twitter', 'newsletter')
        config: Optional configuration for social media generation
        persona_instructions: Optional persona-specific instructions

    Returns:
        Complete prompt string for social media generation
    """
    if config is None:
        config = SocialMediaConfig()

    # Special handling for LinkedIn Interview Trap template
    if platform == 'linkedin' and getattr(config, 'use_interview_trap', False):
        # Use the interview trap template for LinkedIn
        from backend.prompts.social_media.interview_trap_template import INTERVIEW_TRAP_LINKEDIN_TEMPLATE
        from backend.models.generation_config import SocialMediaConfig
        from pathlib import Path

        # Extract blog title from content (first line or use a placeholder)
        blog_title = "Blog Post"
        lines = blog_content.split('\n')
        for line in lines:
            if line.strip() and not line.startswith('#'):
                blog_title = line.strip()[:50]
                break

        return INTERVIEW_TRAP_LINKEDIN_TEMPLATE.format(
            persona_instructions=persona_instructions,
            blog_content=blog_content,
            blog_title=blog_title
        )

    # Start with persona instructions if provided
    prompt = persona_instructions + "\n\n" if persona_instructions else ""

    # Add configuration block
    prompt += f"""<social_media_config>
    <platform>{platform}</platform>
"""

    # Add platform-specific counts
    if platform == 'linkedin':
        prompt += f"    <variants>{config.linkedin_variants}</variants>\n"
    elif platform == 'twitter':
        prompt += f"    <single_variants>{config.twitter_single_variants}</single_variants>\n"
        prompt += f"    <thread_length>{config.twitter_thread_length}</thread_length>\n"
    elif platform == 'newsletter':
        prompt += f"    <variants>{config.newsletter_variants}</variants>\n"

    # Add guidelines
    if config.mandatory_guidelines:
        prompt += "    <mandatory_guidelines>\n"
        for guideline in config.mandatory_guidelines:
            prompt += f"        <guideline>{guideline}</guideline>\n"
        prompt += "    </mandatory_guidelines>\n"

    if config.platform_specific_guidelines and platform in config.platform_specific_guidelines:
        prompt += f"    <{platform}_guidelines>\n"
        for guideline in config.platform_specific_guidelines[platform]:
            prompt += f"        <guideline>{guideline}</guideline>\n"
        prompt += f"    </{platform}_guidelines>\n"

    # Add hashtag configuration
    prompt += "    <hashtag_config>\n"
    prompt += f"        <include_hashtags>{str(config.include_hashtags).lower()}</include_hashtags>\n"
    if config.include_hashtags:
        if config.max_hashtags:
            prompt += f"        <max_hashtags>{config.max_hashtags}</max_hashtags>\n"
        if config.required_hashtags:
            prompt += f"        <required_hashtags>{', '.join(config.required_hashtags)}</required_hashtags>\n"
    prompt += "    </hashtag_config>\n"

    if config.tone_style:
        prompt += f"    <tone_style>{config.tone_style}</tone_style>\n"

    prompt += "</social_media_config>\n\n"

    # Add the blog content
    prompt += f"""Content to share:
<blogpost_markdown>
{blog_content}
</blogpost_markdown>

**CRITICAL INSTRUCTIONS:**
You MUST follow ALL guidelines specified in the <social_media_config> section above.
Generate content according to the specified counts and constraints.
"""

    # Add platform-specific format requirements
    if platform == 'linkedin':
        prompt += f"""
Generate {config.linkedin_variants} LinkedIn post variant(s):
- Each should be 200-250 words of clear, factual explanation
- Build the concept step-by-step
- Use bullet points for key components
- Include link placeholder: "Full post: [link-placeholder]"
"""
        if config.include_hashtags:
            max_tags = config.max_hashtags or 3
            prompt += f"- Use {max_tags} relevant technical hashtags\n"

    elif platform == 'twitter':
        prompt += f"""
Generate {config.twitter_single_variants} single tweet variant(s) (max 280 chars each)
AND a Twitter thread with {config.twitter_thread_length} tweets:
- Each tweet under 280 characters
- Build understanding progressively
- Thread should tell a complete story
"""

    elif platform == 'newsletter':
        prompt += f"""
Generate {config.newsletter_variants} newsletter content variant(s):
- Title: "Understanding [concept]" or similar
- 150-200 words of clear explanation
- Structure: Opening → Core concept → Key insight → Practical application
- Include link: "Full analysis: [{{blog_title}}](link-placeholder)"
"""

    return prompt