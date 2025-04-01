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
    template="""You are a highly skilled technical writer and content structurer. Your task is to create a detailed blog post outline based on the provided analysis and guidelines.
Output MUST be valid JSON matching the format instructions precisely.

{format_instructions}

**Input Information:**

1.  **Main Topics Identified:**
    {main_topics}

2.  **Source Document Section Structure (for reference):**
    {section_structure}

3.  **Identified Technical Concepts:**
    {technical_concepts}

4.  **Assessed Difficulty Level:**
    {difficulty_level}

5.  **Identified Prerequisites:**
    {prerequisites}

6.  **User Provided Guidelines:**
    {user_guidelines}

**Task:** Create a structured outline (`OutlineStructure`) with sections (`OutlineSection`).

**Guidelines for Outline Creation:**

1.  **Logical Flow:** Ensure a clear and logical progression of topics, using `main_topics` and `section_structure` as primary guides.
2.  **Section Content:** For each `OutlineSection`:
    *   Define a clear `title`.
    *   List relevant `subsections` (as strings).
    *   Specify concise `learning_goals`.
    *   Optionally provide an `estimated_time`.
3.  **Code Inclusion (`include_code` flag):**
    *   **Priority:** Strictly follow any explicit instructions in `user_guidelines` regarding code inclusion/exclusion for specific sections.
    *   **Source Analysis:** Examine `technical_concepts` and `section_structure`. If the source document clearly contains relevant code examples for a section's topic, lean towards setting `include_code: true`.
    *   **Necessity:** Set `include_code: true` only if code significantly enhances understanding, demonstrates a crucial practical implementation, or is explicitly requested/present in source. Avoid code for purely theoretical or introductory sections unless specified otherwise.
    *   **Default:** If unsure, default to `include_code: false`.
4.  **Subpoint Limits (`max_subpoints`):**
    *   Aim for a maximum of 4 `subsections` per section by default (`max_subpoints: 4`).
    *   If `include_code` is `true` for a section, consider reducing the limit slightly (e.g., `max_subpoints: 3`) to manage complexity.
    *   Adhere to any limits specified in `user_guidelines`.
5.  **Code Example Limits (`max_code_examples`):**
    *   If `include_code` is `true`, suggest a default maximum of 1-2 code examples (`max_code_examples: 1` or `2`).
    *   Adjust based on `user_guidelines` if provided.
6.  **De-duplication:** Review the overall outline. Ensure sections and subsections cover distinct topics. Avoid proposing redundant content or repetitive code examples suggested by the `technical_concepts` or `section_structure`.
7.  **Focus:** Structure only the technical core content derived from the source and analysis. Do NOT create generic 'Introduction' or 'Conclusion' sections for the overall blog post here; focus on the technical flow.
8.  **Output Format:** The entire output MUST be a single, valid JSON object conforming exactly to the `OutlineStructure` schema provided in `format_instructions`. No extra text, explanations, or markdown formatting outside the JSON structure.

Generate the `OutlineStructure` JSON object now.
    """,
    input_variables=[
        "format_instructions",
        "main_topics",
        "section_structure",
        "difficulty_level",
        "prerequisites",
        "user_guidelines", # Added
        "technical_concepts", # Added
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
