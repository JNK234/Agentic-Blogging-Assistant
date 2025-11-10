# -*- coding: utf-8 -*-
"""
Agent responsible for generating social media posts and newsletter content
based on a finalized blog draft. Includes comprehensive cost tracking.
"""
import logging
import re
from typing import List, Optional
from backend.prompts.social_media.templates import SOCIAL_MEDIA_GENERATION_PROMPT, TWITTER_THREAD_GENERATION_PROMPT
from backend.services.persona_service import PersonaService
from backend.models.social_media import TwitterThread, Tweet, SocialMediaContent
from backend.services.sql_project_manager import MilestoneType
from backend.services.cost_aggregator import CostAggregator
from backend.models.cost_tracking_wrapper import CostTrackingModel
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SocialMediaAgent:
    """
    Generates social media content (LinkedIn, X/Twitter) and newsletter snippets
    from a given blog post markdown content.
    """

    def __init__(self, model, persona_service=None, sql_project_manager=None, project_id: Optional[str] = None):
        """
        Initializes the SocialMediaAgent.

        Args:
            model: An initialized language model instance (e.g., from ModelFactory).
            persona_service: Optional PersonaService instance for voice consistency.
            sql_project_manager: Optional SQL project manager for milestone persistence.
            project_id: Optional project ID for cost tracking and SQL storage.
        """
        self.llm = model
        self.persona_service = persona_service or PersonaService()
        self.sql_project_manager = sql_project_manager  # SQL project manager for persistence
        self.project_id = project_id
        self._initialized = False
        self.cost_aggregator = CostAggregator()
        self.cost_aggregator.start_workflow(project_id=project_id or 'social_media_unknown')
        self._llm_wrapped = False
        logger.info(f"SocialMediaAgent initialized with project_id: {project_id}")

    async def initialize(self):
        """Async initialization - wraps LLM with cost tracking."""
        if self._initialized:
            return
        # Wrap LLM with cost tracking
        if self.llm and not self._llm_wrapped:
            self.llm = CostTrackingModel(
                base_model=self.llm,
                model_name=getattr(self.llm, 'model_name', 'social_media_model') if hasattr(self.llm, 'model_name') else str(type(self.llm).__name__)
            )
            self.llm.configure_tracking(
                sql_project_manager=self.sql_project_manager,
                context={
                    "agent": "SocialMediaAgent",
                    "project_id": self.project_id,
                    "stage": "social_media_generation"
                }
            )
            self._llm_wrapped = True
            logger.info("LLM wrapped with cost tracking")
        self._initialized = True
        logger.info("SocialMediaAgent async initialization complete.")

    def _wrap_llm_for_cost_tracking(self):
        """Wrap LLM with cost tracking if not already wrapped."""
        if self.llm and not self._llm_wrapped:
            self.llm = CostTrackingModel(
                base_model=self.llm,
                model_name=getattr(self.llm, 'model_name', 'social_media_model') if hasattr(self.llm, 'model_name') else str(type(self.llm).__name__)
            )
            self.llm.configure_tracking(
                sql_project_manager=self.sql_project_manager,
                context={
                    "agent": "SocialMediaAgent",
                    "project_id": self.project_id,
                    "stage": "social_media_generation"
                }
            )
            self._llm_wrapped = True

    def get_cost_summary(self) -> dict:
        """Get the cost summary for this agent's operations."""
        return self.cost_aggregator.get_workflow_summary()

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
        Generates social media and newsletter content using the LLM with cost tracking.

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

        # Ensure LLM is wrapped for cost tracking
        self._wrap_llm_for_cost_tracking()

        try:
            # Get persona instructions
            persona_instructions = self.persona_service.get_persona_prompt(persona)

            # Format the prompt with the blog content, title, and persona
            formatted_prompt = SOCIAL_MEDIA_GENERATION_PROMPT.format(
                persona_instructions=persona_instructions,
                blog_content=blog_content,
                blog_title=blog_title
            )

            # Invoke the language model (with cost tracking if wrapped)
            logger.info("Invoking LLM for social content generation...")
            start_time = datetime.utcnow()
            response = await self.llm.ainvoke(formatted_prompt)
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"LLM invocation complete in {elapsed:.2f}s.")

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

    def _split_long_tweet(self, content: str, max_length: int = 280) -> List[str]:
        """
        Split a long tweet into multiple tweets while preserving meaning.
        
        Args:
            content: The original tweet content
            max_length: Maximum character length per tweet
            
        Returns:
            List of tweet parts
        """
        if len(content) <= max_length:
            return [content]
        
        # Try to split at sentence boundaries first
        sentences = re.split(r'(?<=[.!?])\s+', content)
        tweets = []
        current_tweet = ""
        
        for sentence in sentences:
            # If adding this sentence would exceed limit, start a new tweet
            if current_tweet and len(current_tweet + " " + sentence) > max_length:
                tweets.append(current_tweet.strip())
                current_tweet = sentence
            # If the sentence itself is too long, split it at word boundaries
            elif len(sentence) > max_length:
                if current_tweet:
                    tweets.append(current_tweet.strip())
                    current_tweet = ""
                
                # Split long sentence at word boundaries
                words = sentence.split()
                temp_tweet = ""
                for word in words:
                    if temp_tweet and len(temp_tweet + " " + word) > max_length:
                        tweets.append(temp_tweet.strip())
                        temp_tweet = word
                    else:
                        temp_tweet = temp_tweet + " " + word if temp_tweet else word
                
                if temp_tweet:
                    current_tweet = temp_tweet
            else:
                current_tweet = current_tweet + " " + sentence if current_tweet else sentence
        
        if current_tweet:
            tweets.append(current_tweet.strip())
        
        return tweets

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
        
        tweet_counter = 1
        for i, (tweet_num, content) in enumerate(matches):
            cleaned_content = content.strip()
            # Remove extra whitespace and newlines
            cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
            
            # Split long tweets if necessary
            tweet_parts = self._split_long_tweet(cleaned_content)
            
            for part in tweet_parts:
                tweet = Tweet(
                    content=part,
                    character_count=len(part),
                    tweet_number=tweet_counter
                )
                tweets.append(tweet)
                tweet_counter += 1
        
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
        Generates a Twitter/X thread from blog content with cost tracking.

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

        # Ensure LLM is wrapped for cost tracking
        self._wrap_llm_for_cost_tracking()

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
            start_time = datetime.utcnow()
            response = await self.llm.ainvoke(formatted_prompt)
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"LLM invocation complete in {elapsed:.2f}s.")
            
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

    async def generate_comprehensive_content(self, blog_content: str, blog_title: str = "Blog Post", persona: str = "student_sharing", project_id: Optional[str] = None) -> SocialMediaContent | None:
        """
        Generates comprehensive social media content including all formats with cost tracking.

        Args:
            blog_content: The full markdown content of the blog post.
            blog_title: The title of the blog post.
            persona: The persona to use for content generation.
            project_id: Optional project ID for SQL persistence and cost tracking.

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

        # Update project_id if provided
        if project_id and not self.project_id:
            self.project_id = project_id
            self.cost_aggregator.start_workflow(project_id=project_id)

        # Ensure LLM is wrapped for cost tracking
        self._wrap_llm_for_cost_tracking()

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
            start_time = datetime.utcnow()
            response = await self.llm.ainvoke(formatted_prompt)
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"LLM invocation complete in {elapsed:.2f}s.")

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

            # NEW: Save SOCIAL_GENERATED milestone to SQL if sql_project_manager is available
            if self.sql_project_manager and project_id:
                try:
                    milestone_data = {
                        "content_breakdown": parsed_data["content_breakdown"] or "",
                        "linkedin_post": parsed_data["linkedin_post"] or "",
                        "x_post": parsed_data["x_post"] or "",
                        "x_thread": {
                            "total_tweets": twitter_thread.total_tweets if twitter_thread else 0,
                            "hook_tweet": twitter_thread.hook_tweet if twitter_thread else "",
                            "conclusion_tweet": twitter_thread.conclusion_tweet if twitter_thread else "",
                            "thread_topic": twitter_thread.thread_topic if twitter_thread else "",
                            "learning_journey": twitter_thread.learning_journey if twitter_thread else ""
                        } if twitter_thread else None,
                        "newsletter_content": parsed_data["newsletter_content"] or "",
                        "blog_title": blog_title,
                        "persona": persona
                    }
                    await self.sql_project_manager.save_milestone(
                        project_id=project_id,
                        milestone_type=MilestoneType.SOCIAL_GENERATED,
                        data=milestone_data
                    )
                    logger.info(f"Saved SOCIAL_GENERATED milestone for project {project_id}")
                except Exception as e:
                    logger.error(f"Failed to save social media milestone: {e}")
                    # Don't fail the workflow for SQL errors

            logger.info(f"Successfully generated comprehensive social content with thread: {bool(twitter_thread)}")
            return social_content

        except Exception as e:
            logger.exception(f"Error during comprehensive social content generation: {e}")
            return None

# Example Usage (for testing purposes)
if __name__ == '__main__':
    import asyncio
    from backend.models.model_factory import ModelFactory # Assuming ModelFactory is accessible

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
