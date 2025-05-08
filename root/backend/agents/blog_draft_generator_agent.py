from root.backend.agents.blog_draft_generator.graph import create_draft_graph
# Combine state imports
from root.backend.agents.blog_draft_generator.state import BlogDraftState, SectionFeedback, DraftSection
from root.backend.agents.outline_generator.state import FinalOutline
from root.backend.parsers import ContentStructure
from root.backend.agents.base_agent import BaseGraphAgent
from datetime import datetime
import logging
import hashlib # Added for cache key generation
import json # Added for serializing/deserializing cache data
from root.backend.services.vector_store_service import VectorStoreService # Added
from typing import Tuple, Optional # Added for type hinting

# Import necessary nodes at the top level
from root.backend.agents.blog_draft_generator.nodes import (
    semantic_content_mapper,
    section_generator,
    content_enhancer,
    code_example_extractor,
    quality_validator,
    auto_feedback_generator,
    feedback_incorporator,
    section_finalizer,
    generate_hypothetical_document, # New HyDE node (will be used later)
    retrieve_context_with_hyde      # New HyDE node (will be used later)
)

logging.basicConfig(level=logging.INFO)

class BlogDraftGeneratorAgent(BaseGraphAgent):
    """Agent responsible for generating blog drafts section by section."""

    # Updated __init__ to accept vector_store
    def __init__(self, model, content_parser, vector_store: VectorStoreService):
        super().__init__(
            llm=model,
            tools=[],
            state_class=BlogDraftState,
            verbose=True
        )
        self.content_parser = content_parser
        self.vector_store = vector_store # Store the passed instance
        self._initialized = False
        self.current_state = None

    async def initialize(self):
        """Initialize the agent and its components."""
        if self._initialized:
            return

        self.graph = await create_draft_graph()
        await self.content_parser.initialize()
        self._initialized = True
        logging.info("BlogDraftGeneratorAgent initialized successfully")

    async def generate_draft(self, project_name: str, outline, notebook_content, markdown_content): # Added project_name parameter
        """Generates a blog draft section by section using LangGraph."""
        logging.info(f"Generating draft for outline: {outline['title']} (Project: {project_name})")

        # Initialize state
        initial_state = BlogDraftState(
            project_name=project_name, # Added project_name initialization
            outline=outline,
            notebook_content=notebook_content,
            markdown_content=markdown_content,
            model=self.llm
        )

        # Execute graph
        try:
            logging.info("Executing draft generation graph...")
            final_state = await self.run_graph(initial_state)
            logging.info("Draft generation graph completed successfully.")

            # Return complete blog post
            if hasattr(final_state, 'final_blog_post') and final_state.final_blog_post:
                return final_state.final_blog_post
            else:
                # Fallback compilation if graph doesn't produce final_blog_post
                return self._compile_final_draft(final_state)
        except Exception as e:
            msg = f"Error generating draft: {e}"
            logging.exception(msg)
            return f"Error generating draft: {str(e)}"

    def _compile_final_draft(self, final_state: BlogDraftState) -> str:
        """Compiles the final blog draft from all sections."""

        # Start with blog title and metadata
        blog_parts = [
            f"# {final_state.outline.title}\n",
            f"**Difficulty Level**: {final_state.outline.difficulty_level}\n",
            "\n## Prerequisites\n",
            # Handle prerequisites potentially being dict or str
            f"{json.dumps(final_state.outline.prerequisites, indent=2) if isinstance(final_state.outline.prerequisites, dict) else final_state.outline.prerequisites}\n\n",
            "## Table of Contents\n"
        ]

        # Add table of contents
        for i, section in enumerate(final_state.sections):
            blog_parts.append(f"{i+1}. [{section.title}](#section-{i+1})\n")

        blog_parts.append("\n")

        # Add each section with transitions
        for i, section in enumerate(final_state.sections):
            # Add section anchor and title
            blog_parts.extend([
                f"<a id='section-{i+1}'></a>\n",
                f"## {section.title}\n",
                f"{section.content}\n\n"
            ])

            # Add transition to next section if available
            if i < len(final_state.sections) - 1:
                next_section = final_state.sections[i+1]
                transition_key = f"{section.title}_to_{next_section.title}"
                if transition_key in final_state.transitions:
                    blog_parts.append(f"{final_state.transitions[transition_key]}\n\n")

        # Add conclusion if available
        if hasattr(final_state.outline, 'conclusion') and final_state.outline.conclusion:
            blog_parts.extend([
                "## Conclusion\n",
                f"{final_state.outline.conclusion}\n\n"
            ])

        return "\n".join(blog_parts)

    async def add_user_feedback(self, feedback_text):
        """Adds user feedback to the current section being generated."""
        if not self.current_state or not self.current_state.current_section:
            logging.warning("No current section to add feedback to")
            return False

        # Create feedback object
        feedback = SectionFeedback(
            content=feedback_text,
            source="user",
            timestamp=datetime.now().isoformat(),
            addressed=False
        )

        # Add to current section
        self.current_state.current_section.feedback.append(feedback)

        # Set flag to indicate feedback is provided
        self.current_state.user_feedback_provided = True

        logging.info(f"Added user feedback to section: {self.current_state.current_section.title}") # Corrected indentation
        return True

    # Method to hash the relevant parts of the outline
    def _hash_outline_for_cache(self, outline: dict) -> str:
        """Creates a hash based on the outline structure for caching purposes."""
        # Select relevant fields that define the outline structure
        # Using title and section titles/subsections seems reasonable
        relevant_data = {
            "title": outline.get("title"),
            "sections": [
                {"title": s.get("title"), "subsections": s.get("subsections")}
                for s in outline.get("sections", [])
            ]
        }
        # Serialize deterministically and hash
        outline_string = json.dumps(relevant_data, sort_keys=True)
        return hashlib.sha256(outline_string.encode()).hexdigest()

    # Updated cache key generation to use outline_hash
    def _create_section_cache_key(self, project_name: str, outline_hash: str, section_index: int) -> str:
        """Creates a deterministic cache key for a section based on outline hash."""
        key_string = f"section_cache:{project_name}:{outline_hash}:{section_index}"
        return hashlib.sha256(key_string.encode()).hexdigest()

    async def get_generation_status(self):
        """Returns the current status of the draft generation process."""
        if not self.current_state:
            return {
                "status": "Not started",
                "sections_completed": 0,
                "total_sections": 0
            }

        return {
            "status": self.current_state.generation_stage,
            "current_section": self.current_state.current_section.title if self.current_state.current_section else None,
            "sections_completed": len(self.current_state.completed_sections),
            "total_sections": len(self.current_state.outline.sections),
            "iteration": self.current_state.iteration_count,
            "errors": self.current_state.errors
        }

    # Updated method signature to include job_id and return tuple (content, was_cached)
    # Updated method signature to remove job_id (not needed for cache key) and pass full outline
    async def generate_section(
        self,
        project_name: str,
        # job_id: str, # No longer needed directly for cache key
        section: dict,
        outline: dict, # Pass the full outline dict
        notebook_content: Optional[ContentStructure],
        markdown_content: Optional[ContentStructure],
        current_section_index: int,
        max_iterations=3,
        quality_threshold=0.8,
        use_cache: bool = True # Added cache control
    ) -> Tuple[Optional[str], bool]: # Return content and cache status
        """Generates a single section of the blog draft, using persistent cache."""
        section_title = section.get('title', f'Section {current_section_index + 1}')
        logging.info(f"Generating section {current_section_index}: {section_title} (Project: {project_name})") # Removed Job ID from log

        outline_hash = self._hash_outline_for_cache(outline) # Generate hash from outline
        cache_key = self._create_section_cache_key(project_name, outline_hash, current_section_index) # Use new key

        # --- Check Cache ---
        if use_cache:
            cached_section_json = self.vector_store.retrieve_section_cache(
                cache_key=cache_key,
                project_name=project_name,
                outline_hash=outline_hash, # Pass outline_hash instead of job_id
                section_index=current_section_index
            )
            if cached_section_json:
                try:
                    cached_data = json.loads(cached_section_json)
                    logging.info(f"Cache hit for section {current_section_index} (Outline Hash: {outline_hash})")
                    # Return cached content and True for was_cached
                    return cached_data.get("content"), True
                except json.JSONDecodeError:
                    logging.warning(f"Failed to parse cached JSON for section {current_section_index}. Regenerating.")
        # --- End Cache Check ---

        logging.info(f"Cache miss for section {current_section_index} (Outline Hash: {outline_hash}). Proceeding with generation.")
        # Reset the current state to ensure fresh generation
        self.current_state = None
        # logging.info("Reset agent state to ensure fresh generation") # Can be verbose

        # Initialize state for this section
        draft_section = DraftSection(
            title=section_title,
            content="",
            status="draft"
        )

        # Ensure ContentStructure objects are provided, even if empty
        default_cs = ContentStructure(main_content="", code_segments=[], content_type="none")
        nb_content = notebook_content if notebook_content is not None else default_cs
        md_content = markdown_content if markdown_content is not None else default_cs

        section_state = BlogDraftState(
            project_name=project_name,
            outline=outline,
            notebook_content=nb_content,
            markdown_content=md_content,
            model=self.llm,
            current_section=draft_section,
            max_iterations=max_iterations,
            quality_threshold=quality_threshold,
            current_section_index=current_section_index
            # job_id is not part of BlogDraftState, but available via project_name/index
        )

        # Execute nodes directly in sequence
        try:
            logging.info(f"Executing direct section generation for: {section_title}")

            # --- HyDE RAG Steps ---
            state = await generate_hypothetical_document(section_state)
            state = await retrieve_context_with_hyde(state)
            # --- End HyDE RAG Steps ---

            state = await section_generator(state)
            state = await content_enhancer(state)
            state = await code_example_extractor(state)
            state = await quality_validator(state)

            # Controlled iteration loop
            iteration = 1
            while iteration < max_iterations:
                if hasattr(state.current_section, 'quality_metrics') and state.current_section.quality_metrics:
                    overall_score = state.current_section.quality_metrics.get('overall_score', 0.0)
                    if overall_score >= quality_threshold:
                        logging.info(f"Quality threshold met ({overall_score} >= {quality_threshold}), stopping iterations")
                        break
                logging.info(f"Quality not yet met, starting iteration {iteration+1}/{max_iterations}")
                state = await auto_feedback_generator(state)
                state = await feedback_incorporator(state)
                state = await quality_validator(state)
                iteration += 1

            state = await section_finalizer(state)
            logging.info(f"Section generation completed for: {section_title}")

            generated_content = state.current_section.content if state.current_section else None

            if generated_content:
                # --- Store in Cache ---
                if use_cache:
                    section_data_to_cache = {
                        "title": section_title,
                        "content": generated_content
                    }
                    section_json = json.dumps(section_data_to_cache)
                    self.vector_store.store_section_cache(
                        section_json=section_json,
                        cache_key=cache_key,
                        project_name=project_name,
                        outline_hash=outline_hash, # Pass outline_hash instead of job_id
                        section_index=current_section_index
                    )
                # --- End Store in Cache ---
                return generated_content, False # Return content and False for was_cached
            else:
                logging.error(f"Generation resulted in empty content for section {current_section_index}")
                return None, False # Return None and False for was_cached

        except Exception as e:
            msg = f"Error generating section {section_title}: {e}"
            logging.exception(msg)
            return None, False # Return None and False for was_cached

    # Updated method signature to remove job_id (not needed for cache key)
    async def regenerate_section_with_feedback(
        self,
        project_name: str,
        # job_id: str, # No longer needed directly for cache key
        section: dict,
        outline: dict,
        notebook_content: Optional[ContentStructure],
        markdown_content: Optional[ContentStructure],
        feedback: str,
        max_iterations=3,
        quality_threshold=0.8
    ) -> Optional[str]: # Return only content (cache status not relevant for direct regen call)
        """Regenerates a section with user feedback, updating the cache."""
        section_title = section.get('title', 'Unknown Section')
        logging.info(f"Regenerating section with feedback: {section_title} (Project: {project_name})") # Removed Job ID from log

        # Find the section index
        section_index = -1
        for i, s in enumerate(outline.get('sections', [])):
            # Ensure comparison works even if section is not a dict (though it should be)
            if isinstance(s, dict) and s.get('title') == section_title:
                section_index = i
                break

        if section_index == -1:
            logging.error(f"Section '{section_title}' not found in outline") # Removed Job ID from log
            return None

        # Reset the current state to ensure fresh regeneration
        self.current_state = None
        # logging.info("Reset agent state to ensure fresh regeneration")

        # Create a DraftSection object for the current section
        draft_section = DraftSection(
            title=section_title,
            content="",
            status="draft"
        )

        # Add user feedback
        feedback_obj = SectionFeedback(
            content=feedback,
            source="user",
            timestamp=datetime.now().isoformat(),
            addressed=False
        )
        draft_section.feedback.append(feedback_obj)

        # Ensure ContentStructure objects are provided, even if empty
        default_cs = ContentStructure(main_content="", code_segments=[], content_type="none")
        nb_content = notebook_content if notebook_content is not None else default_cs
        md_content = markdown_content if markdown_content is not None else default_cs

        # Initialize state
        initial_state = BlogDraftState(
            project_name=project_name,
            outline=outline,
            notebook_content=nb_content,
            markdown_content=md_content,
            model=self.llm,
            current_section=draft_section,
            current_section_index=section_index,
            max_iterations=max_iterations,
            quality_threshold=quality_threshold
        )
        initial_state.user_feedback_provided = True

        # Execute nodes directly in sequence
        try:
            logging.info(f"Executing direct section regeneration with feedback for: {section_title}")

            # --- HyDE RAG Steps ---
            state = await generate_hypothetical_document(initial_state)
            state = await retrieve_context_with_hyde(state)
            # --- End HyDE RAG Steps ---

            state = await section_generator(state)
            state = await feedback_incorporator(state) # Incorporate user feedback
            state = await content_enhancer(state)
            state = await code_example_extractor(state)
            state = await quality_validator(state)

            # Controlled iteration loop
            iteration = 1
            while iteration < max_iterations:
                if hasattr(state.current_section, 'quality_metrics') and state.current_section.quality_metrics:
                    overall_score = state.current_section.quality_metrics.get('overall_score', 0.0)
                    if overall_score >= quality_threshold:
                        logging.info(f"Quality threshold met ({overall_score} >= {quality_threshold}), stopping iterations")
                        break
                logging.info(f"Quality not yet met, starting iteration {iteration+1}/{max_iterations}")
                state = await auto_feedback_generator(state)
                state = await feedback_incorporator(state) # Incorporate auto-feedback
                state = await quality_validator(state)
                iteration += 1

            state = await section_finalizer(state)
            logging.info(f"Section regeneration completed for: {section_title}")

            regenerated_content = state.current_section.content if state.current_section else None

            if regenerated_content:
                logging.info(f"Successfully regenerated section '{section_title}' with content length: {len(regenerated_content)}")
                # --- Update Cache ---
                outline_hash = self._hash_outline_for_cache(outline) # Generate hash from outline
                cache_key = self._create_section_cache_key(project_name, outline_hash, section_index) # Use new key
                section_data_to_cache = {
                    "title": section_title,
                    "content": regenerated_content
                }
                section_json = json.dumps(section_data_to_cache)
                self.vector_store.store_section_cache(
                    section_json=section_json,
                    cache_key=cache_key,
                    project_name=project_name,
                    outline_hash=outline_hash, # Pass outline_hash instead of job_id
                    section_index=section_index
                )
                # --- End Update Cache ---
                return regenerated_content
            else:
                logging.error(f"Failed to regenerate section content for '{section_title}'")
                return None
        except Exception as e:
            msg = f"Error regenerating section with feedback {section_title}: {e}"
            logging.exception(msg)
            return None
