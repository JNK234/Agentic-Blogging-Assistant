import os
import logging
from langchain_deepseek import ChatDeepSeek
from ..config.settings import DeepseekSettings

class DeepseekModel:
    def __init__(self, settings: DeepseekSettings):
        self.api_key = settings.api_key or os.getenv('DEEPSEEK_API_KEY')
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY environment variable is required")
        model_name = getattr(settings, 'model_name', 'deepseek-reasoner')
        temperature = getattr(settings, 'temperature', 0.7)
        max_tokens = getattr(settings, 'max_tokens', 8000)
        try:
            self.llm = ChatDeepSeek(
                model_name=model_name,
                api_key=self.api_key,
                temperature=temperature,
                max_tokens=max_tokens
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
