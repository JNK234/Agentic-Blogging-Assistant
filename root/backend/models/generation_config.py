# ABOUTME: Configuration models for controlling title/subtitle and social media generation
# ABOUTME: Provides flexible, optional settings with mandatory enforcement when specified

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class TitleGenerationConfig(BaseModel):
    """Configuration for title and subtitle generation with optional guidelines"""

    # Core count controls
    num_titles: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of title options to generate"
    )

    num_subtitles_per_title: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Number of subtitle variants per title"
    )

    # Optional but mandatory-when-provided guidelines
    mandatory_guidelines: Optional[List[str]] = Field(
        default=None,
        description="Guidelines that MUST be followed when provided"
    )

    # SEO and style constraints
    max_title_length: Optional[int] = Field(
        default=None,
        ge=10,
        le=100,
        description="Maximum character length for titles"
    )

    max_subtitle_length: Optional[int] = Field(
        default=None,
        ge=20,
        le=200,
        description="Maximum character length for subtitles"
    )

    required_keywords: Optional[List[str]] = Field(
        default=None,
        description="Keywords that must appear in titles"
    )

    style_tone: Optional[str] = Field(
        default=None,
        description="Tone/style directive (e.g., 'professional', 'conversational', 'technical')"
    )

    @validator('mandatory_guidelines')
    def validate_guidelines(cls, v):
        """Ensure guidelines are non-empty strings"""
        if v is not None:
            filtered = [g.strip() for g in v if g and g.strip()]
            return filtered if filtered else None
        return v

    def to_prompt_instructions(self) -> str:
        """Convert configuration to prompt instructions"""
        instructions = []

        instructions.append(f"Generate exactly {self.num_titles} title options.")

        if self.num_subtitles_per_title > 1:
            instructions.append(f"Each title must have {self.num_subtitles_per_title} subtitle variants.")

        if self.mandatory_guidelines:
            instructions.append("\nMANDATORY GUIDELINES (MUST BE FOLLOWED):")
            for guideline in self.mandatory_guidelines:
                instructions.append(f"  - {guideline}")

        if self.max_title_length:
            instructions.append(f"\nTitle length constraint: Maximum {self.max_title_length} characters")

        if self.max_subtitle_length:
            instructions.append(f"Subtitle length constraint: Maximum {self.max_subtitle_length} characters")

        if self.required_keywords:
            instructions.append(f"\nRequired keywords (must include at least one): {', '.join(self.required_keywords)}")

        if self.style_tone:
            instructions.append(f"\nTone/Style: {self.style_tone}")

        return "\n".join(instructions)


class SocialMediaConfig(BaseModel):
    """Configuration for social media post generation with platform-specific settings"""

    # Platform-specific post counts
    linkedin_variants: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Number of LinkedIn post variants"
    )

    twitter_single_variants: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Number of single Twitter post variants"
    )

    twitter_thread_length: int = Field(
        default=5,
        ge=3,
        le=10,
        description="Number of tweets in Twitter thread"
    )

    newsletter_variants: int = Field(
        default=1,
        ge=1,
        le=2,
        description="Number of newsletter variants"
    )

    # LinkedIn Interview Trap template option
    use_interview_trap: bool = Field(
        default=False,
        description="Use interview trap narrative pattern for LinkedIn posts (engaging Q&A format)"
    )

    # Optional guidelines
    mandatory_guidelines: Optional[List[str]] = Field(
        default=None,
        description="Guidelines that MUST be followed for all platforms"
    )

    platform_specific_guidelines: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Platform-specific guidelines (e.g., {'linkedin': [...], 'twitter': [...]})"
    )

    # Content constraints
    include_hashtags: Optional[bool] = Field(
        default=True,
        description="Whether to include hashtags"
    )

    max_hashtags: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="Maximum number of hashtags per post"
    )

    required_hashtags: Optional[List[str]] = Field(
        default=None,
        description="Hashtags that must be included"
    )

    tone_style: Optional[str] = Field(
        default=None,
        description="Overall tone for social media posts"
    )

    @validator('platform_specific_guidelines')
    def validate_platform_guidelines(cls, v):
        """Ensure platform guidelines are properly formatted"""
        if v is not None:
            valid_platforms = {'linkedin', 'twitter', 'newsletter', 'x'}
            filtered = {}
            for platform, guidelines in v.items():
                if platform.lower() in valid_platforms and guidelines:
                    filtered[platform.lower()] = [g.strip() for g in guidelines if g and g.strip()]
            return filtered if filtered else None
        return v

    def get_platform_instructions(self, platform: str) -> str:
        """Get instructions for a specific platform"""
        instructions = []

        # Add platform-specific counts
        if platform == 'linkedin':
            if self.linkedin_variants > 1:
                instructions.append(f"Generate {self.linkedin_variants} LinkedIn post variants.")
        elif platform == 'twitter':
            if self.twitter_single_variants > 1:
                instructions.append(f"Generate {self.twitter_single_variants} single tweet variants.")
            instructions.append(f"Thread should contain {self.twitter_thread_length} tweets.")
        elif platform == 'newsletter':
            if self.newsletter_variants > 1:
                instructions.append(f"Generate {self.newsletter_variants} newsletter variants.")

        # Add general mandatory guidelines
        if self.mandatory_guidelines:
            instructions.append("\nMANDATORY GUIDELINES (ALL POSTS):")
            for guideline in self.mandatory_guidelines:
                instructions.append(f"  - {guideline}")

        # Add platform-specific guidelines
        if self.platform_specific_guidelines and platform in self.platform_specific_guidelines:
            instructions.append(f"\n{platform.upper()} SPECIFIC GUIDELINES:")
            for guideline in self.platform_specific_guidelines[platform]:
                instructions.append(f"  - {guideline}")

        # Add hashtag requirements
        if self.include_hashtags:
            if self.max_hashtags:
                instructions.append(f"\nUse maximum {self.max_hashtags} hashtags.")
            if self.required_hashtags:
                instructions.append(f"Must include: {' '.join(['#' + tag.lstrip('#') for tag in self.required_hashtags])}")
        else:
            instructions.append("\nDo not include hashtags.")

        if self.tone_style:
            instructions.append(f"\nTone: {self.tone_style}")

        return "\n".join(instructions) if instructions else ""


class GenerationValidationResult(BaseModel):
    """Result of validating generated content against configuration"""

    is_valid: bool = Field(description="Whether content meets all requirements")
    violations: List[str] = Field(default_factory=list, description="List of guideline violations")
    warnings: List[str] = Field(default_factory=list, description="Non-critical issues")

    def add_violation(self, violation: str):
        """Add a violation and mark as invalid"""
        self.violations.append(violation)
        self.is_valid = False

    def add_warning(self, warning: str):
        """Add a warning (doesn't affect validity)"""
        self.warnings.append(warning)

    def to_feedback_prompt(self) -> Optional[str]:
        """Generate correction prompt for retry"""
        if self.is_valid:
            return None

        prompt = "Please correct the following issues:\n\n"
        for i, violation in enumerate(self.violations, 1):
            prompt += f"{i}. {violation}\n"

        prompt += "\nGenerate corrected content that addresses ALL the above issues."
        return prompt