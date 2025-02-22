from root.backend.prompts.prompt_manager import PromptManager
from root.backend.agents.outline_generator.graph import create_outline_graph
from root.backend.agents.outline_generator.state import OutlineState
from root.backend.utils.file_parser import FileParser

import logging

logging.basicConfig(level=logging.INFO)

class OutlineGeneratorAgent:
    def __init__(self):
        self.prompt_manager = PromptManager()
        self.graph = create_outline_graph()
        self.file_parser = FileParser()

    async def generate_outline(self, notebook_path: str, markdown_path: str, model) -> str:
        """Generates a blog outline using LangGraph."""
        logging.info(f"Generating outline for notebook: {notebook_path} and markdown: {markdown_path}")
        # Parse both files
        logging.info("Parsing notebook content...")
        notebook_content = self.file_parser.parse_file(notebook_path)
        logging.info("Parsing markdown content...")
        markdown_content = self.file_parser.parse_file(markdown_path)
        
        # Initialize state
        initial_state = OutlineState(
            notebook_content=notebook_content,
            markdown_content=markdown_content,
            model=model,
        )

        # Execute graph
        try:
            logging.info("Executing outline generation graph...")
            state = await self.graph.ainvoke(initial_state)
            logging.info("Outline generation graph completed successfully.")
            
            print(type(state))
            
            if state.final_outline:
                return state.final_outline, initial_state.notebook_content, initial_state.markdown_content
            else:
                msg = "Error generating outline: Final outline not found."
                logging.error(msg)
                return msg, None, None
        except Exception as e:
            msg = f"Error generating outline: {e}"
            logging.exception(msg)
            return f"Error generating outline: {e}", None, None
