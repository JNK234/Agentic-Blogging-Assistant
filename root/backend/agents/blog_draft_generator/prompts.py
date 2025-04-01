from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from root.backend.agents.blog_draft_generator.state import ContentReference, CodeExample, DraftSection

# Initialize parsers
content_mapping_parser = PydanticOutputParser(pydantic_object=ContentReference)
section_generation_parser = PydanticOutputParser(pydantic_object=DraftSection)
code_example_parser = PydanticOutputParser(pydantic_object=CodeExample)

# Content Mapping Prompt
CONTENT_MAPPING_PROMPT = PromptTemplate(
    template="""You are a technical content analyst. Your task is to identify content that is relevant to a specific section of a technical blog.

{format_instructions}

SECTION INFORMATION:
Title: {section_title}
Learning Goals: {learning_goals}

CONTENT TO ANALYZE:
{combined_content}

TASK:
1. Identify the most relevant paragraphs, sentences, and code examples for this section
2. Focus on content that directly addresses the learning goals
3. Include technical explanations, code examples, and implementation details
4. Analyze the content semantically, not just by keyword matching
5. Categorize content by type (concept, example, implementation, best practice)

Your output MUST be a valid JSON object that includes:
- content: The relevant text or code snippet
- source_type: The type of source ("notebook", "markdown", "code")
- relevance_score: A score from 0.0 to 1.0 indicating relevance
- category: One of "concept", "example", "implementation", "best_practice"
- source_location: Optional location information
    """,
    input_variables=[
        "format_instructions",
        "section_title",
        "learning_goals",
        "combined_content",
    ],
)

# Section Generation Prompt
SECTION_GENERATION_PROMPT = PromptTemplate(
    template="""You are an expert technical blog writer. Generate a comprehensive blog section based on the following information:

{format_instructions}

SECTION INFORMATION (From Outline):
Title: {section_title}
Learning Goals: {learning_goals}
Constraints: {current_section_data} # Contains include_code, max_subpoints, max_code_examples

ORIGINAL DOCUMENT STRUCTURE (For Reference):
{original_structure}

STRUCTURAL INSIGHTS:
{structural_insights}

RELEVANT CONTENT:
{formatted_content}

PREVIOUS SECTION CONTEXT:
{previous_context}

TASK:
Write a comprehensive and engaging blog section that adheres strictly to the provided constraints:

**Constraints to Follow:**
- **Code Inclusion:** Refer to `current_section_data.include_code`. If `false`, DO NOT include any code examples. If `true`, proceed with code generation.
- **Subpoint Limit:** The number of distinct sub-topics or points discussed should not exceed `current_section_data.max_subpoints`. Be concise if the limit is low.
- **Code Example Limit:** If `include_code` is `true`, generate a maximum of `current_section_data.max_code_examples` relevant code snippets. Choose the most illustrative examples.

**TASK:**
Write a comprehensive and engaging blog section that:

1. Structure:
   - Adhere to the `max_subpoints` constraint from `current_section_data`.
   - Follow the original document structure where applicable.
   - Maintain the hierarchical relationships between topics.
   - Start with a clear technical introduction *specific to this section's topic*, building upon the previous context if available.
   - Break down complex concepts into digestible parts
   - Build concepts progressively
   - Conclude by reinforcing the section's key learning goals or summarizing the main technical points covered *in this section*. Avoid generic summaries.

2. Content Preservation:
   - Prioritize using content from the original document
   - Maintain the original explanations and examples where possible
   - Preserve the logical flow of the original content
   - Use the original section headers as a guide

3. Technical Depth:
   - Use appropriate technical terminology and jargon
   - Explain advanced concepts with precision
   - Include relevant technical specifications
   - Reference industry standards where applicable

4. Code Examples:
   - Provide well-commented code snippets
   - Explain each significant code block
   - Include setup and configuration details
   - Show best practices in implementation.
   - **IMPORTANT**: Only include code examples if `current_section_data.include_code` is `true`. Limit the number of examples to `current_section_data.max_code_examples`.

5. Implementation Focus:
   - Include practical implementation details.
   - Highlight common pitfalls and solutions
   - Discuss performance considerations
   - Address security implications if relevant

6. Educational Style:
   - Use professional technical tone
   - Include callouts for important points
   - Add technical tips and tricks
   - Reference relevant documentation

Format Guidelines:
- Use markdown formatting
- Include code blocks with language specification
- Use tables for comparing approaches
- Add bullet points for key concepts
- Include technical notes and warnings
- Reference external documentation where relevant

Ensure the content is:
- Technically accurate
- Well-structured
- Practical and implementable
- Suitable for professional developers
- Consistent with the original document's organization
    """,
    input_variables=[
        "format_instructions",
        "section_title",
        "learning_goals",
        "original_structure",
        "structural_insights",
        "formatted_content",
        "previous_context",
        "current_section_data", # Added
    ],
)

