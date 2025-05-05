# -*- coding: utf-8 -*-
"""
Agent responsible for refining a compiled blog draft using a LangGraph workflow.
Inherits from BaseGraphAgent.
"""
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel

# Import BaseGraphAgent and necessary components
from root.backend.agents.base_agent import BaseGraphAgent
from root.backend.agents.blog_refinement.state import BlogRefinementState, RefinementResult, TitleOption
from root.backend.agents.blog_refinement.graph import create_refinement_graph
from root.backend.utils.serialization import serialize_object # For potential result serialization if needed

# Configure logging
logger = logging.getLogger(__name__)

class BlogRefinementAgent(BaseGraphAgent):
    """
    An agent that refines a blog draft using a LangGraph state machine.
    It generates introduction, conclusion, summary, and title options.
    """

    def __init__(self, model: BaseModel):
        """
        Initializes the BlogRefinementAgent.

        Args:
            model: An instance of a language model compatible with BaseGraphAgent.
        """
        super().__init__(
            llm=model,
            tools=[], # No specific tools needed for this agent's graph
            state_class=BlogRefinementState, # Use the defined state model
            verbose=True # Or configure as needed
        )
        self._initialized = False
        self.model = model # Keep model reference for graph creation
        logger.info(f"BlogRefinementAgent instantiated with model: {type(model).__name__}")

    async def initialize(self):
        """
        Initializes the agent by creating and compiling the LangGraph.
        """
        if self._initialized:
            logger.info("BlogRefinementAgent already initialized.")
            return

        try:
            # Create the graph, passing the model instance
            self.graph = await create_refinement_graph(self.model)
            self._initialized = True
            logger.info("BlogRefinementAgent initialized successfully with graph.")
        except Exception as e:
            logger.exception("Failed to initialize BlogRefinementAgent graph.")
            self._initialized = False
            # Optionally re-raise or handle initialization failure
            raise RuntimeError(f"BlogRefinementAgent initialization failed: {e}") from e

    async def refine_blog_with_graph(self, blog_draft: str) -> Optional[RefinementResult]:
        """
        Runs the blog refinement process using the compiled LangGraph.

        Args:
            blog_draft: The complete, compiled blog draft content.

        Returns:
            A RefinementResult object containing the refined draft, summary,
            and title options, or None if the process fails or encounters an error.
        """
        if not self._initialized or not self.graph:
            logger.error("BlogRefinementAgent is not initialized. Call initialize() first.")
            # Optionally try to initialize here, or raise an error
            await self.initialize()
            if not self._initialized or not self.graph:
                 raise RuntimeError("Failed to initialize BlogRefinementAgent before running.")


        logger.info("Starting blog refinement process via graph...")

        # Prepare the initial state for the graph as a Pydantic object
        initial_state = BlogRefinementState(original_draft=blog_draft)

        try:
            # Execute the graph with the initial state Pydantic object
            final_state_result = await self.run_graph(initial_state) # Returns a dict-like object

            # Handle the dict-like result from the graph
            final_state = None # Initialize final_state
            if isinstance(final_state_result, dict):
                logger.info(f"Graph returned dict-like object: {type(final_state_result)}. Attempting validation.")
                try:
                    # Use model_validate for Pydantic v2
                    final_state = BlogRefinementState.model_validate(final_state_result)
                    logger.info("Successfully validated final graph state dictionary into BlogRefinementState.")
                except ValidationError as e:
                    logger.error(f"Pydantic validation failed for final state dictionary: {e}. State Dict: {final_state_result}")
                    # Explicitly set error state before returning None
                    # This helps if the error check below relies on final_state being assigned
                    # Although returning None should prevent further processing anyway.
                    return None # Stop processing if validation fails
            else:
                 # If it's not dict-like, log the error and stop
                 logger.error(f"Graph execution returned unexpected type: {type(final_state_result)}. Expected dict-like. Result: {final_state_result}")
                 return None

            # Ensure final_state was successfully created
            if final_state is None:
                 logger.error("State validation failed, cannot proceed.")
                 return None

            # Process the validated Pydantic state object
            if final_state.error:
                logger.error(f"Blog refinement graph finished with error: {final_state.error}")
                return None

            # Validate that all required fields are present in the final state object
            if not final_state.refined_draft or not final_state.summary or not final_state.title_options:
                missing = []
                if not final_state.refined_draft: missing.append('refined_draft')
                if not final_state.summary: missing.append('summary')
                if not final_state.title_options: missing.append('title_options')
                logger.error(f"Refinement graph completed but missing required fields: {missing}. Final state: {final_state}")
                return None

            # Title options should already be list of dicts from the node,
            # but we need TitleOption objects for the RefinementResult
            parsed_title_options = [TitleOption.model_validate(opt) for opt in final_state.title_options if isinstance(opt, dict)]


            logger.info("Blog refinement process completed successfully via graph.")

            # Construct and return the final result object using attributes from the state object
            return RefinementResult(
                refined_draft=final_state.refined_draft,
                summary=final_state.summary,
                title_options=parsed_title_options
            )

        except Exception as e:
            logger.exception(f"An unexpected error occurred while running the refinement graph: {e}")
            return None

    # Remove the old 'refine' method and individual generation methods
    # as the graph nodes now handle this logic.
    # The BaseGraphAgent's run_graph method is used for execution.
