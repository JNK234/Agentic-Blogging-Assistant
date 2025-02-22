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
                max_tokens=8000
            )
        except Exception as e:
            logging.error(f"Failed to initialize Deepseek LLM chain: {str(e)}")
            raise

    def generate(self, messages):
        # Format messages into a single string
        formatted_messages = "\n".join([f"{message['role']}: {message['content']}" for message in messages])
        response = self.invoke(formatted_messages)
        return response

    def invoke(self, prompt: str):
        return self.llm.invoke(prompt)

    async def ainvoke(self, prompt: str):
        return await self.llm.ainvoke(prompt)
    
    async def generate_message(self, prompt):
        # Generate a message using the LLM
        response = await self.llm.ainvoke(prompt)
        return response
