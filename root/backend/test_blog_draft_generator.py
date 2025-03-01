import asyncio
import logging
from root.backend.agents.outline_generator_agent import OutlineGeneratorAgent
from root.backend.agents.content_parsing_agent import ContentParsingAgent
from root.backend.agents.blog_draft_generator_agent import BlogDraftGeneratorAgent
from root.backend.models.model_factory import ModelFactory

logging.basicConfig(level=logging.INFO)

async def generate_basic_draft():
    """
    Demonstrates the basic usage of the blog draft generator.
    This function shows how to generate a complete blog draft in one go,
    without any user interaction during the generation process.
    """
    project_name = "Task Project 2"
    notebook_path = "data/uploads/Task Project 2/text Processing.ipynb"
    markdown_path = "data/uploads/Task Project 2/Working with Text Data.md"
    model_name = "claude"  # Or any other valid model name

    # Get model instance
    model = ModelFactory().create_model(model_name)
    if not model:
        logging.error(f"Model '{model_name}' not found")
        return

    # Initialize content parsing agent
    content_parser = ContentParsingAgent(model)
    await content_parser.initialize()
    
    # Process files with content parser
    notebook_hash = await content_parser.process_file_with_graph(notebook_path, project_name)
    markdown_hash = await content_parser.process_file_with_graph(markdown_path, project_name)
    
    if not notebook_hash or not markdown_hash:
        logging.error("Failed to process input files")
        return
    
    # Initialize outline generator agent
    outline_agent = OutlineGeneratorAgent(model, content_parser)
    await outline_agent.initialize()
    
    # Generate outline using the content hashes
    outline_json, notebook_content, markdown_content = await outline_agent.generate_outline(
        project_name=project_name,
        notebook_hash=notebook_hash,
        markdown_hash=markdown_hash
    )

    if not outline_json:
        logging.error("Outline generation failed")
        return

    logging.info(f"Generated outline: {outline_json.title}")
    logging.info(type(outline_json))
    
    # Initialize blog draft generator agent
    draft_agent = BlogDraftGeneratorAgent(model, content_parser)
    await draft_agent.initialize()
    
    # Generate blog draft using the outline and parsed content
    blog_draft = await draft_agent.generate_draft(
        outline=outline_json,
        notebook_content=notebook_content,
        markdown_content=markdown_content
    )
    
    if not blog_draft:
        logging.error("Blog draft generation failed")
        return
    
    # Print the blog draft
    print("\n\n" + "="*50 + " GENERATED BLOG DRAFT " + "="*50)
    print(blog_draft)
    print("="*120)
    
    # Save the blog draft to a file
    output_path = f"data/uploads/{project_name}/generated_blog.md"
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(blog_draft)
        logging.info(f"Blog draft saved to {output_path}")
    except Exception as e:
        logging.error(f"Error saving blog draft: {e}")

async def generate_draft_with_feedback():
    """
    Demonstrates the advanced usage of the blog draft generator with user feedback.
    This function shows how to:
    1. Initialize the generation process
    2. Add user feedback during generation
    3. Track generation status
    4. Complete the generation with feedback incorporated
    
    This approach would typically be used in an interactive application where
    users can provide feedback on sections as they are generated.
    """
    project_name = "Task Project 2"
    notebook_path = "data/uploads/Task Project 2/text Processing.ipynb"
    markdown_path = "data/uploads/Task Project 2/Working with Text Data.md"
    model_name = "claude"  # Or any other valid model name

    # Get model instance
    model = ModelFactory().create_model(model_name)
    if not model:
        logging.error(f"Model '{model_name}' not found")
        return

    # Initialize content parsing agent
    content_parser = ContentParsingAgent(model)
    await content_parser.initialize()
    
    # Process files with content parser
    notebook_hash = await content_parser.process_file_with_graph(notebook_path, project_name)
    markdown_hash = await content_parser.process_file_with_graph(markdown_path, project_name)
    
    # Initialize outline generator agent
    outline_agent = OutlineGeneratorAgent(model, content_parser)
    await outline_agent.initialize()
    
    # Generate outline using the content hashes
    outline_json, notebook_content, markdown_content = await outline_agent.generate_outline(
        project_name=project_name,
        notebook_hash=notebook_hash,
        markdown_hash=markdown_hash
    )
    
    # Initialize blog draft generator agent
    draft_agent = BlogDraftGeneratorAgent(model, content_parser)
    await draft_agent.initialize()
    
    # Start the draft generation process
    # This would typically be done in a web application where the user can provide feedback
    # For demonstration purposes, we'll simulate the process
    
    # Initialize state
    initial_state = draft_agent.state_class(
        outline=outline_json,
        notebook_content=notebook_content,
        markdown_content=markdown_content,
        model=model
    )
    
    # Store the state for later access
    draft_agent.current_state = initial_state
    
    # Execute the first part of the graph (content mapping)
    # In a real application, this would be done incrementally with user feedback
    
    # Example of adding user feedback
    await draft_agent.add_user_feedback("Please add more code examples and explain the implementation details more thoroughly.")
    
    # Get generation status
    status = await draft_agent.get_generation_status()
    logging.info(f"Generation status: {status}")
    
    # In a real application, you would continue the graph execution after feedback
    # For demonstration, we'll just generate the complete draft
    blog_draft = await draft_agent.generate_draft(
        outline=outline_json,
        notebook_content=notebook_content,
        markdown_content=markdown_content
    )
    
    # Save the blog draft to a file
    output_path = f"data/uploads/{project_name}/generated_blog_with_feedback.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(blog_draft)
    logging.info(f"Blog draft with feedback saved to {output_path}")

if __name__ == "__main__":
    # Choose which function to run based on your needs:
    
    # Option 1: Basic draft generation (no user interaction)
    asyncio.run(generate_basic_draft())
    
    # Option 2: Advanced draft generation with user feedback
    # Uncomment the line below to run this instead
    # asyncio.run(generate_draft_with_feedback())
