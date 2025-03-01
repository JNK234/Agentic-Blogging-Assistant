from root.backend.agents.blog_draft_generator.graph import create_draft_graph
from root.backend.agents.blog_draft_generator.state import BlogDraftState, SectionFeedback
from root.backend.agents.outline_generator.state import FinalOutline
from root.backend.parsers import ContentStructure
from root.backend.agents.base_agent import BaseGraphAgent
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)

class BlogDraftGeneratorAgent(BaseGraphAgent):
    """Agent responsible for generating blog drafts section by section."""
    
    def __init__(self, model, content_parser):
        super().__init__(
            llm=model,
            tools=[],
            state_class=BlogDraftState,
            verbose=True
        )
        self.content_parser = content_parser
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

    async def generate_draft(self, outline, notebook_content, markdown_content):
        """Generates a blog draft section by section using LangGraph."""
        logging.info(f"Generating draft for outline: {outline['title']}")

        # Initialize state
        initial_state = BlogDraftState(
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
            f"{final_state.outline.prerequisites}\n\n",
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
        
        logging.info(f"Added user feedback to section: {self.current_state.current_section.title}")
        return True
    
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

    async def generate_section(self, section, outline, notebook_content, markdown_content, current_section_index, max_iterations=3, quality_threshold=0.8):
        """Generates a single section of the blog draft."""
        logging.info(f"Generating section: {section['title']}")
        
        # Reset the current state to ensure fresh generation
        self.current_state = None
        logging.info("Reset agent state to ensure fresh generation")
        
        # Initialize state for this section
        # Create a DraftSection object for the current section
        from root.backend.agents.blog_draft_generator.state import DraftSection
        
        draft_section = DraftSection(
            title=section['title'],
            content="",  # Initialize with empty content
            status="draft"
        )
        
        section_state = BlogDraftState(
            outline=outline,
            notebook_content=notebook_content,
            markdown_content=markdown_content,
            model=self.llm,
            current_section=draft_section,
            max_iterations=max_iterations,
            quality_threshold=quality_threshold,
            current_section_index=current_section_index
        )
        
        # Instead of using the full graph, we'll execute the nodes directly in sequence
        # This avoids the recursion limit issue by controlling the flow manually
        try:
            logging.info(f"Executing direct section generation for: {section['title']}")
            
            # Step 1: Map content to this section
            from root.backend.agents.blog_draft_generator.nodes import semantic_content_mapper
            state = await semantic_content_mapper(section_state)
            
            # Step 2: Generate the section content
            from root.backend.agents.blog_draft_generator.nodes import section_generator
            state = await section_generator(state)
            
            # Step 3: Enhance the content
            from root.backend.agents.blog_draft_generator.nodes import content_enhancer
            state = await content_enhancer(state)
            
            # Step 4: Extract code examples
            from root.backend.agents.blog_draft_generator.nodes import code_example_extractor
            state = await code_example_extractor(state)
            
            # Step 5: Validate quality and iterate if needed
            from root.backend.agents.blog_draft_generator.nodes import quality_validator
            state = await quality_validator(state)
            
            # Controlled iteration loop - manually implement the feedback loop
            iteration = 1
            while iteration < max_iterations:
                # Check if quality is good enough to stop
                if hasattr(state.current_section, 'quality_metrics') and state.current_section.quality_metrics:
                    overall_score = state.current_section.quality_metrics.get('overall_score', 0.0)
                    if overall_score >= quality_threshold:
                        logging.info(f"Quality threshold met ({overall_score} >= {quality_threshold}), stopping iterations")
                        break
                
                logging.info(f"Quality not yet met, starting iteration {iteration+1}/{max_iterations}")
                
                # Generate feedback
                from root.backend.agents.blog_draft_generator.nodes import auto_feedback_generator
                state = await auto_feedback_generator(state)
                
                # Incorporate feedback
                from root.backend.agents.blog_draft_generator.nodes import feedback_incorporator
                state = await feedback_incorporator(state)
                
                # Validate quality again
                state = await quality_validator(state)
                
                iteration += 1
            
            # Step 6: Finalize the section
            from root.backend.agents.blog_draft_generator.nodes import section_finalizer
            state = await section_finalizer(state)
            
            logging.info(f"Section generation completed for: {section['title']}")
            
            # Return the section content
            if state.current_section and state.current_section.content:
                return state.current_section.content
            else:
                return None
        except Exception as e:
            msg = f"Error generating section {section['title']}: {e}"
            logging.exception(msg)
            return None

    async def regenerate_section_with_feedback(self, section, outline, notebook_content, markdown_content, feedback, max_iterations=3, quality_threshold=0.8):
        """Regenerates a section with user feedback."""
        logging.info(f"Regenerating section with feedback: {section['title']}")
        
        # Initialize state for this section
        from root.backend.agents.blog_draft_generator.state import DraftSection, SectionFeedback
        from datetime import datetime
        
        # Find the section index
        section_index = -1
        for i, s in enumerate(outline['sections']):
            if s['title'] == section['title']:
                section_index = i
                break
                
        if section_index == -1:
            logging.error(f"Section '{section['title']}' not found in outline")
            return None
        
        # Reset the current state to ensure fresh generation
        self.current_state = None
        logging.info("Reset agent state to ensure fresh regeneration")
        
        # Create a DraftSection object for the current section
        draft_section = DraftSection(
            title=section['title'],
            content="",  # Initialize with empty content
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
        
        # Initialize state
        initial_state = BlogDraftState(
            outline=outline,
            notebook_content=notebook_content,
            markdown_content=markdown_content,
            model=self.llm,
            current_section=draft_section,
            current_section_index=section_index,
            max_iterations=max_iterations,
            quality_threshold=quality_threshold
        )
        initial_state.user_feedback_provided = True
        
        # Execute nodes directly in sequence, similar to generate_section
        try:
            logging.info(f"Executing direct section regeneration with feedback for: {section['title']}")
            
            # Step 1: Map content to this section
            from root.backend.agents.blog_draft_generator.nodes import semantic_content_mapper
            state = await semantic_content_mapper(initial_state)
            
            # Step 2: Generate the section content
            from root.backend.agents.blog_draft_generator.nodes import section_generator
            state = await section_generator(state)
            
            # Step 3: Incorporate the user feedback
            from root.backend.agents.blog_draft_generator.nodes import feedback_incorporator
            state = await feedback_incorporator(state)
            
            # Step 4: Enhance the content
            from root.backend.agents.blog_draft_generator.nodes import content_enhancer
            state = await content_enhancer(state)
            
            # Step 5: Extract code examples
            from root.backend.agents.blog_draft_generator.nodes import code_example_extractor
            state = await code_example_extractor(state)
            
            # Step 6: Validate quality and iterate if needed
            from root.backend.agents.blog_draft_generator.nodes import quality_validator
            state = await quality_validator(state)
            
            # Controlled iteration loop - manually implement the feedback loop
            iteration = 1
            while iteration < max_iterations:
                # Check if quality is good enough to stop
                if hasattr(state.current_section, 'quality_metrics') and state.current_section.quality_metrics:
                    overall_score = state.current_section.quality_metrics.get('overall_score', 0.0)
                    if overall_score >= quality_threshold:
                        logging.info(f"Quality threshold met ({overall_score} >= {quality_threshold}), stopping iterations")
                        break
                
                logging.info(f"Quality not yet met, starting iteration {iteration+1}/{max_iterations}")
                
                # Generate feedback (auto feedback, not user feedback)
                from root.backend.agents.blog_draft_generator.nodes import auto_feedback_generator
                state = await auto_feedback_generator(state)
                
                # Incorporate feedback
                state = await feedback_incorporator(state)
                
                # Validate quality again
                state = await quality_validator(state)
                
                iteration += 1
            
            # Step 7: Finalize the section
            from root.backend.agents.blog_draft_generator.nodes import section_finalizer
            state = await section_finalizer(state)
            
            logging.info(f"Section regeneration completed for: {section['title']}")
            
            # Return the section content
            if state.current_section and state.current_section.content:
                logging.info(f"Successfully regenerated section '{section['title']}' with content length: {len(state.current_section.content)}")
                return state.current_section.content
            else:
                logging.error(f"Failed to regenerate section content for '{section['title']}'")
                return None
        except Exception as e:
            msg = f"Error regenerating section with feedback {section['title']}: {e}"
            logging.exception(msg)
            return None
