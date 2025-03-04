# app/services/llm/openai.py
import json
import logging
from typing import Dict, Any, Optional, List, Union
import httpx
import os
from dotenv import load_dotenv

from app.services.llm.provider import LLMProvider

load_dotenv()

logger = logging.getLogger(__name__)

class OpenAIProvider(LLMProvider):
    """Implementation for OpenAI API."""
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        model: str = "gpt-4o",
        api_base: Optional[str] = None
    ):
        """Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY from environment.
            model: Model to use.
            api_base: Base URL for API. If not provided, uses default OpenAI URL.
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required.")
        
        self.model = model
        self.api_base = api_base or "https://api.openai.com/v1"
        
    async def generate(
        self, 
        prompt: str, 
        system_message: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate text from OpenAI.
        
        Args:
            prompt: The prompt to send to OpenAI
            system_message: Optional system message
            temperature: Controls randomness (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text
            
        Raises:
            Exception: If API call fails
        """
        async with httpx.AsyncClient() as client:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            messages = []
            if system_message:
                messages.append({"role": "system", "content": system_message})
            
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
                
            try:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"OpenAI API error: {str(e)}")
                raise
    
    async def generate_structured(
        self, 
        prompt: str, 
        output_schema: Dict[str, Any],
        system_message: Optional[str] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """Generate structured data from OpenAI.
        
        Args:
            prompt: The prompt to send to OpenAI
            output_schema: JSON schema defining the expected output structure
            system_message: Optional system message
            temperature: Controls randomness (0.0 to 1.0)
            
        Returns:
            Structured data according to the output schema
            
        Raises:
            Exception: If API call fails or JSON parsing fails
        """
        # Format the prompt to include the schema requirements
        formatted_prompt = f"""
        {prompt}
        
        You must respond ONLY with a valid JSON object matching this schema:
        {json.dumps(output_schema, indent=2)}
        
        Response:
        """
        
        # Add JSON format guidance to system message
        if system_message:
            enhanced_system = f"{system_message}\nYou must respond with valid JSON only, no other text."
        else:
            enhanced_system = "You must respond with valid JSON only, no other text."
        
        try:
            # Generate with low temperature for more consistent JSON
            response_text = await self.generate(
                formatted_prompt, 
                system_message=enhanced_system,
                temperature=temperature
            )
            
            # Extract and parse JSON from response
            try:
                # Find JSON object in response (in case model adds extra text)
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    return json.loads(json_str)
                else:
                    raise ValueError("No JSON object found in response")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from OpenAI response: {str(e)}")
                return {
                    "error": "Failed to parse JSON from LLM response", 
                    "raw_response": response_text
                }
        except Exception as e:
            logger.error(f"Error in structured generation: {str(e)}")
            raise