# Content Enhancement Prompt
CONTENT_ENHANCEMENT_PROMPT = PromptTemplate(
    template="""You are an expert technical editor. Enhance the following blog section to make it more comprehensive, technically accurate, and engaging:

{format_instructions}

SECTION INFORMATION:
Title: {section_title}
Learning Goals: {learning_goals}

ORIGINAL DOCUMENT STRUCTURE:
{original_structure}

STRUCTURAL INSIGHTS:
{structural_insights}

CURRENT CONTENT:
{existing_content}

ADDITIONAL RELEVANT CONTENT:
{formatted_content}

TASK:
Enhance the existing content by:
1. Following the original document structure where applicable
2. Preserving the logical flow of the original content
3. Adding more technical depth where needed
4. Improving code examples with better comments and explanations
5. Adding practical implementation details
6. Clarifying complex concepts
7. Adding best practices and tips
8. Ensuring all learning goals are thoroughly addressed

IMPORTANT:
- Maintain the original structure and flow
- Prioritize using content from the original document
- Keep the technical accuracy high
- Ensure code examples are well-explained
- Add concrete examples for abstract concepts
- Reinforce the section's key learning goals or summarize the main technical points covered *in this section*. Avoid generic summaries or takeaways.
- Preserve the hierarchical relationships between topics

FORMAT:
- Use markdown formatting
- Include code blocks with appropriate syntax highlighting
- Use headings, lists, and emphasis appropriately
- Keep paragraphs concise and focused
    """,
    input_variables=[
        "format_instructions",
        "section_title",
        "learning_goals",
        "original_structure",
        "structural_insights",
        "existing_content",
        "formatted_content",
    ],
)

# Code Example Extraction Prompt
CODE_EXAMPLE_EXTRACTION_PROMPT = PromptTemplate(
    template="""You are an expert code reviewer. Analyze the following code example and its context:

{format_instructions}

CODE:
```{language}
{code}
```

CONTEXT:
{context}

TASK:
1. Provide a concise description of what this code does
2. Identify any improvements that could be made
3. Add explanatory comments if needed

Your output MUST be a valid JSON object that includes:
- code: The code with any improvements and better comments
- language: The programming language
- description: Brief description of the code
- explanation: Detailed explanation of how the code works
- output: Expected output (if applicable)
- source_location: Where this code appears in the document
    """,
    input_variables=[
        "format_instructions",
        "language",
        "code",
        "context",
    ],
)

