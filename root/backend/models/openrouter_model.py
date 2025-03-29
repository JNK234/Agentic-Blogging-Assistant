import logging
import json
import requests
import aiohttp
import re
from ..config.settings import OpenRouterSettings

class OpenRouterModel:
    def __init__(self, settings: OpenRouterSettings):
        try:
            # Store settings for later use
            self.settings = settings
            self.temperature = 0.7
            self.max_tokens = settings.max_tokens
            
            # Set up headers
            self.headers = {
                "Authorization": f"Bearer {settings.api_key}",
                "Content-Type": "application/json",
                **settings.headers
            }
        except Exception as e:
            logging.error(f"OpenRouter initialization failed: {str(e)}")
            raise

    def generate(self, messages):
        """
        Generate a response from a list of messages.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
        """
        # Messages are already in the format expected by the OpenAI API
        return self.invoke(messages)

    def invoke(self, prompt):
        """
        Invoke the model with a prompt.
        
        Args:
            prompt: Either a string or a list of message dictionaries
        """
        try:
            # If prompt is a string, convert it to a messages array
            if isinstance(prompt, str):
                messages = [{"role": "user", "content": prompt}]
            else:
                messages = prompt

            # Prepare the request data
            data = {
                "model": self.settings.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }

            # Make the API request
            response = requests.post(
                self.settings.base_url,
                headers=self.headers,
                data=json.dumps(data)
            )

            # Check for successful response
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                error_msg = f"OpenRouter API error: {response.status_code}, {response.text}"
                logging.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            logging.error(f"OpenRouter invoke error: {str(e)}")
            raise
        
    def extract_response(self, text):
        pattern = r"```json\s+(.*?)\s+```"
        match = re.search(pattern, text)
        
        if match:
            return match.group(1)
        else:
            return text
        

    async def ainvoke(self, prompt):
        """
        Asynchronously invoke the model with a prompt.
        
        Args:
            prompt: Either a string or a list of message dictionaries
        """
        try:
            # If prompt is a string, convert it to a messages array
            if isinstance(prompt, str):
                messages = [{"role": "user", "content": prompt}]
            else:
                messages = prompt

            # Prepare the request data
            data = {
                "model": self.settings.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens
            }

            # Make the async API request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.settings.base_url,
                    headers=self.headers,
                    json=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        extracted_response = self.extract_response(result["choices"][0]["message"]["content"])
                        return extracted_response
                    else:
                        error_msg = f"OpenRouter Async API error: {response.status}, {await response.text()}"
                        logging.error(error_msg)
                        raise Exception(error_msg)

        except Exception as e:
            logging.error(f"OpenRouter async invoke error: {str(e)}")
            raise
