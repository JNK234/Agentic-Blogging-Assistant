from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from .state import ContentAnalysis, Prerequisites, OutlineStructure, DifficultyLevel

# Initialize parsers
content_parser = PydanticOutputParser(pydantic_object=ContentAnalysis)
difficulty_parser = PydanticOutputParser(pydantic_object=DifficultyLevel)
prerequisites_parser = PydanticOutputParser(pydantic_object=Prerequisites)
outline_parser = PydanticOutputParser(pydantic_object=OutlineStructure)

# Content Analysis Prompt
CONTENT_ANALYSIS_PROMPT = PromptTemplate(
    template="""You are a technical content analyzer. Output must be valid JSON matching the format instructions.

{format_instructions}

Analyze the following technical content:

Notebook Content:
Text Content: {notebook_content_main_content}
Code Blocks: {notebook_content_code_segments}

Markdown Content:
Text Content: {markdown_content_main_content}
Code Blocks: {markdown_content_code_segments}

File Metadata:
Notebook: {notebook_content_metadata}
Markdown: {markdown_content_metadata}

Guidelines:
1. Use code blocks to identify technical concepts
2. Consider code complexity and outputs
3. Extract learning objectives from both text and code
4. Analyze relationships between notebook and markdown content
    """,
    input_variables=[
        "format_instructions",
        "notebook_content_main_content",
        "notebook_content_code_segments",
        "markdown_content_main_content",
        "markdown_content_code_segments",
        "notebook_content_metadata",
        "markdown_content_metadata",
    ],
)

# Difficulty Assessment Prompt
DIFFICULTY_ASSESSMENT_PROMPT = PromptTemplate(
    template="""You are a technical content analyzer. Output must be valid JSON matching the format instructions.

{format_instructions}

Evaluate the complexity of:

Technical Concepts:
{technical_concepts}

Complexity Indicators:
{complexity_indicators}

Guidelines:
- Consider concept interdependencies
- Evaluate technical depth
- Assess prerequisite knowledge needed
    """,
    input_variables=[
        "format_instructions",
        "technical_concepts",
        "complexity_indicators",
    ],
)

# Prerequisites Identification Prompt
PREREQUISITE_IDENTIFICATION_PROMPT = PromptTemplate(
    template="""You are a technical content analyzer. Output must be valid JSON matching the format instructions.

{format_instructions}

Identify prerequisites for:

Technical Concepts:
{technical_concepts}

Learning Objectives:
{learning_objectives}

Guidelines:
- List fundamental concepts needed
- Specify required tools and versions
- Include setup steps if necessary
    """,
    input_variables=[
        "format_instructions",
        "technical_concepts",
        "learning_objectives",
    ],
)

# Outline Structuring Prompt
OUTLINE_STRUCTURING_PROMPT = PromptTemplate(
    template="""You are a technical content analyzer. Output must be valid JSON matching the format instructions with required content from the input only.

{format_instructions}

Create outline structure for:

Main Topics:
{main_topics}

Difficulty Level:
{difficulty_level}

Prerequisites:
{prerequisites}

Guidelines:
- Ensure logical topic progression
- Include clear learning goals per section
- Estimate time requirements
- Add relevant subsections
- The entire output MUST be valid JSON according to format_instructions and nothing else. Do not include any conversational text or explanations or schemas.
    """,
    input_variables=[
        "format_instructions",
        "main_topics",
        "difficulty_level",
        "prerequisites",
    ],
)

# Final Generation Prompt
FINAL_GENERATION_PROMPT = PromptTemplate(
    template="""You are a technical content analyzer. Output must be valid JSON matching the format instructions.

Create a comprehensive outline using:

Title:
{title}

Difficulty Level:
{difficulty_level}

Prerequisites:
{prerequisites}

Outline Structure:
{outline_structure}
    """,
    input_variables=[
        "title",
        "difficulty_level",
        "prerequisites",
        "outline_structure",
    ],
)

# Export the prompts with their parsers
PROMPT_CONFIGS = {
    "content_analysis": {
        "prompt": CONTENT_ANALYSIS_PROMPT,
        "parser": content_parser
    },
    "difficulty_assessment": {
        "prompt": DIFFICULTY_ASSESSMENT_PROMPT,
        "parser": difficulty_parser
    },
    "prerequisites": {
        "prompt": PREREQUISITE_IDENTIFICATION_PROMPT,
        "parser": prerequisites_parser
    },
    "outline_structure": {
        "prompt": OUTLINE_STRUCTURING_PROMPT,
        "parser": outline_parser
    },
    "final_generation": {
        "prompt": FINAL_GENERATION_PROMPT,
        "parser": None  # No parser needed for markdown output
    }
}
