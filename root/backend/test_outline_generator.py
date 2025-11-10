import asyncio
import logging
from backend.agents.outline_generator_agent import OutlineGeneratorAgent
from backend.agents.content_parsing_agent import ContentParsingAgent
from backend.models.model_factory import ModelFactory

logging.basicConfig(level=logging.INFO)

async def main():
    """Generates and prints a blog outline using hardcoded file paths."""
    project_name = "Task Project 2"
    notebook_path = "data/uploads/Task Project 2/text Processing.ipynb"
    markdown_path = "data/uploads/Task Project 2/Working with Text Data.md"
    model_name = "claude"  # Or any other valid model name

    # Get model instance
    model = ModelFactory().create_model(model_name)
    if not model:
        logging.error(f"Model '{model_name}' not found")
        return

    # Initialize content parsing agent separately
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

    logging.info(f"Generated outline: {outline_json}")
    # logging.info(f"Notebook content: {notebook_content}")
    # logging.info(f"Markdown content: {markdown_content}")

if __name__ == "__main__":
    asyncio.run(main())