# Quality Validation Prompt (Revised for Robustness)
QUALITY_VALIDATION_PROMPT = PromptTemplate(
    template="""You are an expert content quality assessor. Evaluate the following blog section based ONLY on the provided CONTENT.

SECTION INFORMATION:
Title: {section_title}
Learning Goals: {learning_goals}

CONTENT TO EVALUATE:
--- START CONTENT ---
{section_content}
--- END CONTENT ---

TASK:
Evaluate the content based *strictly* on the following criteria. Provide a score between 0.0 and 1.0 for each metric, where 0.0 is poor and 1.0 is excellent.
1. Completeness: Does the CONTENT cover all stated Learning Goals? (Score: 0.0-1.0)
2. Technical Accuracy: Is the technical information in the CONTENT correct and precise? (Score: 0.0-1.0)
3. Clarity: Is the CONTENT easy to understand, well-explained, and unambiguous? (Score: 0.0-1.0)
4. Code Quality: Are code examples within the CONTENT well-written, correctly formatted, and adequately explained? (Score: 0.0-1.0, use 0.0 if no code exists)
5. Engagement: Is the CONTENT engaging and likely to hold a technical reader's interest? (Score: 0.0-1.0)
6. Structural Consistency: Does the CONTENT maintain a logical flow and organization consistent with typical technical documentation or the implied structure? (Score: 0.0-1.0)

OUTPUT REQUIREMENTS:
Your response MUST be **ONLY** a single, valid JSON object containing the following keys and value types. Do NOT include any text before or after the JSON object.

{{
    "completeness": float,              # Score 0.0 to 1.0
    "technical_accuracy": float,      # Score 0.0 to 1.0
    "clarity": float,                 # Score 0.0 to 1.0
    "code_quality": float,            # Score 0.0 to 1.0 (use 0.0 if no code)
    "engagement": float,              # Score 0.0 to 1.0
    "structural_consistency": float,  # Score 0.0 to 1.0
    "overall_score": float,           # Calculated average of the above scores (0.0 to 1.0)
    "improvement_needed": boolean,      # MUST be true or false (lowercase). True if overall_score < 0.8, false otherwise.
    "improvement_suggestions": [string] # MUST be a JSON list of specific, actionable suggestions based on low scores. Use an empty list [] if no improvements are needed.
}}

**IMPORTANT:** Ensure ALL keys are present in the JSON. Scores MUST be numbers between 0.0 and 1.0. `improvement_needed` MUST be `true` or `false`. `improvement_suggestions` MUST be a list of strings (can be empty `[]`). Double-check the output is valid JSON.
    """,
    input_variables=[
        "section_title",
        "learning_goals",
        "section_content",
    ],
)

# Feedback Incorporation Prompt
FEEDBACK_INCORPORATION_PROMPT = PromptTemplate(
    template="""You are an expert technical editor. Revise the following blog section based on feedback:

SECTION INFORMATION:
Title: {section_title}
Learning Goals: {learning_goals}

CURRENT CONTENT:
{existing_content}

FEEDBACK:
{feedback}

TASK:
Revise the content to address all feedback points while:
1. Maintaining the original structure and flow
2. Preserving technical accuracy
3. Enhancing clarity and engagement
4. Improving code examples if needed
5. Ensuring all learning goals are thoroughly addressed
6. Preserving the hierarchical relationships between topics
7. Maintaining consistency with the original document's organization

IMPORTANT:
- If the feedback mentions structural consistency, ensure your revisions align with the original document structure
- Preserve the logical flow of the original content
- Maintain the hierarchical relationships between topics
- Use the original section headers as a guide where applicable

FORMAT:
- Use markdown formatting
- Include code blocks with appropriate syntax highlighting
- Use headings, lists, and emphasis appropriately
- Keep paragraphs concise and focused
    """,
    input_variables=[
        "section_title",
        "learning_goals",
        "existing_content",
        "feedback",
    ],
)

# Section Transition Prompt
SECTION_TRANSITION_PROMPT = PromptTemplate(
    template="""You are an expert technical writer. Create a smooth transition between these blog sections:

CURRENT SECTION:
Title: {current_section_title}
Ending: {current_section_ending}

NEXT SECTION:
Title: {next_section_title}

TASK:
Write a brief transition paragraph (2-3 sentences) that:
1. Summarizes the key points from the current section
2. Creates a logical bridge to the next section
3. Maintains the technical and educational tone
    """,
    input_variables=[
        "current_section_title",
        "current_section_ending",
        "next_section_title",
    ],
)

