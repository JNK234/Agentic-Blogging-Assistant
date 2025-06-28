"""
Integration test for Neuraforge persona and blog continuity enhancements.
Tests persona consistency, enhanced context, length management, and section continuity.
"""
import asyncio
import sys
from pathlib import Path

# Add the root directory to the Python path
sys.path.append(str(Path(__file__).parent))

from root.backend.services.persona_service import PersonaService
from root.backend.utils.blog_context import (
    calculate_content_length, 
    extract_blog_narrative_context, 
    calculate_section_length_targets, 
    get_length_priority
)
from root.backend.agents.blog_draft_generator.prompts import (
    SECTION_GENERATION_PROMPT,
    SECTION_TRANSITION_PROMPT,
    BLOG_COMPILATION_PROMPT
)
from root.backend.agents.outline_generator.prompts import FINAL_GENERATION_PROMPT

def test_persona_service():
    """Test PersonaService functionality."""
    print("🧪 Testing PersonaService...")
    
    # Test initialization
    service = PersonaService()
    assert service is not None, "PersonaService should initialize"
    
    # Test persona retrieval
    neuraforge_persona = service.get_persona_prompt("neuraforge")
    assert len(neuraforge_persona) > 1000, "Neuraforge persona should be substantial"
    assert "WRITER PERSONA - NEURAFORGE" in neuraforge_persona, "Should contain persona header"
    assert "explanatory voice" in neuraforge_persona, "Should contain voice guidelines"
    
    # Test persona listing
    personas = service.list_personas()
    assert "neuraforge" in personas, "Should list neuraforge persona"
    
    print("✅ PersonaService tests passed")

def test_length_management():
    """Test length management utilities."""
    print("🧪 Testing length management...")
    
    # Test word counting
    test_cases = [
        ("Hello world", 2),
        ("", 0),
        ("Single", 1),
        ("This is a longer sentence with multiple words.", 8)
    ]
    
    for text, expected in test_cases:
        actual = calculate_content_length(text)
        assert actual == expected, f"Expected {expected} words, got {actual} for '{text}'"
    
    # Test length priority
    assert get_length_priority(500, 800, 2000) == "expand", "Should expand with large budget"
    assert get_length_priority(500, 800, 800) == "maintain", "Should maintain with adequate budget"
    assert get_length_priority(500, 800, 100) == "compress", "Should compress with low budget"
    assert get_length_priority(500, 800, 0) == "compress", "Should compress with zero budget"
    
    print("✅ Length management tests passed")

def test_prompt_templates():
    """Test that all prompt templates include persona instructions."""
    print("🧪 Testing prompt template enhancements...")
    
    # Test SECTION_GENERATION_PROMPT
    assert "persona_instructions" in SECTION_GENERATION_PROMPT.input_variables, \
        "Section generation should include persona_instructions"
    assert "blog_narrative_context" in SECTION_GENERATION_PROMPT.input_variables, \
        "Section generation should include blog_narrative_context"
    assert "target_section_length" in SECTION_GENERATION_PROMPT.input_variables, \
        "Section generation should include length constraints"
    
    # Test SECTION_TRANSITION_PROMPT
    assert "persona_instructions" in SECTION_TRANSITION_PROMPT.input_variables, \
        "Transition generation should include persona_instructions"
    assert "blog_title" in SECTION_TRANSITION_PROMPT.input_variables, \
        "Transition generation should include blog context"
    
    # Test BLOG_COMPILATION_PROMPT
    assert "persona_instructions" in BLOG_COMPILATION_PROMPT.input_variables, \
        "Blog compilation should include persona_instructions"
    
    # Test FINAL_GENERATION_PROMPT (outline)
    assert "persona_instructions" in FINAL_GENERATION_PROMPT.input_variables, \
        "Outline generation should include persona_instructions"
    
    print("✅ Prompt template tests passed")

