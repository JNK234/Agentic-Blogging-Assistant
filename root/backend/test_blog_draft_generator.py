import asyncio
import os

import logging
from dotenv import load_dotenv

load_dotenv()

from root.backend.agents.blog_draft_generator_agent import BlogDraftGeneratorAgent
from root.backend.agents.outline_generator_agent import OutlineGeneratorAgent
from root.backend.models.model_factory import ModelFactory


# Configure logging
logging.basicConfig(level=logging.INFO)

async def main():
    # 1. Define file paths
    notebook_path = "root/data/uploads/Task Project 2/text Processing.ipynb"
    markdown_path = "root/data/uploads/Task Project 2/Working with Text Data.md"

    # 2. Initialize model first
    try:
        model = ModelFactory().create_model("azure")  # You can change the model provider here
        if model is None:
            logging.error("Model could not be initialized.")
            return
    except ValueError as e:
        logging.error(e)
        return

    # 3. Initialize agents and file parser
    outline_generator = OutlineGeneratorAgent()
    draft_generator = BlogDraftGeneratorAgent()

    # 4. Validate file paths
    if not os.path.exists(notebook_path) or not os.path.exists(markdown_path):
        logging.error("One or both input files do not exist")
        return

    # 5. Generate outline
    try:
        outline_str, parsed_notebook, parsed_markdown = await outline_generator.generate_outline(notebook_path, markdown_path, model)
        if isinstance(outline_str, str) and outline_str.startswith("Error"):
            logging.error(outline_str)
            return
        
        logging.info(f"Generated outline: {outline_str}")
    except Exception as e:
        logging.error(f"Error generating outline: {e}")
        return

    # 6. Generate draft using the outline and parsed content
    try:
        draft = await draft_generator.generate_draft(outline_str, parsed_notebook, parsed_markdown, model)
        logging.info(f"Generated draft: {draft}")
        logging.info(f"Draft generated successfully")
    except Exception as e:
        logging.error(f"Error generating draft: {e}")
        print(f"Error: {e}")
        return

if __name__ == "__main__":
    logging.info("Starting the test...")
    asyncio.run(main())
    logging.info("Test finished.")
