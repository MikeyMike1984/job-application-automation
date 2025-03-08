# app/services/llm/provider_simple.py
from abc import ABC, abstractmethod
import json
import httpx
from typing import Dict, Any, Optional, List, Union
import logging

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def generate(
        self, 
        prompt: str, 
        system_message: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate text from the LLM"""
        pass
    
    @abstractmethod
    async def generate_structured(
        self, 
        prompt: str, 
        output_schema: Dict[str, Any],
        system_message: Optional[str] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """Generate structured data from the LLM"""
        pass

class OllamaProvider(LLMProvider):
    """Implementation for ollama"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "mistral:instruct"):
        self.base_url = base_url
        self.model = model
        
    async def generate(
        self, 
        prompt: str, 
        system_message: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate text from ollama"""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": temperature,
                    "system": system_message if system_message else "",
                    "options": {},
                    "stream": False  # Explicitly disable streaming
                }
                
                if max_tokens:
                    payload["options"]["num_predict"] = max_tokens
                    
                logger.info(f"Generating text with {self.model}")
                response = await client.post(
                    f"{self.base_url}/api/generate", 
                    json=payload,
                    timeout=120.0  # Increased timeout for longer responses
                )
                response.raise_for_status()
                
                # Proper error handling for JSON parsing
                try:
                    result = response.json()
                    return result.get("response", "No response generated")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Ollama response as JSON: {str(e)}")
                    # Try to extract text content directly as fallback
                    return response.text
        except Exception as e:
            logger.error(f"Error generating text with Ollama: {str(e)}")
            return f"Error generating text: {str(e)}"
    
    async def generate_structured(
        self, 
        prompt: str, 
        output_schema: Dict[str, Any],
        system_message: Optional[str] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """Generate structured JSON data from ollama"""
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
            # Lower temperature for more consistent JSON format
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
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        # If JSON is invalid, try to create a simple default response
                        logger.warning("Could not parse JSON from response, using fallback")
                        if "skills" in output_schema.get("properties", {}):
                            return {"skills": []}
                        elif "education" in output_schema.get("properties", {}):
                            return {"education": []}
                        elif "keywords" in output_schema.get("properties", {}):
                            return {"keywords": []}
                        elif "years" in output_schema.get("properties", {}):
                            return {"years": None}
                        elif "level" in output_schema.get("properties", {}):
                            return {"level": "mid"}
                        else:
                            return {"error": "Failed to parse JSON", "raw_response": response_text}
                else:
                    logger.warning("No JSON object found in response")
                    # Return an empty default structure based on schema
                    if "skills" in output_schema.get("properties", {}):
                        return {"skills": []}
                    elif "education" in output_schema.get("properties", {}):
                        return {"education": []}
                    elif "keywords" in output_schema.get("properties", {}):
                        return {"keywords": []}
                    elif "years" in output_schema.get("properties", {}):
                        return {"years": None}
                    elif "level" in output_schema.get("properties", {}):
                        return {"level": "mid"}
                    else:
                        return {"error": "No JSON object found in response", "raw_response": response_text}
            except Exception as e:
                logger.error(f"Error processing JSON: {str(e)}")
                return {"error": "Error processing JSON response", "raw_response": response_text}
        except Exception as e:
            logger.error(f"Error in structured generation: {str(e)}")
            return {"error": f"Error in structured generation: {str(e)}"}

# Factory class to get the appropriate provider
class LLMProviderFactory:
    @staticmethod
    def get_provider(provider_type: str, **kwargs) -> LLMProvider:
        if provider_type.lower() == "ollama":
            return OllamaProvider(**kwargs)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")