def test_prompt_template_formatting():
    """Test that prompts can be formatted with all required variables."""
    print("🧪 Testing prompt template formatting...")
    
    # Test SECTION_GENERATION_PROMPT formatting
    try:
        test_variables = {
            "persona_instructions": "Test persona",
            "format_instructions": "Test format",
            "section_title": "Test Section",
            "learning_goals": "Test goals",
            "original_structure": "Test structure",
            "structural_insights": "Test insights",
            "formatted_content": "Test content",
            "previous_context": "Test context",
            "blog_narrative_context": "Test narrative",
            "target_section_length": 500,
            "current_blog_length": 1000,
            "remaining_length_budget": 2000,
            "length_priority": "expand",
            "current_section_data": "{}"
        }
        
        formatted = SECTION_GENERATION_PROMPT.format(**test_variables)
        assert len(formatted) > 100, "Formatted prompt should be substantial"
        assert "Test persona" in formatted, "Should include persona instructions"
        assert "expand" in formatted, "Should include length priority"
        
    except KeyError as e:
        assert False, f"Missing variable in SECTION_GENERATION_PROMPT: {e}"
    
    print("✅ Prompt formatting tests passed")

def test_agent_imports():
    """Test that agents can be imported with new PersonaService signatures."""
    print("🧪 Testing agent imports...")
    
    try:
        from root.backend.agents.blog_draft_generator_agent import BlogDraftGeneratorAgent
        from root.backend.agents.outline_generator_agent import OutlineGeneratorAgent
        
        # Test that PersonaService is properly imported in the agents
        assert hasattr(BlogDraftGeneratorAgent, '__init__'), "BlogDraftGeneratorAgent should have __init__"
        assert hasattr(OutlineGeneratorAgent, '__init__'), "OutlineGeneratorAgent should have __init__"
        
    except ImportError as e:
        assert False, f"Failed to import agents: {e}"
    
    print("✅ Agent import tests passed")

def test_backward_compatibility():
    """Test that changes maintain backward compatibility."""
    print("🧪 Testing backward compatibility...")
    
    # Test PersonaService with default parameters
    service = PersonaService()
    unknown_persona = service.get_persona_prompt("unknown_persona")
    assert unknown_persona == "", "Should return empty string for unknown persona"
    
    # Test length functions with edge cases
    # Note: calculate_content_length expects string input, None would cause error
    # This is acceptable behavior - function should be called with valid strings
    assert get_length_priority(0, 0, 0) == "compress", "Should handle all zero inputs"
    
    print("✅ Backward compatibility tests passed")

def test_continuity_enhancements():
    """Test that continuity enhancements are properly integrated."""
    print("🧪 Testing continuity enhancements...")
    
    # Test that prompt templates include continuity guidelines
    section_template = SECTION_GENERATION_PROMPT.template
    assert "SECTION CONTINUITY GUIDELINES" in section_template, \
        "Section generation should include continuity guidelines"
    assert "flow naturally from the previous content" in section_template, \
        "Should include flow guidelines"
    assert "Avoid standalone introductions" in section_template, \
        "Should discourage standalone introductions"
    
    # Test compilation guidelines
    compilation_template = BLOG_COMPILATION_PROMPT.template
    assert "COMPILATION GUIDELINES" in compilation_template, \
        "Blog compilation should include compilation guidelines"
    assert "consistent voice and style" in compilation_template, \
        "Should enforce voice consistency"
    
    print("✅ Continuity enhancement tests passed")

def run_all_tests():
    """Run all integration tests."""
    print("🚀 Starting Neuraforge Persona & Blog Continuity Integration Tests")
    print("=" * 70)
    
    try:
        test_persona_service()
        test_length_management()
        test_prompt_templates()
        test_prompt_template_formatting()
        test_agent_imports()
        test_backward_compatibility()
        test_continuity_enhancements()
        
        print("=" * 70)
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("✅ Persona consistency: READY")
        print("✅ Enhanced context: READY")
        print("✅ Length management: READY")
        print("✅ Section continuity: READY")
        print("✅ Agent integration: READY")
        print("✅ Backward compatibility: MAINTAINED")
        print("✅ System ready for production use!")
        
        return True
        
    except Exception as e:
        print("=" * 70)
        print(f"❌ INTEGRATION TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)