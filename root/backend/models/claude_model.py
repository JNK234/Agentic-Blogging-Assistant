import os
import logging
from langchain_anthropic import ChatAnthropic

class ClaudeModel:
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        try:
            self.llm = ChatAnthropic(
                model_name="claude-3-sonnet-20240229",
                api_key=self.api_key,
                temperature=0.7,
                max_tokens=100
            )
        except Exception as e:
            logging.error(f"Failed to initialize Claude LLM chain: {str(e)}")
            raise

    def generate(self, messages):
        # Format messages into a single string
        formatted_messages = "\n".join([f"{message['role']}: {message['content']}" for message in messages])
        response = self.llm(formatted_messages)
        return response
