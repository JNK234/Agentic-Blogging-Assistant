import os
import logging
from langchain_deepseek import ChatDeepSeek

class DeepseekModel:
    def __init__(self):
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is required")
        try:
            self.llm = ChatDeepSeek(
                model_name="deepseek-chat",
                api_key=self.api_key,
                temperature=0.7,
                max_tokens=1000
            )
        except Exception as e:
            logging.error(f"Failed to initialize Deepseek LLM chain: {str(e)}")
            raise

    def generate(self, messages):
        # Format messages into a single string
        formatted_messages = "\n".join([f"{message['role']}: {message['content']}" for message in messages])
        response = self.llm(formatted_messages)
        return response
