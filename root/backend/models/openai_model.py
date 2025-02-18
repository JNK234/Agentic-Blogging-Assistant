import os
import logging
from langchain_openai import ChatOpenAI

class OpenAIModel:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        try:
            self.llm = ChatOpenAI(
                model_name="gpt-3.5-turbo",
                openai_api_key=self.api_key,
                temperature=0.7,
                max_tokens=1000
            )
        except Exception as e:
            logging.error(f"Failed to initialize OpenAI LLM chain: {str(e)}")
            raise

    def generate(self, messages):
        # Format messages into a single string
        formatted_messages = "\n".join([f"{message['role']}: {message['content']}" for message in messages])
        response = self.llm(formatted_messages)
        return response
