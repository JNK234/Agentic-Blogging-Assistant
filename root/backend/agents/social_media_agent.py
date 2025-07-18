# -*- coding: utf-8 -*-
"""
Agent responsible for generating social media posts and newsletter content
based on a finalized blog draft.
"""
import logging
import re
from root.backend.prompts.social_media.templates import SOCIAL_MEDIA_GENERATION_PROMPT, TWITTER_THREAD_GENERATION_PROMPT
from root.backend.services.persona_service import PersonaService
from root.backend.models.social_media import TwitterThread, Tweet, SocialMediaContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SocialMediaAgent:
    """
    Generates social media content (LinkedIn, X/Twitter) and newsletter snippets
    from a given blog post markdown content.
    """

    def __init__(self, model, persona_service=None):
        """
        Initializes the SocialMediaAgent.

        Args:
            model: An initialized language model instance (e.g., from ModelFactory).
            persona_service: Optional PersonaService instance for voice consistency.
        """
        self.llm = model
        self.persona_service = persona_service or PersonaService()
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

    async def generate_content(self, blog_content: str, blog_title: str = "Blog Post", persona: str = "student_sharing") -> dict | None:
        """
        Generates social media and newsletter content using the LLM.

        Args:
            blog_content: The full markdown content of the blog post.
            blog_title: The title of the blog post (used for placeholders).
            persona: The persona to use for content generation (default: "student_sharing").

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
            # Get persona instructions
            persona_instructions = self.persona_service.get_persona_prompt(persona)
            
            # Format the prompt with the blog content, title, and persona
            formatted_prompt = SOCIAL_MEDIA_GENERATION_PROMPT.format(
                persona_instructions=persona_instructions,
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

    def _parse_thread_response(self, response_text: str) -> dict:
        """
        Parses the LLM response to extract Twitter thread content.
        
        Args:
            response_text: The raw text response from the language model.
            
        Returns:
            A dictionary containing thread data and metadata.
        """
        thread_data = {
            "x_thread": None,
            "thread_topic": None,
            "learning_journey": None
        }
        
        # Extract thread content
        thread_match = re.search(r"<x_thread>(.*?)</x_thread>", response_text, re.DOTALL | re.IGNORECASE)
        if thread_match:
            thread_content = thread_match.group(1).strip()
            thread_data["x_thread"] = thread_content
        
        # Extract thread topic
        topic_match = re.search(r"\*\*Thread Topic:\*\*\s*(.+)", response_text, re.IGNORECASE)
        if topic_match:
            thread_data["thread_topic"] = topic_match.group(1).strip()
        
        # Extract learning journey
        journey_match = re.search(r"\*\*Learning Journey:\*\*\s*(.+)", response_text, re.IGNORECASE)
        if journey_match:
            thread_data["learning_journey"] = journey_match.group(1).strip()
        
        return thread_data

    def _parse_thread_content(self, thread_content: str, topic: str = "", journey: str = "") -> TwitterThread:
        """
        Parses thread content into structured TwitterThread object.
        
        Args:
            thread_content: Raw thread text with numbered tweets
            topic: Thread topic description
            journey: Learning journey description
            
        Returns:
            TwitterThread object with validated tweets
        """
        tweets = []
        
        # Split by tweet numbers (1., 2., etc.)
        tweet_pattern = r"(\d+)\.\s*(.+?)(?=\n\d+\.|$)"
        matches = re.findall(tweet_pattern, thread_content, re.DOTALL)
        
        for i, (tweet_num, content) in enumerate(matches, 1):
            cleaned_content = content.strip()
            # Remove extra whitespace and newlines
            cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
            
            tweet = Tweet(
                content=cleaned_content,
                character_count=len(cleaned_content),
                tweet_number=i
            )
            tweets.append(tweet)
        
        if not tweets:
            raise ValueError("No valid tweets found in thread content")
        
        return TwitterThread(
            tweets=tweets,
            total_tweets=len(tweets),
            hook_tweet=tweets[0].content if tweets else "",
            conclusion_tweet=tweets[-1].content if tweets else "",
            thread_topic=topic or "Learning thread",
            learning_journey=journey or "Sharing insights from learning journey"
        )

    async def generate_thread(self, blog_content: str, blog_title: str = "Blog Post", persona: str = "student_sharing") -> TwitterThread | None:
        """
        Generates a Twitter/X thread from blog content.
        
        Args:
            blog_content: The full markdown content of the blog post.
            blog_title: The title of the blog post.
            persona: The persona to use for content generation.
            
        Returns:
            TwitterThread object or None if generation fails.
        """
        if not self.llm:
            logger.error("LLM is not initialized.")
            return None
        if not blog_content:
            logger.error("Blog content cannot be empty.")
            return None
            
        logger.info(f"Generating Twitter thread for blog titled: {blog_title}")
        
        try:
            # Get persona instructions
            persona_instructions = self.persona_service.get_persona_prompt(persona)
            
            # Format the thread-specific prompt
            formatted_prompt = TWITTER_THREAD_GENERATION_PROMPT.format(
                persona_instructions=persona_instructions,
                blog_content=blog_content,
                blog_title=blog_title
            )
            
            # Invoke the language model
            logger.info("Invoking LLM for thread generation...")
            response = await self.llm.ainvoke(formatted_prompt)
            logger.info("LLM invocation complete.")
            
            # Extract content from response
            response_text = ""
            if hasattr(response, 'content'):
                response_text = response.content
            elif isinstance(response, str):
                response_text = response
            else:
                logger.warning(f"Unexpected LLM response type: {type(response)}")
                response_text = str(response)
            
            if not response_text:
                logger.error("LLM returned an empty response.")
                return None
            
            # Parse the thread response
            parsed_data = self._parse_thread_response(response_text)
            
            if not parsed_data["x_thread"]:
                logger.error("Failed to extract thread content from LLM response.")
                return None
            
            # Convert to structured TwitterThread object
            thread = self._parse_thread_content(
                parsed_data["x_thread"],
                parsed_data.get("thread_topic", ""),
                parsed_data.get("learning_journey", "")
            )
            
            logger.info(f"Successfully generated Twitter thread with {thread.total_tweets} tweets.")
            return thread
            
        except ValueError as ve:
            logger.error(f"Thread validation error: {ve}")
            return None
        except Exception as e:
            logger.exception(f"Error during thread generation: {e}")
            return None

    def _parse_comprehensive_response(self, response_text: str) -> dict:
        """
        Parses the LLM response to extract all social media content types.
        
        Args:
            response_text: The raw text response from the language model.
            
        Returns:
            A dictionary containing all parsed content.
        """
        parsed_data = {
            "content_breakdown": None,
            "linkedin_post": None,
            "x_post": None,
            "x_thread": None,
            "newsletter_content": None
        }
        
        # Parse standard tags
        standard_tags = ["content_breakdown", "linkedin_post", "x_post", "newsletter_content"]
        for tag in standard_tags:
            match = re.search(rf"<{tag}>(.*?)</{tag}>", response_text, re.DOTALL | re.IGNORECASE)
            if match:
                parsed_data[tag] = match.group(1).strip()
            else:
                logger.warning(f"Could not find or parse content for tag: <{tag}>")
        
        # Parse thread content
        thread_match = re.search(r"<x_thread>(.*?)</x_thread>", response_text, re.DOTALL | re.IGNORECASE)
        if thread_match:
            parsed_data["x_thread"] = thread_match.group(1).strip()
        else:
            logger.warning("Could not find or parse content for tag: <x_thread>")
        
        return parsed_data

    async def generate_comprehensive_content(self, blog_content: str, blog_title: str = "Blog Post", persona: str = "student_sharing") -> SocialMediaContent | None:
        """
        Generates comprehensive social media content including all formats.
        
        Args:
            blog_content: The full markdown content of the blog post.
            blog_title: The title of the blog post.
            persona: The persona to use for content generation.
            
        Returns:
            SocialMediaContent object with all content types or None if generation fails.
        """
        if not self.llm:
            logger.error("LLM is not initialized.")
            return None
        if not blog_content:
            logger.error("Blog content cannot be empty.")
            return None
            
        logger.info(f"Generating comprehensive social content for blog titled: {blog_title}")
        
        try:
            # Get persona instructions
            persona_instructions = self.persona_service.get_persona_prompt(persona)
            
            # Format the comprehensive prompt
            formatted_prompt = SOCIAL_MEDIA_GENERATION_PROMPT.format(
                persona_instructions=persona_instructions,
                blog_content=blog_content,
                blog_title=blog_title
            )
            
            # Invoke the language model
            logger.info("Invoking LLM for comprehensive social content generation...")
            response = await self.llm.ainvoke(formatted_prompt)
            logger.info("LLM invocation complete.")
            
            # Extract content from response
            response_text = ""
            if hasattr(response, 'content'):
                response_text = response.content
            elif isinstance(response, str):
                response_text = response
            else:
                logger.warning(f"Unexpected LLM response type: {type(response)}")
                response_text = str(response)
            
            if not response_text:
                logger.error("LLM returned an empty response.")
                return None
            
            # Parse the comprehensive response
            parsed_data = self._parse_comprehensive_response(response_text)
            
            # Check if we got at least some content
            if not any(parsed_data.values()):
                logger.error("Failed to parse any content from LLM response.")
                return None
            
            # Parse thread content if available
            twitter_thread = None
            if parsed_data["x_thread"]:
                try:
                    twitter_thread = self._parse_thread_content(
                        parsed_data["x_thread"],
                        f"Learning thread about {blog_title}",
                        "Sharing insights from learning journey"
                    )
                except ValueError as ve:
                    logger.warning(f"Failed to parse thread content: {ve}")
                    # Continue without thread rather than failing completely
            
            # Create comprehensive content object
            social_content = SocialMediaContent(
                content_breakdown=parsed_data["content_breakdown"],
                linkedin_post=parsed_data["linkedin_post"],
                x_post=parsed_data["x_post"],
                x_thread=twitter_thread,
                newsletter_content=parsed_data["newsletter_content"]
            )
            
            logger.info(f"Successfully generated comprehensive social content with thread: {bool(twitter_thread)}")
            return social_content
            
        except Exception as e:
            logger.exception(f"Error during comprehensive social content generation: {e}")
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
