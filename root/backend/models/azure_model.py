import logging
from langchain_community.chat_models import AzureChatOpenAI
from ..config.settings import AzureSettings

class AzureModel:
    def __init__(self, settings: AzureSettings):
        """
        Initialize Azure OpenAI model.
        
        Args:
            settings: Azure configuration settings
        """
        try:
            self.llm = AzureChatOpenAI(
                deployment_name=settings.deployment_name,
                openai_api_base=settings.api_base,
                openai_api_key=settings.api_key,
                openai_api_version=settings.api_version,
                temperature=0.5,
                max_tokens=4096
            )
        except Exception as e:
            logging.error(f"Failed to initialize Azure OpenAI LLM: {str(e)}")
            raise

    def agenerate(self, messages):
        # Format messages into a single string
        formatted_messages = "\n".join([f"{message['role']}: {message['content']}" for message in messages])
        response = self.invoke(formatted_messages)
        return response

    def invoke(self, prompt: str):
        return self.llm.invoke(prompt)

    async def ainvoke(self, prompt: str):
        return await self.llm.ainvoke(prompt)
