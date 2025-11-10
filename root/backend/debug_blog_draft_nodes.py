import asyncio
import logging
import os
import json
import time
from datetime import datetime
from backend.agents.outline_generator_agent import OutlineGeneratorAgent
from backend.agents.content_parsing_agent import ContentParsingAgent
from backend.agents.blog_draft_generator_agent import BlogDraftGeneratorAgent
from backend.agents.blog_draft_generator.nodes import (
    semantic_content_mapper,
    section_generator,
    content_enhancer,
    code_example_extractor,
    quality_validator,
    auto_feedback_generator,
    feedback_incorporator,
    section_finalizer,
    transition_generator,
    blog_compiler
)
from backend.agents.blog_draft_generator.state import BlogDraftState
from backend.models.model_factory import ModelFactory

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"node_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)

class BlogDraftNodeDebugger:
    """
    A utility class for debugging individual nodes in the blog draft generator graph.
    """
    
    def __init__(self):
        self.model = None
        self.content_parser = None
        self.outline_agent = None
        self.project_name = None
        self.notebook_path = None
        self.markdown_path = None
        self.outline = None
        self.notebook_content = None
        self.markdown_content = None
        self.state = None
        self.debug_dir = f"node_debug_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.debug_dir, exist_ok=True)
    
    async def initialize(self):
        """Initialize the debugger with user input."""
        print("\n" + "="*80)
        print("BLOG DRAFT NODE DEBUGGER")
        print("="*80)
        
        # Get project name
        self.project_name = input("\nEnter project name (or 'next' for default 'Task Project 2'): ")
        if self.project_name == 'next' or not self.project_name:
            self.project_name = "Task Project 2"
        
        # Get notebook path
        self.notebook_path = input(f"\nEnter notebook path (or 'next' for default 'data/uploads/{self.project_name}/text Processing.ipynb'): ")
        if self.notebook_path == 'next' or not self.notebook_path:
            self.notebook_path = f"data/uploads/{self.project_name}/text Processing.ipynb"
        
        # Get markdown path
        self.markdown_path = input(f"\nEnter markdown path (or 'next' for default 'data/uploads/{self.project_name}/Working with Text Data.md'): ")
        if self.markdown_path == 'next' or not self.markdown_path:
            self.markdown_path = f"data/uploads/{self.project_name}/Working with Text Data.md"
        
        # Get model name
        model_name = input("\nEnter model name (or 'next' for default 'claude'): ")
        if model_name == 'next' or not model_name:
            model_name = "claude"
        
        # Initialize model
        print(f"\nInitializing model: {model_name}")
        self.model = ModelFactory().create_model(model_name)
        if not self.model:
            print(f"ERROR: Model '{model_name}' not found")
            return False
        
        # Initialize agents
        print("\nInitializing content parsing agent...")
        self.content_parser = ContentParsingAgent(self.model)
        await self.content_parser.initialize()
        
        print("\nInitializing outline generator agent...")
        self.outline_agent = OutlineGeneratorAgent(self.model, self.content_parser)
        await self.outline_agent.initialize()
        
        print("\nInitialization complete!")
        return True
    
    async def prepare_state(self):
        """Prepare the initial state for node testing."""
        print("\n" + "="*80)
        print("PREPARING INITIAL STATE")
        print("="*80)
        
        # Check if files exist
        if not os.path.exists(self.notebook_path):
            print(f"ERROR: Notebook file not found: {self.notebook_path}")
            return False
        
        if not os.path.exists(self.markdown_path):
            print(f"ERROR: Markdown file not found: {self.markdown_path}")
            return False
        
        # Process files
        print(f"\nProcessing notebook: {self.notebook_path}")
        notebook_hash = await self.content_parser.process_file_with_graph(self.notebook_path, self.project_name)
        if not notebook_hash:
            print("ERROR: Failed to process notebook file")
            return False
        
        print(f"\nProcessing markdown: {self.markdown_path}")
        markdown_hash = await self.content_parser.process_file_with_graph(self.markdown_path, self.project_name)
        if not markdown_hash:
            print("ERROR: Failed to process markdown file")
            return False
        
        # Generate outline
        print("\nGenerating outline...")
        self.outline, self.notebook_content, self.markdown_content = await self.outline_agent.generate_outline(
            project_name=self.project_name,
            notebook_hash=notebook_hash,
            markdown_hash=markdown_hash
        )
        
        if not self.outline:
            print("ERROR: Failed to generate outline")
            return False
        
        print(f"\nOutline generated successfully!")
        print(f"Title: {self.outline.title}")
        print(f"Number of sections: {len(self.outline.sections)}")
        
        # Create initial state
        self.state = BlogDraftState(
            outline=self.outline,
            notebook_content=self.notebook_content,
            markdown_content=self.markdown_content,
            model=self.model
        )
        
        # Save outline for debugging
        with open(f"{self.debug_dir}/outline.json", "w") as f:
            outline_dict = self.outline.dict() if hasattr(self.outline, "dict") else self.outline
            json.dump(outline_dict, f, indent=2)
        
        print("\nInitial state prepared successfully!")
        return True
    
    async def test_node(self, node_name):
        """Test a specific node in the graph."""
        if not self.state:
            print("ERROR: State not prepared. Run prepare_state first.")
            return False
        
        node_map = {
            "semantic_content_mapper": semantic_content_mapper,
            "section_generator": section_generator,
            "content_enhancer": content_enhancer,
            "code_example_extractor": code_example_extractor,
            "quality_validator": quality_validator,
            "auto_feedback_generator": auto_feedback_generator,
            "feedback_incorporator": feedback_incorporator,
            "section_finalizer": section_finalizer,
            "transition_generator": transition_generator,
            "blog_compiler": blog_compiler
        }
        
        if node_name not in node_map:
            print(f"ERROR: Unknown node '{node_name}'")
            return False
        
        node_func = node_map[node_name]
        
        print(f"\n" + "="*80)
        print(f"TESTING NODE: {node_name}")
        print("="*80)
        
        # Special handling for section_generator
        if node_name == "section_generator" and self.state.current_section_index == 0:
            print("\nPreparing state for section_generator...")
            # Make sure we have content mapping
            if not hasattr(self.state, 'content_mapping') or not self.state.content_mapping:
                print("Running semantic_content_mapper first to prepare content mapping...")
                self.state = await semantic_content_mapper(self.state)
        
        # Special handling for content_enhancer
        if node_name == "content_enhancer" and not self.state.current_section:
            print("\nPreparing state for content_enhancer...")
            # Make sure we have a current section
            if not self.state.sections:
                print("Running section_generator first to prepare a section...")
                self.state = await section_generator(self.state)
            self.state.current_section = self.state.sections[-1]
        
        # Special handling for feedback_incorporator
        if node_name == "feedback_incorporator":
            print("\nPreparing feedback for feedback_incorporator...")
            if not self.state.current_section:
                print("Running section_generator first to prepare a section...")
                self.state = await section_generator(self.state)
                self.state.current_section = self.state.sections[-1]
            
            # Add feedback
            feedback_text = input("\nEnter feedback for testing (or 'next' for default feedback): ")
            if feedback_text == 'next' or not feedback_text:
                feedback_text = "Please add more code examples and explain the implementation details more thoroughly."
            
            from backend.agents.blog_draft_generator.state import SectionFeedback
            from datetime import datetime
            
            feedback = SectionFeedback(
                content=feedback_text,
                source="user",
                timestamp=datetime.now().isoformat(),
                addressed=False
            )
            
            self.state.current_section.feedback.append(feedback)
            self.state.user_feedback_provided = True
        
        # Execute the node
        print(f"\nExecuting {node_name}...")
        start_time = time.time()
        
        try:
            updated_state = await node_func(self.state)
            execution_time = time.time() - start_time
            
            print(f"\n{node_name} executed successfully in {execution_time:.2f} seconds!")
            
            # Save state for debugging
            self.save_state_info(updated_state, node_name)
            
            # Update state for next node
            self.state = updated_state
            
            return True
        except Exception as e:
            print(f"\nERROR executing {node_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_state_info(self, state, node_name):
        """Save state information for debugging."""
        output_dir = f"{self.debug_dir}/{node_name}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Save general state info
        state_info = {
            "generation_stage": state.generation_stage,
            "current_section_index": state.current_section_index,
            "iteration_count": state.iteration_count,
            "sections_count": len(state.sections),
            "errors": state.errors
        }
        
        with open(f"{output_dir}/state_info.json", "w") as f:
            json.dump(state_info, f, indent=2)
        
        # Save content mapping if available
        if hasattr(state, 'content_mapping') and state.content_mapping:
            mapping_dict = {}
            for section_title, references in state.content_mapping.items():
                mapping_dict[section_title] = [
                    {
                        "content": ref.content[:200] + "..." if len(ref.content) > 200 else ref.content,
                        "source_type": ref.source_type,
                        "relevance_score": ref.relevance_score,
                        "category": ref.category
                    }
                    for ref in references
                ]
            
            with open(f"{output_dir}/content_mapping.json", "w") as f:
                json.dump(mapping_dict, f, indent=2)
        
        # Save current section if available
        if state.current_section:
            with open(f"{output_dir}/current_section.md", "w") as f:
                f.write(f"# {state.current_section.title}\n\n{state.current_section.content}")
            
            # Save section metadata
            section_meta = {
                "title": state.current_section.title,
                "status": state.current_section.status,
                "current_version": state.current_section.current_version,
                "feedback_count": len(state.current_section.feedback),
                "versions_count": len(state.current_section.versions),
                "code_examples_count": len(state.current_section.code_examples) if hasattr(state.current_section, 'code_examples') else 0
            }
            
            with open(f"{output_dir}/current_section_meta.json", "w") as f:
                json.dump(section_meta, f, indent=2)
        
        # Save all sections
        if state.sections:
            os.makedirs(f"{output_dir}/sections", exist_ok=True)
            for i, section in enumerate(state.sections):
                with open(f"{output_dir}/sections/section_{i+1}_{section.title.replace(' ', '_')}.md", "w") as f:
                    f.write(f"# {section.title}\n\n{section.content}")
        
        # Save final blog post if available
        if hasattr(state, 'final_blog_post') and state.final_blog_post:
            with open(f"{output_dir}/final_blog_post.md", "w") as f:
                f.write(state.final_blog_post)
        
        print(f"State information saved to {output_dir}")
    
    async def run_interactive_debug(self):
        """Run interactive debugging session."""
        if not await self.initialize():
            print("\nInitialization failed. Exiting.")
            return
        
        if not await self.prepare_state():
            print("\nState preparation failed. Exiting.")
            return
        
        while True:
            print("\n" + "="*80)
            print("AVAILABLE NODES")
            print("="*80)
            print("1. semantic_content_mapper - Maps content to sections")
            print("2. section_generator - Generates content for a section")
            print("3. content_enhancer - Enhances section content")
            print("4. code_example_extractor - Extracts and improves code examples")
            print("5. quality_validator - Validates section quality")
            print("6. auto_feedback_generator - Generates automatic feedback")
            print("7. feedback_incorporator - Incorporates feedback into content")
            print("8. section_finalizer - Finalizes the current section")
            print("9. transition_generator - Generates transitions between sections")
            print("10. blog_compiler - Compiles the final blog post")
            print("0. Exit")
            
            choice = input("\nEnter node number to test (or 0 to exit): ")
            
            if choice == '0':
                break
            
            node_map = {
                '1': "semantic_content_mapper",
                '2': "section_generator",
                '3': "content_enhancer",
                '4': "code_example_extractor",
                '5': "quality_validator",
                '6': "auto_feedback_generator",
                '7': "feedback_incorporator",
                '8': "section_finalizer",
                '9': "transition_generator",
                '10': "blog_compiler"
            }
            
            if choice in node_map:
                await self.test_node(node_map[choice])
            else:
                print("Invalid choice. Please try again.")
        
        print("\n" + "="*80)
        print("DEBUGGING SESSION COMPLETED")
        print("="*80)
        print(f"Debug output saved to: {self.debug_dir}")

async def main():
    """Main function to run the node debugger."""
    debugger = BlogDraftNodeDebugger()
    await debugger.run_interactive_debug()

if __name__ == "__main__":
    asyncio.run(main())
