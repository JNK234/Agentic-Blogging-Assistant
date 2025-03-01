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

SECTION INFORMATION:
Title: {section_title}
Learning Goals: {learning_goals}

RELEVANT CONTENT:
{formatted_content}

PREVIOUS SECTION CONTEXT:
{previous_context}

TASK:
Write a comprehensive and engaging blog section that:

1. Structure:
   - Start with a clear technical introduction
   - Break down complex concepts into digestible parts
   - Build concepts progressively
   - Conclude with key takeaways

2. Technical Depth:
   - Use appropriate technical terminology and jargon
   - Explain advanced concepts with precision
   - Include relevant technical specifications
   - Reference industry standards where applicable

3. Code Examples:
   - Provide well-commented code snippets
   - Explain each significant code block
   - Include setup and configuration details
   - Show best practices in implementation

4. Implementation Focus:
   - Include practical implementation details
   - Highlight common pitfalls and solutions
   - Discuss performance considerations
   - Address security implications if relevant

5. Educational Style:
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
    """,
    input_variables=[
        "format_instructions",
        "section_title",
        "learning_goals",
        "formatted_content",
        "previous_context",
    ],
)

# Content Enhancement Prompt
CONTENT_ENHANCEMENT_PROMPT = PromptTemplate(
    template="""You are an expert technical editor. Enhance the following blog section to make it more comprehensive, technically accurate, and engaging:

{format_instructions}

SECTION INFORMATION:
Title: {section_title}
Learning Goals: {learning_goals}

CURRENT CONTENT:
{existing_content}

ADDITIONAL RELEVANT CONTENT:
{formatted_content}

TASK:
Enhance the existing content by:
1. Adding more technical depth where needed
2. Improving code examples with better comments and explanations
3. Adding practical implementation details
4. Clarifying complex concepts
5. Adding best practices and tips
6. Ensuring all learning goals are thoroughly addressed

IMPORTANT:
- Maintain the original structure and flow
- Keep the technical accuracy high
- Ensure code examples are well-explained
- Add concrete examples for abstract concepts
- Highlight key points and takeaways

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

# Quality Validation Prompt
QUALITY_VALIDATION_PROMPT = PromptTemplate(
    template="""You are an expert content quality assessor. Evaluate the following blog section:

SECTION INFORMATION:
Title: {section_title}
Learning Goals: {learning_goals}

CONTENT:
{section_content}

TASK:
Evaluate the content on the following criteria:
1. Completeness: Does it cover all learning goals?
2. Technical accuracy: Is the information correct?
3. Clarity: Is the content easy to understand?
4. Code quality: Are code examples well-written and explained?
5. Engagement: Is the content engaging and interesting?

FORMAT YOUR RESPONSE AS A JSON OBJECT:
{{
    "completeness": 0.0-1.0,
    "technical_accuracy": 0.0-1.0,
    "clarity": 0.0-1.0,
    "code_quality": 0.0-1.0,
    "engagement": 0.0-1.0,
    "overall_score": 0.0-1.0,
    "improvement_needed": true/false,
    "improvement_suggestions": ["suggestion1", "suggestion2", ...]
}}
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

CONTENT REFERENCES:
{content_references}

TASK:
1. Evaluate each content reference for relevance to the section
2. Adjust relevance scores if needed
3. Categorize content appropriately (concept, example, implementation, best_practice)
4. Identify the most valuable content for this section

Your output MUST be a list of JSON objects, each containing:
- content_snippet: A short snippet of the content for identification
- adjusted_relevance: A score from 0.0 to 1.0 indicating relevance
- category: One of "concept", "example", "implementation", "best_practice"
- notes: Optional notes about why this content is relevant
    """,
    input_variables=[
        "format_instructions",
        "section_title",
        "learning_goals",
        "content_references",
    ],
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
    }
}
