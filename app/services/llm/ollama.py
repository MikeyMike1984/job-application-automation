# app/services/llm/ollama.py
import json
import logging
from typing import Dict, Any, Optional, List, Union
import httpx
import os
from dotenv import load_dotenv

from app.services.llm.provider import LLMProvider

load_dotenv()

logger = logging.getLogger(__name__)

class OllamaProvider(LLMProvider):
    """Implementation for Ollama API."""
    
    def __init__(
        self, 
        base_url: Optional[str] = None,
        model: str = "llama3:8b-instruct"
    ):
        """Initialize Ollama provider.
        
        Args:
            base_url: Base URL for Ollama API. If not provided, uses OLLAMA_BASE_URL from environment.
            model: Model to use.
        """
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model
        
    async def generate(
        self, 
        prompt: str, 
        system_message: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate text from Ollama.
        
        Args:
            prompt: The prompt to send to Ollama
            system_message: Optional system message
            temperature: Controls randomness (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text
            
        Raises:
            Exception: If API call fails
        """
        async with httpx.AsyncClient() as client:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "temperature": temperature,
                "system": system_message if system_message else "",
                "options": {}
            }
            
            if max_tokens:
                payload["options"]["num_predict"] = max_tokens
                
            try:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=60.0
                )
                response.raise_for_status()
                
                return response.json()["response"]
            except Exception as e:
                logger.error(f"Ollama API error: {str(e)}")
                raise
    
    async def generate_structured(
        self, 
        prompt: str, 
        output_schema: Dict[str, Any],
        system_message: Optional[str] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """Generate structured data from Ollama.
        
        Args:
            prompt: The prompt to send to Ollama
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
        
        # Try up to 3 times to get valid JSON
        max_attempts = 3
        
        for attempt in range(max_attempts):
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
                        logger.warning(f"No JSON object found in response (attempt {attempt+1}/{max_attempts})")
                        if attempt == max_attempts - 1:
                            return {"error": "No JSON object found in response after multiple attempts", "raw_response": response_text}
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON (attempt {attempt+1}/{max_attempts}): {str(e)}")
                    if attempt == max_attempts - 1:
                        return {"error": "Failed to parse JSON from LLM response", "raw_response": response_text}
            except Exception as e:
                logger.error(f"Error in structured generation: {str(e)}")
                if attempt == max_attempts - 1:
                    raise
        
        # This should not be reached due to the returns in the loop
        return {"error": "Failed to generate structured response after multiple attempts"}