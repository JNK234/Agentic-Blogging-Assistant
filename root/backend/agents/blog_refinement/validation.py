# ABOUTME: Validation functions for ensuring generated content meets configuration requirements
# ABOUTME: Provides compliance checking with retry feedback generation

from typing import List, Dict, Any, Optional
from root.backend.models.generation_config import (
    TitleGenerationConfig,
    SocialMediaConfig,
    GenerationValidationResult
)
import json
import re
import logging

logger = logging.getLogger(__name__)


def validate_title_generation(
    generated_titles: List[Dict[str, Any]],
    config: TitleGenerationConfig
) -> GenerationValidationResult:
    """
    Validate generated titles against configuration requirements.

    Args:
        generated_titles: List of generated title dictionaries
        config: Configuration specifying requirements

    Returns:
        ValidationResult with violations and warnings
    """
    result = GenerationValidationResult(is_valid=True)

    # Check count requirement
    if len(generated_titles) != config.num_titles:
        result.add_violation(
            f"Expected {config.num_titles} title(s), but got {len(generated_titles)}"
        )

    # Validate each title
    for i, title_obj in enumerate(generated_titles, 1):
        # Check title structure
        if not isinstance(title_obj, dict):
            result.add_violation(f"Title {i} is not a valid dictionary")
            continue

        if 'title' not in title_obj:
            result.add_violation(f"Title {i} missing 'title' field")
            continue

        title_text = title_obj.get('title', '')

        # Check subtitle presence based on config
        if config.num_subtitles_per_title == 1:
            if 'subtitle' not in title_obj:
                result.add_violation(f"Title {i} missing 'subtitle' field")
        else:
            if 'subtitles' not in title_obj:
                result.add_violation(f"Title {i} missing 'subtitles' array")
            elif len(title_obj.get('subtitles', [])) != config.num_subtitles_per_title:
                result.add_violation(
                    f"Title {i} should have {config.num_subtitles_per_title} subtitles, "
                    f"but has {len(title_obj.get('subtitles', []))}"
                )

        # Check length constraints
        if config.max_title_length and len(title_text) > config.max_title_length:
            result.add_violation(
                f"Title {i} exceeds maximum length of {config.max_title_length} "
                f"characters ({len(title_text)} chars)"
            )

        # Check subtitle length
        if config.max_subtitle_length:
            if config.num_subtitles_per_title == 1:
                subtitle_text = title_obj.get('subtitle', '')
                if len(subtitle_text) > config.max_subtitle_length:
                    result.add_violation(
                        f"Title {i} subtitle exceeds maximum length of "
                        f"{config.max_subtitle_length} characters"
                    )
            else:
                for j, subtitle_obj in enumerate(title_obj.get('subtitles', []), 1):
                    subtitle_text = subtitle_obj.get('subtitle', '')
                    if len(subtitle_text) > config.max_subtitle_length:
                        result.add_violation(
                            f"Title {i}, subtitle {j} exceeds maximum length of "
                            f"{config.max_subtitle_length} characters"
                        )

        # Check required keywords
        if config.required_keywords:
            title_lower = title_text.lower()
            subtitle_texts = []
            if config.num_subtitles_per_title == 1:
                subtitle_texts = [title_obj.get('subtitle', '').lower()]
            else:
                subtitle_texts = [s.get('subtitle', '').lower()
                                for s in title_obj.get('subtitles', [])]

            combined_text = title_lower + ' ' + ' '.join(subtitle_texts)

            has_keyword = False
            for keyword in config.required_keywords:
                if keyword.lower() in combined_text:
                    has_keyword = True
                    break

            if not has_keyword:
                result.add_warning(
                    f"Title {i} doesn't contain any required keywords: "
                    f"{', '.join(config.required_keywords)}"
                )

    # Check mandatory guidelines compliance
    if config.mandatory_guidelines:
        # This is harder to validate automatically, so we add warnings
        result.add_warning(
            "Manual review needed for guideline compliance: " +
            "; ".join(config.mandatory_guidelines)
        )

    return result


