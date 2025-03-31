# -*- coding: utf-8 -*-
"""
Agent responsible for generating social media posts and newsletter content
based on a finalized blog draft.
"""
import logging
import re
from root.backend.prompts.social_media.templates import SOCIAL_MEDIA_GENERATION_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SocialMediaAgent:
    """
    Generates social media content (LinkedIn, X/Twitter) and newsletter snippets
    from a given blog post markdown content.
    """

    def __init__(self, model):
        """
        Initializes the SocialMediaAgent.

        Args:
            model: An initialized language model instance (e.g., from ModelFactory).
        """
        self.llm = model
        self._initialized = False
        logger.info("SocialMediaAgent initialized.")

    async def initialize(self):
        """Placeholder for async initialization if needed in the future."""
        if self._initialized:
            return
        # Add any async setup here if required
        self._initialized = True
        logger.info("SocialMediaAgent async initialization complete.")

    def _parse_llm_response(self, response_text: str) -> dict:
        """
        Parses the LLM response string to extract structured content.

        Args:
            response_text: The raw text response from the language model.

        Returns:
            A dictionary containing the parsed content:
            {
                "content_breakdown": str | None,
                "linkedin_post": str | None,
                "x_post": str | None,
                "newsletter_content": str | None
            }
        """
        parsed_data = {
            "content_breakdown": None,
            "linkedin_post": None,
            "x_post": None,
            "newsletter_content": None
        }

        # Use regex to find content within specific tags
        tags = ["content_breakdown", "linkedin_post", "x_post", "newsletter_content"]
        for tag in tags:
            # Regex to find content between <tag> and </tag>, handling potential newlines
            # DOTALL flag makes '.' match newlines as well
            match = re.search(rf"<{tag}>(.*?)</{tag}>", response_text, re.DOTALL | re.IGNORECASE)
            if match:
                # Extract the content and strip leading/trailing whitespace
                parsed_data[tag] = match.group(1).strip()
            else:
                logger.warning(f"Could not find or parse content for tag: <{tag}>")

        return parsed_data

    async def generate_content(self, blog_content: str, blog_title: str = "Blog Post") -> dict | None:
        """
        Generates social media and newsletter content using the LLM.

        Args:
            blog_content: The full markdown content of the blog post.
            blog_title: The title of the blog post (used for placeholders).

        Returns:
            A dictionary containing the generated content for each platform,
            or None if generation fails.
        """
        if not self.llm:
            logger.error("LLM is not initialized.")
            return None
        if not blog_content:
            logger.error("Blog content cannot be empty.")
            return None

        logger.info(f"Generating social content for blog titled: {blog_title}")

        try:
            # Format the prompt with the blog content and title
            formatted_prompt = SOCIAL_MEDIA_GENERATION_PROMPT.format(
                blog_content=blog_content,
                blog_title=blog_title
            )

            # Invoke the language model
            logger.info("Invoking LLM for social content generation...")
            response = await self.llm.ainvoke(formatted_prompt)
            logger.info("LLM invocation complete.")

            # Extract content based on LLM response structure
            response_text = ""
            if hasattr(response, 'content'):
                response_text = response.content
            elif isinstance(response, str):
                 response_text = response
            else:
                 logger.warning(f"Unexpected LLM response type: {type(response)}")
                 response_text = str(response) # Fallback

            if not response_text:
                logger.error("LLM returned an empty response.")
                return None

            # Parse the structured response
            parsed_content = self._parse_llm_response(response_text)

            # Basic validation: Check if at least some content was parsed
            if not any(parsed_content.values()):
                 logger.error("Failed to parse any structured content from the LLM response.")
                 logger.debug(f"Raw LLM Response:\n{response_text}")
                 return None # Indicate failure if nothing could be parsed

            logger.info("Successfully generated and parsed social content.")
            return parsed_content

        except Exception as e:
            logger.exception(f"Error during social content generation: {e}")
            return None

# Example Usage (for testing purposes)
if __name__ == '__main__':
    import asyncio
    from root.backend.models.model_factory import ModelFactory # Assuming ModelFactory is accessible

    async def test_agent():
        # Replace with your actual model setup
        try:
            model_factory = ModelFactory()
            # Choose a model provider, e.g., 'gemini'
            model = model_factory.create_model('gemini')
        except Exception as model_err:
            print(f"Failed to create model: {model_err}")
            return

        agent = SocialMediaAgent(model)
        await agent.initialize()

        # Sample blog content (replace with actual content for real testing)
        sample_blog = """
        # Understanding Gradient Descent

        Gradient descent is a fundamental optimization algorithm used in machine learning...
        It works by iteratively moving in the direction of the steepest descent...

        ## Key Concepts
        - Learning Rate
        - Cost Function
        - Iterations

        ## Conclusion
        Gradient descent is powerful but requires careful tuning.
        """

        result = await agent.generate_content(sample_blog, blog_title="Understanding Gradient Descent")

        if result:
            print("Generated Content:")
            import json
            print(json.dumps(result, indent=2))
        else:
            print("Failed to generate content.")

    # Run the async test function
    asyncio.run(test_agent())
