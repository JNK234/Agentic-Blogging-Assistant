"""
ABOUTME: Persona management service for writer voice consistency across content generation
ABOUTME: Provides configurable personas with extensible architecture for future persona types
"""
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Persona definition constants
NEURAFORGE_PERSONA_PROMPT = """WRITER PERSONA - NEURAFORGE:

You are writing for Neuraforge, a technical newsletter where complex concepts are explained with clarity and confidence. Your voice is that of a knowledgeable professional sharing insights with fellow practitioners.

WRITING STYLE:
- Use explanatory voice, not first person ("The algorithm processes..." not "I process...")
- Write with confidence and authority - make direct, clear statements
- Keep language professional, simple, and concise - avoid filler words
- Use concrete examples to illustrate abstract concepts
- Assume technical competence - don't over-explain fundamentals unless introducing new topics

TECHNICAL EXPLANATION APPROACH:
- Adapt depth based on content complexity - gauge from source material
- Don't define common technical terms unless rare or topic introduction
- Focus on clear conceptual understanding before diving into implementation
- Use progressive complexity when needed (simple concept → detailed mechanics)
- Include practical, implementable examples

CODE EXAMPLES:
- Include inline comments as required but not overly detailed
- Focus comments on non-obvious logic or key concepts
- Assume readers can read code - don't explain basic syntax
- Show practical, working examples with expected behavior

TRANSITIONS:
- Keep transitions professional, simple, and short
- Use clear, direct phrases ("The following demonstrates..." "This approach...")
- Avoid verbose connecting language
- Maintain logical flow between concepts

AUDIENCE ASSUMPTIONS:
- Technical professionals familiar with ML/programming fundamentals
- Can reference standard techniques without detailed explanation
- Understand production considerations and best practices
- Seeking deep understanding, not surface-level overviews

Remember: You are sharing knowledge to help fellow practitioners understand and implement concepts effectively. Be clear, be confident, be practical."""

class PersonaService:
    """
    Service for managing writer personas in the Agentic Blogging Assistant.
    
    Provides a centralized way to store and retrieve persona definitions
    for consistent voice and style across all content generation phases.
    """
    
    def __init__(self):
        """Initialize the persona service with default personas."""
        self.personas: Dict[str, Dict[str, str]] = {
            "neuraforge": {
                "name": "Neuraforge",
                "prompt": NEURAFORGE_PERSONA_PROMPT,
                "description": "Technical newsletter voice for sharing complex concepts clearly"
            }
        }
        logger.info("PersonaService initialized with default personas")
    
    def get_persona_prompt(self, persona_name: str = "neuraforge") -> str:
        """
        Retrieve the persona prompt by name.
        
        Args:
            persona_name: Name of the persona to retrieve
            
        Returns:
            The persona prompt text, or empty string if not found
        """
        persona = self.personas.get(persona_name)
        if not persona:
            logger.warning(f"Persona '{persona_name}' not found, returning empty prompt")
            return ""
        
        return persona.get("prompt", "")
    
    def add_persona(self, name: str, prompt: str, description: str) -> None:
        """
        Add a new persona to the service.
        
        Args:
            name: Unique name for the persona
            prompt: The persona instruction text
            description: Human-readable description of the persona
        """
        self.personas[name] = {
            "name": name,
            "prompt": prompt,
            "description": description
        }
        logger.info(f"Added new persona: {name}")
    
    def list_personas(self) -> Dict[str, str]:
        """
        Get a dictionary of available personas with their descriptions.
        
        Returns:
            Dictionary mapping persona names to their descriptions
        """
        return {name: data["description"] for name, data in self.personas.items()}
    
    def get_persona_info(self, persona_name: str) -> Optional[Dict[str, str]]:
        """
        Get complete information about a specific persona.
        
        Args:
            persona_name: Name of the persona
            
        Returns:
            Dictionary with persona information, or None if not found
        """
        return self.personas.get(persona_name)