# Final Blog Compilation Prompt
BLOG_COMPILATION_PROMPT = PromptTemplate(
    template="""You are an expert technical editor. Compile the following blog sections into a cohesive final blog post:

BLOG TITLE: {blog_title}
DIFFICULTY LEVEL: {difficulty_level}
PREREQUISITES: {prerequisites}

ORIGINAL DOCUMENT STRUCTURE:
{original_structure}

SECTIONS:
{sections_content}

TRANSITIONS:
{transitions}

TASK:
Compile a complete blog post that:
1. Starts with an engaging introduction
2. Includes all sections in the correct order
3. Uses transitions between sections
4. Ends with a comprehensive conclusion
5. Maintains consistent formatting and style throughout
6. Preserves the hierarchical relationships between topics
7. Maintains the logical flow of the original content

IMPORTANT:
- Follow the original document structure where applicable
- Preserve the structure of each section as provided
- Maintain the hierarchical relationships between topics
- Ensure the blog follows a logical progression that aligns with the original document's organization
- Use the transitions to create smooth connections between sections while preserving the original flow

FORMAT:
- Use markdown formatting
- Include a table of contents
- Ensure consistent heading levels
- Maintain code formatting
- Include appropriate metadata
    """,
    input_variables=[
        "blog_title",
        "difficulty_level",
        "prerequisites",
        "original_structure",
        "sections_content",
        "transitions",
    ],
)

# Content Validation Prompt (used in semantic_content_mapper)
CONTENT_VALIDATION_PROMPT = PromptTemplate(
    template="""You are a technical content analyst. Your task is to validate and categorize content for a specific section of a technical blog.

{format_instructions}

SECTION INFORMATION:
Title: {section_title}
Learning Goals: {learning_goals}

RELEVANT DOCUMENT STRUCTURE:
{relevant_headers}

CONTENT REFERENCES:
{content_references}

TASK:
1. Evaluate each content reference for relevance to the section
2. Adjust relevance scores based on structural alignment with original headers
3. Categorize content appropriately (concept, example, implementation, best_practice)
4. Identify how each piece fits into the document structure
5. Prioritize content that maintains the original document's organization

Your output MUST be a list of JSON objects, each containing:
- content_snippet: A short snippet of the content for identification
- adjusted_relevance: A score from 0.0 to 1.0 indicating relevance
- category: One of "concept", "example", "implementation", "best_practice"
- notes: Optional notes about why this content is relevant
- structural_fit: Optional notes about how this content fits into the original document structure
    """,
    input_variables=[
        "format_instructions",
        "section_title",
        "learning_goals",
        "relevant_headers",
        "content_references",
    ],
)

# HyDE Generation Prompt
HYDE_GENERATION_PROMPT = PromptTemplate(
    template="""You are an expert technical writer simulating answering a query about a specific blog section.
Given the section title and learning goals, write a concise, hypothetical paragraph that directly addresses what a user might expect to learn or find in this section.
Focus on capturing the core concepts and potential content. This hypothetical answer will be used to find relevant source documents.

SECTION TITLE: {section_title}
LEARNING GOALS: {learning_goals}

HYPOTHETICAL ANSWER (Write a short paragraph):""",
    input_variables=["section_title", "learning_goals"],
)


# Export the prompts with their parsers
PROMPT_CONFIGS = {
    "content_mapping": {
        "prompt": CONTENT_MAPPING_PROMPT,
        "parser": content_mapping_parser
    },
    "content_validation": {
        "prompt": CONTENT_VALIDATION_PROMPT,
        "parser": content_mapping_parser  # Reuse the same parser
    },
    "section_generation": {
        "prompt": SECTION_GENERATION_PROMPT,
        "parser": section_generation_parser
    },
    "content_enhancement": {
        "prompt": CONTENT_ENHANCEMENT_PROMPT,
        "parser": None  # Text output
    },
    "code_example_extraction": {
        "prompt": CODE_EXAMPLE_EXTRACTION_PROMPT,
        "parser": code_example_parser
    },
    "quality_validation": {
        "prompt": QUALITY_VALIDATION_PROMPT,
        "parser": None  # JSON output
    },
    "feedback_incorporation": {
        "prompt": FEEDBACK_INCORPORATION_PROMPT,
        "parser": None  # Text output
    },
    "section_transition": {
        "prompt": SECTION_TRANSITION_PROMPT,
        "parser": None  # Text output
    },
    "blog_compilation": {
        "prompt": BLOG_COMPILATION_PROMPT,
        "parser": None  # Text output
    },
    "hyde_generation": {
        "prompt": HYDE_GENERATION_PROMPT,
        "parser": None # Text output
    }
}