def validate_social_media_generation(
    generated_content: str,
    platform: str,
    config: SocialMediaConfig
) -> GenerationValidationResult:
    """
    Validate generated social media content against configuration.

    Args:
        generated_content: The generated social media content
        platform: The platform ('linkedin', 'twitter', 'newsletter')
        config: Configuration specifying requirements

    Returns:
        ValidationResult with violations and warnings
    """
    result = GenerationValidationResult(is_valid=True)

    # Platform-specific validation
    if platform == 'linkedin':
        # Check for required sections
        if '<linkedin_post>' not in generated_content:
            result.add_violation("LinkedIn post section not found in output")

        # Extract LinkedIn content
        linkedin_match = re.search(
            r'<linkedin_post>(.*?)</linkedin_post>',
            generated_content,
            re.DOTALL
        )
        if linkedin_match:
            linkedin_text = linkedin_match.group(1).strip()

            # Check word count (approximate)
            word_count = len(linkedin_text.split())
            if word_count < 150:
                result.add_warning(
                    f"LinkedIn post seems short ({word_count} words), "
                    "target is 200-250 words"
                )
            elif word_count > 300:
                result.add_warning(
                    f"LinkedIn post seems long ({word_count} words), "
                    "target is 200-250 words"
                )

            # Check hashtag requirements
            if config.include_hashtags:
                hashtag_count = len(re.findall(r'#\w+', linkedin_text))
                if config.max_hashtags and hashtag_count > config.max_hashtags:
                    result.add_violation(
                        f"LinkedIn post has {hashtag_count} hashtags, "
                        f"maximum is {config.max_hashtags}"
                    )
                if config.required_hashtags:
                    for required_tag in config.required_hashtags:
                        tag = required_tag if required_tag.startswith('#') else f"#{required_tag}"
                        if tag.lower() not in linkedin_text.lower():
                            result.add_warning(
                                f"Required hashtag '{tag}' not found in LinkedIn post"
                            )
            elif re.search(r'#\w+', linkedin_text):
                result.add_violation("LinkedIn post contains hashtags but they are disabled")

    elif platform == 'twitter':
        # Check for Twitter sections
        if '<x_post>' not in generated_content and '<x_thread>' not in generated_content:
            result.add_violation("Twitter content sections not found in output")

        # Validate single tweet
        if '<x_post>' in generated_content:
            tweet_match = re.search(r'<x_post>(.*?)</x_post>', generated_content, re.DOTALL)
            if tweet_match:
                tweet_text = tweet_match.group(1).strip()
                if len(tweet_text) > 280:
                    result.add_violation(
                        f"Single tweet exceeds 280 characters ({len(tweet_text)} chars)"
                    )

        # Validate thread
        if '<x_thread>' in generated_content:
            thread_match = re.search(r'<x_thread>(.*?)</x_thread>', generated_content, re.DOTALL)
            if thread_match:
                thread_text = thread_match.group(1).strip()
                # Count numbered tweets
                tweet_matches = re.findall(r'^\d+\.\s+(.+)$', thread_text, re.MULTILINE)
                if len(tweet_matches) != config.twitter_thread_length:
                    result.add_violation(
                        f"Twitter thread should have {config.twitter_thread_length} tweets, "
                        f"but has {len(tweet_matches)}"
                    )

                # Check each tweet length
                for i, tweet in enumerate(tweet_matches, 1):
                    if len(tweet) > 280:
                        result.add_violation(
                            f"Thread tweet {i} exceeds 280 characters ({len(tweet)} chars)"
                        )

    elif platform == 'newsletter':
        # Check for newsletter section
        if '<newsletter_content>' not in generated_content:
            result.add_violation("Newsletter content section not found in output")

        newsletter_match = re.search(
            r'<newsletter_content>(.*?)</newsletter_content>',
            generated_content,
            re.DOTALL
        )
        if newsletter_match:
            newsletter_text = newsletter_match.group(1).strip()

            # Check for title
            if not re.search(r'^#\s+.+', newsletter_text, re.MULTILINE):
                result.add_warning("Newsletter content missing title (H1 header)")

            # Check word count
            # Remove markdown formatting for word count
            clean_text = re.sub(r'[#*\[\]()]', '', newsletter_text)
            word_count = len(clean_text.split())
            if word_count < 100:
                result.add_warning(
                    f"Newsletter content seems short ({word_count} words), "
                    "target is 150-200 words"
                )
            elif word_count > 250:
                result.add_warning(
                    f"Newsletter content seems long ({word_count} words), "
                    "target is 150-200 words"
                )

    # Check mandatory guidelines (generic warning)
    if config.mandatory_guidelines:
        result.add_warning(
            "Manual review needed for general guideline compliance"
        )

    if config.platform_specific_guidelines and platform in config.platform_specific_guidelines:
        result.add_warning(
            f"Manual review needed for {platform}-specific guideline compliance"
        )

    return result


def create_correction_prompt(
    original_content: Any,
    validation_result: GenerationValidationResult,
    content_type: str = "titles"
) -> str:
    """
    Create a correction prompt for retry based on validation failures.

    Args:
        original_content: The originally generated content
        validation_result: The validation result with violations
        content_type: Type of content ('titles' or 'social')

    Returns:
        Prompt for correction retry
    """
    if validation_result.is_valid:
        return ""

    prompt = f"The previously generated {content_type} have the following issues:\n\n"

    # List violations
    prompt += "**VIOLATIONS (MUST FIX):**\n"
    for i, violation in enumerate(validation_result.violations, 1):
        prompt += f"{i}. {violation}\n"

    if validation_result.warnings:
        prompt += "\n**WARNINGS (SHOULD ADDRESS):**\n"
        for i, warning in enumerate(validation_result.warnings, 1):
            prompt += f"{i}. {warning}\n"

    # Add the original content
    prompt += f"\n**ORIGINAL CONTENT:**\n"
    if content_type == "titles":
        prompt += f"```json\n{json.dumps(original_content, indent=2)}\n```\n"
    else:
        prompt += f"{original_content}\n"

    prompt += "\n**INSTRUCTIONS:**\n"
    prompt += "Generate corrected content that addresses ALL violations listed above.\n"
    prompt += "Maintain the same overall quality and style, but ensure compliance with all requirements.\n"
    prompt += "Output in the same format as originally requested.\n"

    return prompt