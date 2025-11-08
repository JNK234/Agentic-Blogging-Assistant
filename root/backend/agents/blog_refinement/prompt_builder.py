# ABOUTME: Dynamic prompt builder for blog refinement with configurable generation
# ABOUTME: Constructs prompts based on TitleGenerationConfig and SocialMediaConfig

from typing import Optional
from root.backend.models.generation_config import TitleGenerationConfig, SocialMediaConfig
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

Create compelling titles that reflect how an expert practitioner would share insights with peers. Your titles should communicate clear value and specific outcomes while maintaining the authentic voice of someone sharing hard-earned knowledge.

**EXPERT PRACTITIONER TITLE PHILOSOPHY:**
You're not creating marketing copy—you're offering genuine insights to fellow practitioners who value substance over style. Your titles should reflect the same conversational authority and strategic clarity found in the best technical writing.

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
    prompt += """**TITLE CREATION PRINCIPLES:**

1. **Direct Value Communication**:
   - Promise specific learning outcomes based on actual content
   - Use concrete language over abstract descriptions
   - Lead with the most valuable insight or practical outcome
   - Reflect the expert practitioner's authentic voice

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
   - Pose questions when content explores open problems
   - Highlight surprising insights or counterintuitive findings
   - Use comparison/contrast when content compares approaches
   - Create intrigue about methodology or implementation details

**ADAPTIVE TITLE APPROACHES:**

Based on content analysis, choose the most appropriate approach:
- **Evolution Narrative**: "From [Past] to [Present]: [Insight]"
- **Practical Implementation**: "[Specific Approach] for [Specific Context]"
- **Insight Sharing**: "Why [Observation] Matters for [Application]"
- **Problem-Solution**: "[Challenge] and [Effective Solution]"
- **Comparative Analysis**: "[Method A] vs [Method B]: [Key Difference]"

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