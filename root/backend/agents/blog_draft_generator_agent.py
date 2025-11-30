from backend.agents.blog_draft_generator.graph import create_draft_graph
# Combine state imports
from backend.agents.blog_draft_generator.state import BlogDraftState, SectionFeedback, DraftSection
from backend.agents.outline_generator.state import FinalOutline
from backend.parsers import ContentStructure
from backend.agents.base_agent import BaseGraphAgent
from datetime import datetime
import logging
import hashlib # Added for cache key generation
import json # Added for serializing/deserializing cache data
from backend.services.vector_store_service import VectorStoreService # Added
from backend.services.persona_service import PersonaService # Added for persona integration
from typing import Tuple, Optional, Dict, Any # Added Dict, Any for type hinting

# Import necessary nodes at the top level
from backend.agents.blog_draft_generator.nodes import (
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

    # Updated __init__ to accept vector_store and persona_service
    def __init__(self, model, content_parser, vector_store: VectorStoreService, persona_service: PersonaService = None, sql_project_manager=None):
        super().__init__(
            llm=model,
            tools=[],
            state_class=BlogDraftState,
            verbose=True
        )
        self.content_parser = content_parser
        self.vector_store = vector_store # Store the passed instance
        self.persona_service = persona_service or PersonaService() # Initialize persona service
        self.sql_project_manager = sql_project_manager  # SQL project manager for persistence
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

    def _extract_intelligent_length_from_outline(self, outline) -> int:
        """Extract intelligent length from outline content analysis or use reasonable default."""
        try:
            # Try to access content analysis from outline structure
            if isinstance(outline, dict) and 'content_analysis' in outline:
                content_analysis = outline['content_analysis']
                if isinstance(content_analysis, dict) and 'suggested_blog_length' in content_analysis:
                    suggested_length = content_analysis['suggested_blog_length']
                    logging.info(f"Using AI-suggested blog length: {suggested_length} words")
                    return max(suggested_length, 800)  # Minimum 800 words
            
            # Fallback: estimate based on outline complexity
            sections_count = len(outline.get('sections', [])) if isinstance(outline, dict) else 0
            if sections_count == 0:
                return 1200  # Default for unknown structure
            
            # Estimate 300-400 words per section as baseline
            estimated_length = sections_count * 350
            estimated_length = max(estimated_length, 1000)  # Minimum 1000 words
            estimated_length = min(estimated_length, 4000)  # Maximum 4000 words
            
            logging.info(f"Estimated blog length based on {sections_count} sections: {estimated_length} words")
            return estimated_length
            
        except Exception as e:
            logging.warning(f"Could not extract intelligent length from outline: {e}. Using default.")
            return 1500  # Safe default

    async def generate_draft(
        self,
        project_name: str,
        outline,
        notebook_content,
        markdown_content,
        cost_aggregator=None,
        project_id: Optional[str] = None
    ): # Added project_name parameter
        """Generates a blog draft section by section using LangGraph."""
        logging.info(f"Generating draft for outline: {outline['title']} (Project: {project_name})")

        # Calculate intelligent target length
        intelligent_length = self._extract_intelligent_length_from_outline(outline)

        # Initialize state
        initial_state = BlogDraftState(
            project_name=project_name, # Added project_name initialization
            outline=outline,
            notebook_content=notebook_content,
            markdown_content=markdown_content,
            model=self.llm,
            target_total_length=intelligent_length,  # Use intelligent length
            remaining_length_budget=intelligent_length,  # Initialize budget
            cost_aggregator=cost_aggregator,
            project_id=project_id,
            current_stage="draft_generation",
            sql_project_manager=self.sql_project_manager  # Pass SQL manager for persistence
        )

        self.current_state = initial_state

        # Execute graph
        try:
            logging.info("Executing draft generation graph...")
            final_state = await self.run_graph(initial_state)
            logging.info("Draft generation graph completed successfully.")

            if hasattr(final_state, 'update_cost_summary'):
                final_state.update_cost_summary()

            self.current_state = final_state

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

    def _hash_outline_for_cache(self, outline: Dict[str, Any]) -> str:
        """Creates a deterministic hash for an outline dictionary."""
        # Ensure consistent serialization for hashing
        # Sort keys to handle potential dict ordering issues, though json.dumps usually sorts
        outline_string = json.dumps(outline, sort_keys=True)
        return hashlib.sha256(outline_string.encode()).hexdigest()

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
        # job_id: str, # No longer directly used for cache key generation here
        section: dict,
        outline: dict, # This is the full outline dictionary
        notebook_content: Optional[ContentStructure],
        markdown_content: Optional[ContentStructure],
        current_section_index: int,
        max_iterations=3,
        quality_threshold=0.8,
        use_cache: bool = True,
        cost_aggregator=None,
        project_id: Optional[str] = None,
        persona: str = "neuraforge"  # Add persona parameter with default
    ) -> Tuple[Optional[str], bool]:
        """Generates a single section of the blog draft, using persistent cache based on outline content."""
        section_title = section.get('title', f'Section {current_section_index + 1}')
        
        outline_hash = self._hash_outline_for_cache(outline)
        logging.info(f"Generating section {current_section_index}: {section_title} (Project: {project_name}, OutlineHash: {outline_hash})")

        cache_key = self._create_section_cache_key(project_name, outline_hash, current_section_index)

        # --- Check Cache ---
        if use_cache:
            cached_section_json = self.vector_store.retrieve_section_cache(
                cache_key=cache_key,
                project_name=project_name,
                outline_hash=outline_hash, # Use outline_hash for retrieval
                section_index=current_section_index
            )
            if cached_section_json:
                try:
                    cached_data = json.loads(cached_section_json)
                    logging.info(f"Cache hit for section {current_section_index} (OutlineHash: {outline_hash})")
                    # Return the full cached data including image placeholders
                    return {
                        "content": cached_data.get("content"),
                        "image_placeholders": cached_data.get("image_placeholders", [])
                    }, True
                except json.JSONDecodeError:
                    logging.warning(f"Failed to parse cached JSON for section {current_section_index} (OutlineHash: {outline_hash}). Regenerating.")
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
            current_section_index=current_section_index,
            cost_aggregator=cost_aggregator,
            project_id=project_id,
            current_stage="draft_generation",
            persona=persona,  # Pass the persona to the state
            sql_project_manager=self.sql_project_manager,  # Pass SQL manager for persistence
            outline_hash=outline_hash  # Pass outline hash for version tracking
            # job_id is not part of BlogDraftState, but available via project_name/index
        )

        self.current_state = section_state

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

            if hasattr(state, 'update_cost_summary'):
                state.update_cost_summary()

            generated_content = state.current_section.content if state.current_section else None
            image_placeholders = state.current_section.image_placeholders if state.current_section else []

            if generated_content:
                # --- Store in Cache ---
                if use_cache:
                    section_data_to_cache = {
                        "title": section_title,
                        "content": generated_content,
                        "image_placeholders": [
                            {
                                "type": p.type,
                                "description": p.description,
                                "alt_text": p.alt_text,
                                "placement": p.placement,
                                "purpose": p.purpose,
                                "section_context": p.section_context,
                                "source_reference": p.source_reference
                            } for p in image_placeholders
                        ] if image_placeholders else []
                    }
                    section_json = json.dumps(section_data_to_cache)
                    self.vector_store.store_section_cache(
                    section_json=section_json,
                    cache_key=cache_key,
                    project_name=project_name,
                    outline_hash=outline_hash, # Use outline_hash for storing
                    section_index=current_section_index
                )
                # --- End Store in Cache ---
                # Return content and image placeholders data
                return {
                    "content": generated_content,
                    "image_placeholders": section_data_to_cache.get("image_placeholders", [])
                }, False # Return dict with content and placeholders, and False for was_cached
            else:
                logging.error(f"Generation resulted in empty content for section {current_section_index}")
                return None, False # Return None and False for was_cached

        except Exception as e:
            msg = f"Error generating section {section_title}: {e}"
            logging.exception(msg)
            return None, False # Return None and False for was_cached

    # Updated method signature to use outline_hash implicitly via outline dict
    async def regenerate_section_with_feedback(
        self,
        project_name: str,
        # job_id: str, # No longer directly used for cache key generation here
        section: dict, # Contains title
        outline: dict, # Full outline for hashing
        notebook_content: Optional[ContentStructure],
        markdown_content: Optional[ContentStructure],
        feedback: str,
        max_iterations=3,
        quality_threshold=0.8,
        cost_aggregator=None,
        project_id: Optional[str] = None
    ) -> Optional[str]: # Return only content (cache status not relevant for direct regen call)
        """Regenerates a section with user feedback, updating the cache."""
        section_title = section.get('title', 'Unknown Section')
        
        # Calculate outline hash
        outline_hash = hashlib.sha256(json.dumps(outline, sort_keys=True).encode()).hexdigest()
        logging.info(f"Regenerating section with feedback: {section_title} (Project: {project_name}, OutlineHash: {outline_hash})")

        # Find the section index
        section_index = -1
        outline_sections = outline.get('sections', [])
        for i, s_data in enumerate(outline_sections):
            if isinstance(s_data, dict) and s_data.get('title') == section_title:
                section_index = i
                break
        
        if section_index == -1:
            logging.error(f"Section '{section_title}' not found in outline. Outline sections: {outline_sections}")
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
            quality_threshold=quality_threshold,
            cost_aggregator=cost_aggregator,
            project_id=project_id,
            current_stage="draft_generation",
            sql_project_manager=self.sql_project_manager  # Pass SQL manager for persistence
        )
        initial_state.user_feedback_provided = True

        self.current_state = initial_state

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

            if hasattr(state, 'update_cost_summary'):
                state.update_cost_summary()

            regenerated_content = state.current_section.content if state.current_section else None

            if regenerated_content:
                logging.info(f"Successfully regenerated section '{section_title}' with content length: {len(regenerated_content)}")
                # --- Update Cache ---
                cache_key = self._create_section_cache_key(project_name, outline_hash, section_index)
                section_data_to_cache = {
                    "title": section_title,
                    "content": regenerated_content
                }
                section_json = json.dumps(section_data_to_cache)
                self.vector_store.store_section_cache(
                    section_json=section_json,
                    cache_key=cache_key,
                    project_name=project_name,
                    outline_hash=outline_hash, # Use outline_hash for storing
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
