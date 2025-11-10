import asyncio
import logging
import os
import json
import time
from datetime import datetime
from backend.agents.outline_generator_agent import OutlineGeneratorAgent
from backend.agents.content_parsing_agent import ContentParsingAgent
from backend.agents.blog_draft_generator_agent import BlogDraftGeneratorAgent
from backend.models.model_factory import ModelFactory

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"blog_generation_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)

class InteractiveBlogTester:
    """
    Interactive tester for the blog generation pipeline.
    Allows step-by-step testing with user input at each stage.
    """
    
    def __init__(self):
        self.model = None
        self.content_parser = None
        self.outline_agent = None
        self.draft_agent = None
        self.project_name = None
        self.notebook_path = None
        self.markdown_path = None
        self.notebook_hash = None
        self.markdown_hash = None
        self.outline = None
        self.notebook_content = None
        self.markdown_content = None
        self.output_dir = None
        self.debug_mode = True
    
    async def initialize(self):
        """Initialize the tester with user input."""
        print("\n" + "="*80)
        print("INTERACTIVE BLOG DRAFT GENERATOR TESTER")
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
        
        # Get output directory
        self.output_dir = input(f"\nEnter output directory (or 'next' for default 'data/uploads/{self.project_name}'): ")
        if self.output_dir == 'next' or not self.output_dir:
            self.output_dir = f"data/uploads/{self.project_name}"
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
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
        
        print("\nInitializing blog draft generator agent...")
        self.draft_agent = BlogDraftGeneratorAgent(self.model, self.content_parser)
        await self.draft_agent.initialize()
        
        print("\nInitialization complete!")
        return True
    
    async def process_content(self):
        """Process content files with user input."""
        print("\n" + "="*80)
        print("STEP 1: CONTENT PARSING")
        print("="*80)
        
        # Check if files exist
        if not os.path.exists(self.notebook_path):
            print(f"ERROR: Notebook file not found: {self.notebook_path}")
            return False
        
        if not os.path.exists(self.markdown_path):
            print(f"ERROR: Markdown file not found: {self.markdown_path}")
            return False
        
        # Process notebook
        print(f"\nProcessing notebook: {self.notebook_path}")
        self.notebook_hash = await self.content_parser.process_file_with_graph(self.notebook_path, self.project_name)
        if not self.notebook_hash:
            print("ERROR: Failed to process notebook file")
            return False
        
        print(f"Notebook processed successfully. Hash: {self.notebook_hash}")
        
        # Process markdown
        print(f"\nProcessing markdown: {self.markdown_path}")
        self.markdown_hash = await self.content_parser.process_file_with_graph(self.markdown_path, self.project_name)
        if not self.markdown_hash:
            print("ERROR: Failed to process markdown file")
            return False
        
        print(f"Markdown processed successfully. Hash: {self.markdown_hash}")
        
        # Save content hashes for debugging
        if self.debug_mode:
            with open(f"{self.output_dir}/content_hashes.json", "w") as f:
                json.dump({
                    "notebook_hash": self.notebook_hash,
                    "markdown_hash": self.markdown_hash
                }, f, indent=2)
            print(f"Content hashes saved to {self.output_dir}/content_hashes.json")
        
        return True
    
    async def generate_outline(self):
        """Generate outline with user input."""
        print("\n" + "="*80)
        print("STEP 2: OUTLINE GENERATION")
        print("="*80)
        
        # Check if content hashes are available
        if not self.notebook_hash or not self.markdown_hash:
            print("ERROR: Content hashes not available. Run process_content first.")
            return False
        
        # Generate outline
        print("\nGenerating outline...")
        self.outline, self.notebook_content, self.markdown_content = await self.outline_agent.generate_outline(
            project_name=self.project_name,
            notebook_hash=self.notebook_hash,
            markdown_hash=self.markdown_hash
        )
        
        if not self.outline:
            print("ERROR: Failed to generate outline")
            return False
        
        print(f"\nOutline generated successfully!")
        print(f"Title: {self.outline.title}")
        print(f"Difficulty: {self.outline.difficulty_level}")
        print(f"Number of sections: {len(self.outline.sections)}")
        
        # Print sections
        print("\nSections:")
        for i, section in enumerate(self.outline.sections):
            print(f"  {i+1}. {section.title}")
        
        # Save outline for debugging
        if self.debug_mode:
            with open(f"{self.output_dir}/outline.json", "w") as f:
                # Convert to dict for JSON serialization
                outline_dict = self.outline.dict() if hasattr(self.outline, "dict") else self.outline
                json.dump(outline_dict, f, indent=2)
            print(f"Outline saved to {self.output_dir}/outline.json")
        
        # Ask if user wants to continue
        continue_input = input("\nDo you want to continue to blog draft generation? (yes/no): ")
        if continue_input.lower() not in ['yes', 'y', 'next']:
            print("Stopping after outline generation.")
            return False
        
        return True
    
    async def generate_draft(self):
        """Generate blog draft with user input."""
        print("\n" + "="*80)
        print("STEP 3: BLOG DRAFT GENERATION")
        print("="*80)
        
        # Check if outline is available
        if not self.outline:
            print("ERROR: Outline not available. Run generate_outline first.")
            return False
        
        # Ask if user wants to add feedback
        add_feedback = input("\nDo you want to add feedback during generation? (yes/no): ")
        with_feedback = add_feedback.lower() in ['yes', 'y']
        
        if with_feedback:
            # Initialize state for tracking
            initial_state = self.draft_agent.state_class(
                outline=self.outline,
                notebook_content=self.notebook_content,
                markdown_content=self.markdown_content,
                model=self.model
            )
            
            # Store the state for later access
            self.draft_agent.current_state = initial_state
            
            # Get feedback from user
            feedback_text = input("\nEnter your feedback (or 'next' for default feedback): ")
            if feedback_text == 'next' or not feedback_text:
                feedback_text = "Please add more code examples and explain the implementation details more thoroughly."
            
            # Add user feedback
            print(f"\nAdding feedback: {feedback_text}")
            feedback_added = await self.draft_agent.add_user_feedback(feedback_text)
            
            if not feedback_added:
                print("WARNING: Failed to add feedback, continuing without feedback")
            else:
                print("Feedback added successfully")
            
            # Get generation status
            status = await self.draft_agent.get_generation_status()
            print(f"\nGeneration status: {status}")
        
        # Generate the complete draft
        print("\nGenerating complete blog draft...")
        start_time = time.time()
        
        blog_draft = await self.draft_agent.generate_draft(
            outline=self.outline,
            notebook_content=self.notebook_content,
            markdown_content=self.markdown_content
        )
        
        execution_time = time.time() - start_time
        
        if not blog_draft or isinstance(blog_draft, str) and blog_draft.startswith("Error"):
            print(f"ERROR: Blog draft generation failed: {blog_draft}")
            return False
        
        # Save the blog draft
        output_filename = "generated_blog_with_feedback.md" if with_feedback else "generated_blog.md"
        output_path = f"{self.output_dir}/{output_filename}"
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(blog_draft)
        
        print(f"\nBlog draft generated successfully in {execution_time:.2f} seconds!")
        print(f"Saved to: {output_path}")
        
        # Ask if user wants to test section regeneration
        test_regeneration = input("\nDo you want to test section regeneration? (yes/no): ")
        if test_regeneration.lower() in ['yes', 'y']:
            await self.test_section_regeneration()
        
        return True
    
    async def test_section_regeneration(self):
        """Test section regeneration with user input."""
        print("\n" + "="*80)
        print("STEP 4: SECTION REGENERATION")
        print("="*80)
        
        # Check if outline is available
        if not self.outline or not hasattr(self.outline, 'sections') or not self.outline.sections:
            print("ERROR: Valid outline with sections not available.")
            return False
        
        # List sections
        print("\nAvailable sections:")
        for i, section in enumerate(self.outline.sections):
            print(f"  {i+1}. {section.title}")
        
        # Get section index
        section_index_input = input("\nEnter section number to regenerate (or 'next' for first section): ")
        if section_index_input == 'next' or not section_index_input:
            section_index = 0
        else:
            try:
                section_index = int(section_index_input) - 1
                if section_index < 0 or section_index >= len(self.outline.sections):
                    print(f"ERROR: Invalid section number. Must be between 1 and {len(self.outline.sections)}")
                    return False
            except ValueError:
                print("ERROR: Invalid input. Please enter a number.")
                return False
        
        # Get section
        section = self.outline.sections[section_index]
        print(f"\nSelected section: {section.title}")
        
        # Get feedback
        feedback_text = input("\nEnter feedback for this section (or 'next' for default feedback): ")
        if feedback_text == 'next' or not feedback_text:
            feedback_text = "This section needs more technical depth and practical examples."
        
        # Regenerate section
        print(f"\nRegenerating section with feedback: {feedback_text}")
        regenerated_section = await self.draft_agent.regenerate_section_with_feedback(
            section=section,
            outline=self.outline,
            notebook_content=self.notebook_content,
            markdown_content=self.markdown_content,
            feedback=feedback_text
        )
        
        if not regenerated_section:
            print(f"ERROR: Failed to regenerate section: {section.title}")
            return False
        
        # Save the regenerated section
        output_path = f"{self.output_dir}/regenerated_section_{section_index+1}.md"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {section.title}\n\n{regenerated_section}")
        
        print(f"\nSection regenerated successfully!")
        print(f"Saved to: {output_path}")
        
        return True

async def main():
    """Main function to run the interactive tester."""
    tester = InteractiveBlogTester()
    
    # Initialize
    if not await tester.initialize():
        print("\nInitialization failed. Exiting.")
        return
    
    # Process content
    if not await tester.process_content():
        print("\nContent processing failed. Exiting.")
        return
    
    # Generate outline
    if not await tester.generate_outline():
        print("\nOutline generation stopped. Exiting.")
        return
    
    # Generate draft
    if not await tester.generate_draft():
        print("\nDraft generation failed. Exiting.")
        return
    
    print("\n" + "="*80)
    print("TESTING COMPLETED SUCCESSFULLY")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
