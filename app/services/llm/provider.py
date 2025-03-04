# app/services/llm/provider.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
import logging

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(
        self, 
        prompt: str, 
        system_message: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate text from the LLM.
        
        Args:
            prompt: The prompt to send to the LLM
            system_message: Optional system message to guide the LLM's behavior
            temperature: Controls randomness (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text
        """
        pass
    
    @abstractmethod
    async def generate_structured(
        self, 
        prompt: str, 
        output_schema: Dict[str, Any],
        system_message: Optional[str] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """Generate structured data from the LLM.
        
        Args:
            prompt: The prompt to send to the LLM
            output_schema: JSON schema defining the expected output structure
            system_message: Optional system message to guide the LLM's behavior
            temperature: Controls randomness (0.0 to 1.0)
            
        Returns:
            Structured data according to the output schema
        """
        pass

class LLMProviderFactory:
    """Factory for creating LLM provider instances."""
    
    @staticmethod
    def get_provider(provider_type: str, **kwargs) -> LLMProvider:
        """Get LLM provider instance based on provider type.
        
        Args:
            provider_type: Type of provider ("openai" or "ollama")
            **kwargs: Additional arguments for provider initialization
            
        Returns:
            LLM provider instance
            
        Raises:
            ValueError: If provider_type is unknown
        """
        if provider_type.lower() == "openai":
            from app.services.llm.openai import OpenAIProvider
            return OpenAIProvider(**kwargs)
        elif provider_type.lower() == "ollama":
            from app.services.llm.ollama import OllamaProvider
            return OllamaProvider(**kwargs)
        else:
            raise ValueError(f"Unknown LLM provider type: {provider_type}")