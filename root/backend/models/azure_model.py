import logging
# from langchain_community.chat_models import AzureChatOpenAI
from langchain_openai import AzureOpenAI, AzureChatOpenAI
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
                azure_endpoint=settings.api_base,
                openai_api_key=settings.api_key,
                openai_api_version=settings.api_version,
                temperature=0.5,
                max_tokens=4096
            )
            
            # deployment_name=deployment_name,
            # model_name="gpt-4o",  # Specify the model
            # openai_api_key=api_key,
            # azure_endpoint=azure_endpoint,
            # openai_api_version=api_version
            
            # self.llm = AzureOpenAI(
            #     deployment_name=settings.deployment_name,
            #     model_name=settings.model_name,
            #     openai_api_key=settings.api_key,
            #     azure_endpoint=settings.api_base,
            #     openai_api_version=settings.api_version
            # )
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
