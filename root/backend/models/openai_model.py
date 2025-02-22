import logging
from langchain_openai import ChatOpenAI
from ..config.settings import OpenAISettings

class OpenAIModel:
    def __init__(self, settings: OpenAISettings):
        """
        Initialize OpenAI model.
        
        Args:
            settings: OpenAI configuration settings
        """
        try:
            self.llm = ChatOpenAI(
                model_name=settings.model_name,
                openai_api_key=settings.api_key,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens
            )
        except Exception as e:
            logging.error(f"Failed to initialize OpenAI LLM chain: {str(e)}")
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
