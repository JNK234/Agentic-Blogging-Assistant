from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from .state import ContentAnalysis, Prerequisites, OutlineStructure, DifficultyLevel, FinalOutline

# Initialize parsers
content_parser = PydanticOutputParser(pydantic_object=ContentAnalysis)
difficulty_parser = PydanticOutputParser(pydantic_object=DifficultyLevel)
prerequisites_parser = PydanticOutputParser(pydantic_object=Prerequisites)
outline_parser = PydanticOutputParser(pydantic_object=OutlineStructure)
final_parser = PydanticOutputParser(pydantic_object=FinalOutline)

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

Section Headers (from markdown):
{markdown_section_headers}

Guidelines:
1. Main Topics: Extract the main topics covered in both notebook and markdown content
2. Technical Concepts: Identify specific technical concepts from code blocks and explanations
3. Complexity Indicators: Look for:
   - Advanced programming patterns
   - Complex algorithms or data structures
   - Error handling and edge cases
   - Performance considerations
4. Learning Objectives: Extract or infer:
   - Skills to be learned
   - Concepts to be mastered
   - Practical applications
   - Expected outcomes
5. Section Structure: Consider the existing section headers from the markdown content
   - Use them as guidance for the blog structure
   - Maintain the hierarchical relationships between topics
   - Incorporate the logical flow of the original content

Your output MUST be a valid JSON object that includes ALL of the following:
- main_topics: List of primary topics covered
- technical_concepts: List of specific technical concepts
- complexity_indicators: List of elements indicating complexity
- learning_objectives: List of clear learning goals
- section_structure: List of section headers with their hierarchy, representing a logical content structure based on the original headers

Ensure each list is complete and properly formatted according to the schema. If a list is empty, return an empty list [].
    """,
    input_variables=[
        "format_instructions",
        "notebook_content_main_content",
        "notebook_content_code_segments",
        "markdown_content_main_content",
        "markdown_content_code_segments",
        "notebook_content_metadata",
        "markdown_content_metadata",
        "markdown_section_headers",
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

Source Document Section Structure:
{section_structure}

Difficulty Level:
{difficulty_level}

Prerequisites:
{prerequisites}

Guidelines:
- Use the source document section structure as a reference
- Ensure logical topic progression
- Include clear learning goals per section
- Estimate time requirements
- Add relevant subsections
- The entire output MUST be valid JSON according to format_instructions and nothing else. Do not include any conversational text or explanations or schemas.
    """,
    input_variables=[
        "format_instructions",
        "main_topics",
        "section_structure",
        "difficulty_level",
        "prerequisites",
    ],
)

# Final Generation Prompt
FINAL_GENERATION_PROMPT = PromptTemplate(
    template="""You are a technical content analyzer. Output must be valid JSON matching the format instructions.

{format_instructions}

Create a comprehensive outline using:

Title:
{title}

Difficulty Level:
{difficulty_level}

Prerequisites:
{prerequisites}

Outline Structure:
{outline_structure}

Guidelines:
- Output must be valid JSON according to format_instructions
- Include all sections and content from the outline structure
- Maintain the hierarchical organization
- Preserve all learning goals and time estimates
- Keep the JSON structure clean and properly formatted
- Provide only the content in required format and nothing else. Do not return any other text or schemas or explanations.
    """,
    input_variables=[
        "format_instructions",
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
        "parser": final_parser
    }
}
