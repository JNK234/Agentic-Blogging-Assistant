import logging
from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage # Import HumanMessage

logger = logging.getLogger(__name__)

class GeminiModel:
    """
    Wrapper for Google Gemini models using the LangChain library.
    Provides invoke and ainvoke methods for synchronous and asynchronous calls.
    """
    def __init__(self, settings: Dict[str, Any]):
        """
        Initializes the GeminiModel using LangChain's ChatGoogleGenerativeAI.

        Args:
            settings: A dictionary containing model configuration, including 'api_key' and 'model_name'.

        Raises:
            ValueError: If the API key is missing.
            Exception: If the LangChain model initialization fails.
        """
        self.api_key = getattr(settings, 'api_key', None) # Use getattr for safer access
        if not self.api_key:
            raise ValueError("Gemini API key is required but not found in settings.")

        self.model_name = getattr(settings, 'model_name', "gemini-pro") # Default to gemini-pro

        try:
            # Initialize the LangChain ChatGoogleGenerativeAI model
            # Pass temperature and max_tokens if they exist in settings, otherwise use defaults
            temperature = getattr(settings, 'temperature', 0.7)
            max_tokens = getattr(settings, 'max_tokens', None) # Gemini uses max_output_tokens internally via LangChain

            self.llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=temperature,
                max_output_tokens=max_tokens,
                convert_system_message_to_human=True # Recommended for Gemini
            )
            logger.info(f"GeminiModel initialized with LangChain wrapper for model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize LangChain Gemini model: {str(e)}")
            # Raise the original exception for better debugging
            raise

    def invoke(self, prompt: str) -> str:
        """
        Synchronously invokes the Gemini model using LangChain.

        Args:
            prompt: The input prompt string.

        Returns:
            The generated text content as a string.

        Raises:
            Exception: If the API call fails.
        """
        try:
            logger.debug(f"Invoking Gemini model {self.model_name} synchronously...")
            # LangChain expects a list of messages or a string; wrap prompt in HumanMessage for clarity
            response = self.llm.invoke([HumanMessage(content=prompt)])
            logger.debug("Sync invocation successful.")
            # The response object has a 'content' attribute
            return response.content
        except Exception as e:
            logger.exception(f"Error during synchronous Gemini invoke: {str(e)}")
            raise Exception(f"Gemini API call failed (sync): {str(e)}")

    async def ainvoke(self, prompt: str) -> str:
        """
        Asynchronously invokes the Gemini model using LangChain.

        Args:
            prompt: The input prompt string.

        Returns:
            The generated text content as a string.

        Raises:
            Exception: If the API call fails.
        """
        try:
            logger.debug(f"Invoking Gemini model {self.model_name} asynchronously...")
            # LangChain expects a list of messages or a string; wrap prompt in HumanMessage for clarity
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            logger.debug("Async invocation successful.")
            # The response object has a 'content' attribute
            return response.content
        except Exception as e:
            logger.exception(f"Error during asynchronous Gemini invoke: {str(e)}")
            raise Exception(f"Gemini API call failed (async): {str(e)}")

    def configure_tracking(self, **kwargs):
        """
        Stub method for compatibility with cost tracking decorator.
        GeminiModel doesn't track costs internally - this is a no-op.
        Cost tracking should be handled by CostTrackingModel wrapper or external decorators.
        """
        # No-op: GeminiModel doesn't implement cost tracking directly
        pass

    # Placeholder for potential future embedding functionality if needed via LangChain
    # async def get_embedding(self, text: str) -> List[float]:
    #     # Implementation would use LangChain's GoogleGenerativeAIEmbeddings
    #     pass
