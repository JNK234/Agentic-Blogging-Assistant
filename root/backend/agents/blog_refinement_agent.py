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

        # Prepare the initial state for the graph
        initial_state = BlogRefinementState(original_draft=blog_draft)
        # Convert Pydantic model to dict for LangGraph input
        initial_state_dict = initial_state.model_dump()

        try:
            # Execute the graph with the initial state
            # The run_graph method is inherited from BaseGraphAgent
            final_state_dict = await self.run_graph(initial_state_dict)

            # --- Enhanced Logging ---
            logger.info(f"Blog refinement graph execution completed. Final state dictionary: {final_state_dict}")
            # --- End Enhanced Logging ---

            # Process the final state
            current_error = final_state_dict.get('error')
            if current_error:
                logger.error(f"Blog refinement graph finished with an error explicitly set in state: {current_error}")
                return None

            # Validate that all required fields for RefinementResult are present
            required_fields_for_result = ['refined_draft', 'summary', 'title_options']
            missing_for_result = [field for field in required_fields_for_result if field not in final_state_dict or final_state_dict.get(field) is None]

            if missing_for_result:
                logger.error(
                    f"Refinement graph completed but missing required fields for RefinementResult: {missing_for_result}. "
                    f"Current state of these fields: "
                    f"refined_draft: {final_state_dict.get('refined_draft') is not None}, "
                    f"summary: {final_state_dict.get('summary') is not None}, "
                    f"title_options: {final_state_dict.get('title_options') is not None}. "
                    f"Full final state: {final_state_dict}"
                )
                return None

            # Parse title options back into Pydantic models if needed, though they are stored as dicts
            # For returning RefinementResult, we need them as TitleOption objects
            title_options_data = final_state_dict.get('title_options', [])
            parsed_title_options = [TitleOption.model_validate(opt) for opt in title_options_data if isinstance(opt, dict)]

            logger.info("Blog refinement process completed successfully via graph.")

            # Construct and return the final result object
            return RefinementResult(
                refined_draft=final_state_dict['refined_draft'],
                summary=final_state_dict['summary'],
                title_options=parsed_title_options # Use the parsed list
            )

        except Exception as e:
            logger.exception(f"An unexpected error occurred while running the refinement graph: {e}")
            return None

    # Remove the old 'refine' method and individual generation methods
    # as the graph nodes now handle this logic.
    # The BaseGraphAgent's run_graph method is used for execution.
