# ABOUTME: Streamlit UI component for configuring title and social media generation settings
# ABOUTME: Provides interactive controls for setting counts and optional guidelines

import streamlit as st
import json
from typing import Optional, Dict, List

def render_title_generation_config():
    """
    Render UI controls for title generation configuration.

    Returns:
        Dict containing the title generation configuration
    """
    with st.expander("📝 Title Generation Settings", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            num_titles = st.slider(
                "Number of title options",
                min_value=1,
                max_value=10,
                value=3,
                help="How many title variations to generate"
            )

            num_subtitles = st.slider(
                "Subtitles per title",
                min_value=1,
                max_value=3,
                value=1,
                help="Number of subtitle variants for each title"
            )

        with col2:
            max_title_length = st.number_input(
                "Max title length (chars)",
                min_value=0,
                max_value=100,
                value=0,
                step=10,
                help="0 means no limit"
            )

            max_subtitle_length = st.number_input(
                "Max subtitle length (chars)",
                min_value=0,
                max_value=200,
                value=0,
                step=20,
                help="0 means no limit"
            )

        # Guidelines section
        st.subheader("📋 Mandatory Guidelines")
        st.caption("Enter guidelines that MUST be followed (optional but enforced when provided)")

        guidelines_text = st.text_area(
            "Guidelines (one per line)",
            height=100,
            placeholder="Example:\nMust include the main topic keyword\nUse active voice\nFocus on value proposition\nAvoid clickbait language",
            help="Each line becomes a mandatory guideline that the AI must follow"
        )

        # Parse guidelines from text
        guidelines = []
        if guidelines_text:
            guidelines = [line.strip() for line in guidelines_text.split('\n') if line.strip()]

        # Required keywords
        keywords_text = st.text_input(
            "Required keywords (comma-separated)",
            placeholder="e.g., machine learning, neural networks, AI",
            help="At least one of these keywords must appear in titles"
        )

        required_keywords = []
        if keywords_text:
            required_keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]

        # Style tone
        style_tone = st.selectbox(
            "Tone/Style",
            options=["", "professional", "conversational", "technical", "educational", "inspirational"],
            index=0,
            help="Overall tone for the titles"
        )

        # Build configuration
        config = {
            "num_titles": num_titles,
            "num_subtitles_per_title": num_subtitles
        }

        # Add optional fields only if they have values
        if guidelines:
            config["mandatory_guidelines"] = guidelines

        if max_title_length > 0:
            config["max_title_length"] = max_title_length

        if max_subtitle_length > 0:
            config["max_subtitle_length"] = max_subtitle_length

        if required_keywords:
            config["required_keywords"] = required_keywords

        if style_tone:
            config["style_tone"] = style_tone

        # Display current configuration outside of nested expander
        st.caption("Current Title Configuration:")
        st.json(config)

        return config


