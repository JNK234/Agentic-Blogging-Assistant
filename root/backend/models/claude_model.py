import os
import logging
from langchain_anthropic import ChatAnthropic

class ClaudeModel:
    def __init__(self, model_settings):
        try:
            self.llm = ChatAnthropic(
                model=model_settings.model_name,
                api_key=model_settings.api_key,
                temperature=0.2,
                max_tokens=4096
            )
        except Exception as e:
            logging.error(f"Failed to initialize Claude LLM chain: {str(e)}")
            raise

    def generate(self, messages):
        # Format messages into a single string
        formatted_messages = "\n".join([f"{message['role']}: {message['content']}" for message in messages])
        response = self.invoke(formatted_messages)
        return response

    def invoke(self, prompt: str):
        return self.llm.invoke(prompt)

    async def ainvoke(self, prompt: str):
        response = await self.llm.ainvoke(prompt)
        return response