def render_social_media_config():
    """
    Render UI controls for social media generation configuration.

    Returns:
        Dict containing the social media generation configuration
    """
    with st.expander("📱 Social Media Settings", expanded=False):
        st.subheader("Platform-Specific Settings")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**LinkedIn**")
            linkedin_variants = st.slider(
                "Post variants",
                min_value=1,
                max_value=3,
                value=1,
                key="linkedin_variants"
            )

        with col2:
            st.markdown("**Twitter/X**")
            twitter_singles = st.slider(
                "Single post variants",
                min_value=1,
                max_value=3,
                value=1,
                key="twitter_singles"
            )

            twitter_thread_length = st.slider(
                "Thread length (tweets)",
                min_value=3,
                max_value=10,
                value=5,
                key="twitter_thread"
            )

        with col3:
            st.markdown("**Newsletter**")
            newsletter_variants = st.slider(
                "Content variants",
                min_value=1,
                max_value=2,
                value=1,
                key="newsletter_variants"
            )

        # Hashtag settings
        st.subheader("Hashtag Configuration")

        col1, col2 = st.columns(2)

        with col1:
            include_hashtags = st.checkbox("Include hashtags", value=True)

            if include_hashtags:
                max_hashtags = st.number_input(
                    "Max hashtags per post",
                    min_value=1,
                    max_value=10,
                    value=3
                )

        with col2:
            required_hashtags = st.text_input(
                "Required hashtags",
                placeholder="e.g., #AI, #MachineLearning",
                help="Hashtags that must be included"
            )

        # General guidelines
        st.subheader("📋 Social Media Guidelines")

        general_guidelines = st.text_area(
            "General guidelines (all platforms)",
            height=80,
            placeholder="Example:\nFocus on key insights\nUse clear, simple language\nInclude call-to-action",
            key="social_general_guidelines"
        )

        # Platform-specific guidelines - using columns instead of nested expander
        st.subheader("Platform-Specific Guidelines")
        col1, col2, col3 = st.columns(3)

        with col1:
            linkedin_guidelines = st.text_area(
                "LinkedIn-specific",
                height=70,
                placeholder="Professional tone, industry insights",
                key="linkedin_guidelines"
            )

        with col2:
            twitter_guidelines = st.text_area(
                "Twitter-specific",
                height=70,
                placeholder="Concise, punchy, thread-friendly",
                key="twitter_guidelines"
            )

        with col3:
            newsletter_guidelines = st.text_area(
                "Newsletter-specific",
                height=70,
                placeholder="Detailed, educational, value-focused",
                key="newsletter_guidelines"
            )

        # Build configuration
        config = {
            "linkedin_variants": linkedin_variants,
            "twitter_single_variants": twitter_singles,
            "twitter_thread_length": twitter_thread_length,
            "newsletter_variants": newsletter_variants,
            "include_hashtags": include_hashtags
        }

        # Add optional fields
        if include_hashtags and max_hashtags:
            config["max_hashtags"] = max_hashtags

        if required_hashtags:
            hashtags = [tag.strip() for tag in required_hashtags.split(',') if tag.strip()]
            if hashtags:
                config["required_hashtags"] = hashtags

        if general_guidelines:
            guidelines = [line.strip() for line in general_guidelines.split('\n') if line.strip()]
            if guidelines:
                config["mandatory_guidelines"] = guidelines

        # Platform-specific guidelines
        platform_guidelines = {}
        if linkedin_guidelines:
            linkedin_g = [line.strip() for line in linkedin_guidelines.split('\n') if line.strip()]
            if linkedin_g:
                platform_guidelines["linkedin"] = linkedin_g

        if twitter_guidelines:
            twitter_g = [line.strip() for line in twitter_guidelines.split('\n') if line.strip()]
            if twitter_g:
                platform_guidelines["twitter"] = twitter_g

        if newsletter_guidelines:
            newsletter_g = [line.strip() for line in newsletter_guidelines.split('\n') if line.strip()]
            if newsletter_g:
                platform_guidelines["newsletter"] = newsletter_g

        if platform_guidelines:
            config["platform_specific_guidelines"] = platform_guidelines

        # Display current configuration outside of nested expander
        st.caption("Current Social Media Configuration:")
        st.json(config)

        return config


def get_generation_configs():
    """
    Main function to get both title and social media configurations.

    Returns:
        Tuple of (title_config_json, social_config_json) as JSON strings
    """
    st.markdown("### ⚙️ Generation Configuration")
    st.caption("Customize how titles and social media content are generated")

    title_config = render_title_generation_config()
    social_config = render_social_media_config()

    # Convert to JSON strings for API
    title_config_json = json.dumps(title_config) if title_config else None
    social_config_json = json.dumps(social_config) if social_config else None

    return title_config_json, social_config_json


# Example usage in main app
def example_usage():
    """
    Example of how to integrate this in the main Streamlit app
    """
    st.title("Blog Generation with Configuration")

    # Get configurations
    title_config_json, social_config_json = get_generation_configs()

    # Show how to use in API call
    if st.button("Generate with Configuration"):
        st.code(f"""
# API call with configuration
response = api_client.refine_blog(
    project_name="my_project",
    job_id="job_123",
    compiled_draft=compiled_draft,
    title_config={title_config_json},
    social_config={social_config_json}
)
        """, language="python")


if __name__ == "__main__":
    # Test the component
    example_usage()