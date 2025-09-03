from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from root.backend.agents.blog_draft_generator.state import ContentReference, CodeExample, DraftSection, ImagePlaceholder

# Expert Writing Principles for contextual content generation
EXPERT_WRITING_PRINCIPLES = """**CONTEXTUAL CONTENT GENERATION PRINCIPLES:**

VOICE AUTHENTICITY:
- Embody expert practitioner sharing insights with peers
- Use conversational authority: balance confidence with appropriate uncertainty
- Apply strategic vulnerability: acknowledge limitations and share learning moments
- Create reader partnership: collaborative exploration rather than one-way information transfer

STRUCTURAL INTELLIGENCE:
- Apply "Context-Definition-Application" pattern for introducing new concepts
- Use "Pyramid of Clarity" organization when content has varying complexity levels
- Employ "Time-Context-Question" introductions for historically relevant topics
- Adapt paragraph length based on content function: brief hooks, detailed explanations, bridge transitions

ENGAGEMENT MASTERY:
- Build genuine curiosity through strategic questions and surprising observations
- Apply engagement formulas contextually: "Surprise-Insight-Application", "Historical-Current-Future"
- Create narrative structure with setup → exploration → insight → implications
- Use natural variation in sentence structure and transition phrases

COMPLEXITY ADAPTATION:
- Assess content depth and adjust complexity layering appropriately
- Start with value proposition before diving into implementation details
- Use progressive disclosure only when content complexity actually varies
- Connect abstract concepts to practical applications throughout

NATURAL LANGUAGE FLOW:
- Vary sentence structure for reading rhythm (short declarations, medium explanations, longer analysis)
- Use organic transitions that emerge from content logic, not forced patterns
- Apply personal insights and observations when they add genuine value
- Maintain technical precision while ensuring accessibility to intended audience"""

# Initialize parsers
content_mapping_parser = PydanticOutputParser(pydantic_object=ContentReference)
section_generation_parser = PydanticOutputParser(pydantic_object=DraftSection)
code_example_parser = PydanticOutputParser(pydantic_object=CodeExample)
image_placeholder_parser = PydanticOutputParser(pydantic_object=ImagePlaceholder)

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
    template="""{persona_instructions}

{expert_writing_principles}

Generate a focused and clear blog section based on the following information:

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

BLOG NARRATIVE CONTEXT:
{blog_narrative_context}

SECTION CONTINUITY GUIDELINES:
- This section should flow naturally from the previous content
- Avoid standalone introductions - build upon established context
- Consider upcoming sections when concluding this section
- Maintain consistent technical depth and explanation style throughout the blog
- Ensure section titles feel like natural progressions, not independent blog titles

ANTI-REDUNDANCY GUIDELINES:
- Avoid repeating concepts already established in previous sections
- Focus on unique value this section provides to the overall narrative
- If referencing previous concepts, do so briefly without re-explaining
- Build upon rather than repeat previously covered material
- Be concise - prefer clarity over comprehensive coverage

LENGTH CONSTRAINTS (IMPORTANT):
Target Length for This Section: {target_section_length} words (estimated)
Current Blog Length: {current_blog_length} words
Remaining Length Budget: {remaining_length_budget} words
Length Priority: {length_priority} (expand/maintain/compress - adjust content depth accordingly)

**Length Guidelines:**
- Prioritize clarity and value over word count
- If length_priority is "compress": Be concise, focus on essential points only
- If length_priority is "maintain": Aim for target length with balanced coverage
- If length_priority is "expand": Include additional context and examples as needed
- Always prefer quality explanations over padding content to meet length targets

**SECTION CONTEXT:**
Title: {section_title}
Learning Goals: {learning_goals}
Content Depth: Adapt complexity and engagement based on material analysis
Audience: Fellow practitioners seeking both understanding and practical insights

**GENERATION APPROACH:**
1. Analyze the content requirements and determine appropriate complexity level
2. Choose narrative structure that best serves the material (not predetermined formula)
3. Apply engagement principles naturally based on content opportunities
4. Use expert practitioner voice with contextual authority and appropriate vulnerability
5. Create reading experience that serves the learner's journey, not style compliance

TASK:
Write a focused and engaging blog section that adheres strictly to the provided constraints:

**CRITICAL CONSTRAINTS - MUST BE FOLLOWED STRICTLY:**
- **Code Inclusion (ABSOLUTE RULE):** Check `current_section_data.include_code`:
  * If `false`: DO NOT include ANY code examples, code blocks, pseudocode, or implementation details
  * If `false`: Focus ONLY on conceptual explanations, theories, and theoretical frameworks
  * If `false`: Use descriptive text and explanations without showing "how to implement"
  * If `true`: Only then proceed with actual code generation and implementation details
- **Subpoint Limit:** The number of distinct sub-topics or points discussed should not exceed `current_section_data.max_subpoints`. Be concise if the limit is low.
- **Code Example Limit:** If and ONLY if `include_code` is `true`, generate a maximum of `current_section_data.max_code_examples` relevant code snippets. Choose the most illustrative examples.

Generate section content that embodies these principles while serving the specific learning goals and maintaining technical accuracy.

**CONTENT GENERATION:**
Write a focused and engaging blog section that:

1. Structure:
   - Adhere to the `max_subpoints` constraint from `current_section_data`.
   - Follow the original document structure where applicable.
   - Maintain the hierarchical relationships between topics.
   - Ensure the section begins by directly addressing its topic, flowing naturally from the previous section or transition. Avoid standalone introductions if a transition is already provided.
   - Break down complex concepts into digestible parts.
   - Build concepts progressively.
   - Ensure the section ends by covering its intended scope. Avoid adding separate summary paragraphs for this section, as overall summarization is handled at the blog compilation stage and transitions will bridge to the next section.

2. Content Preservation:
   - Prioritize using content from the original document
   - Maintain the original explanations and examples where possible
   - Preserve the logical flow of the original content
   - Use the original section headers as a guide
   - **Crucially, all generated content for this section's body must be based *solely* on the information present in the 'RELEVANT CONTENT', 'ORIGINAL DOCUMENT STRUCTURE', and 'STRUCTURAL INSIGHTS' provided. Do NOT invent or infer information beyond these sources.**
   - If specific details from the learning goals cannot be substantiated from the provided context, briefly state that the information is not covered in the source material rather than hallucinating.

3. Technical Depth:
   - Use appropriate technical terminology and jargon *as found in the provided content*.
   - Explain advanced concepts with precision, *grounding explanations in the provided sources*.
   - Include relevant technical specifications *if available in the sources*.
   - Reference industry standards where applicable, *if mentioned in the sources*.

4. Code Examples - CONDITIONAL SECTION:
   - **CRITICAL**: This entire section applies ONLY if `current_section_data.include_code` is `true`
   - **If include_code is false**: Skip this section entirely and focus on conceptual content
   - **If include_code is true**: 
     * Provide well-commented code snippets
     * Explain each significant code block
     * Include setup and configuration details
     * Show best practices in implementation
     * Limit the number of examples to `current_section_data.max_code_examples`

5. Implementation Focus - CONDITIONAL SECTION:
   - **CRITICAL**: This section applies ONLY if `current_section_data.include_code` is `true`
   - **If include_code is false**: Focus on conceptual understanding rather than implementation
   - **If include_code is true**:
     * Include practical implementation details
     * Highlight common pitfalls and solutions
     * Discuss performance considerations
     * Address security implications if relevant

6. Educational Style:
   - Use professional technical tone
   - Include callouts for important points
   - Add technical tips and tricks
   - Reference relevant documentation

Format Guidelines:
- The primary output for the section's body should be placed directly into the "content" field of the `DraftSection` JSON object.
- This "content" field MUST be a string containing well-formed Markdown.
- **CODE BLOCK WARNING**: Only include code blocks (```language ... ```) if `current_section_data.include_code` is `true`
- Within this Markdown string in the "content" field:
    - Use Markdown formatting (headings, lists, bold, italics, etc.).
    - Include code blocks with language specification ONLY if `include_code` is `true` (e.g., ```python ... ```).
    - Use tables for comparing approaches.
    - Add bullet points for key concepts.
    - Include technical notes and warnings.
    - Reference external documentation where relevant.
- Ensure LaTeX formulas are correctly embedded in the Markdown (e.g., $E=mc^2$ or $$ \sum x_i $$).
- **Adherence to Source**: The generated Markdown in the "content" field must strictly adhere to the provided 'RELEVANT CONTENT' and structural information. Avoid introducing external knowledge or hallucinated details.

Ensure the "content" field's Markdown is:
- Technically accurate *based on the provided sources*.
- Well-structured
- Practical and implementable *as suggested by the sources*.
- Suitable for professional developers
- Consistent with the original document's organization
    """,
    input_variables=[
        "persona_instructions",
        "expert_writing_principles",
        "format_instructions",
        "section_title",
        "learning_goals",
        "original_structure",
        "structural_insights",
        "formatted_content",
        "previous_context",
        "blog_narrative_context",
        "target_section_length",
        "current_blog_length",
        "remaining_length_budget",
        "length_priority",
        "current_section_data", # Added
    ],
)

# Content Enhancement Prompt
CONTENT_ENHANCEMENT_PROMPT = PromptTemplate(
    template="""You are an expert technical editor. Enhance the following blog section to make it more focused, technically accurate, and engaging while strictly adhering to the provided constraints:

{format_instructions}

SECTION INFORMATION:
Title: {section_title}
Learning Goals: {learning_goals}
Constraints: {current_section_data} # Contains include_code, max_subpoints, max_code_examples

ORIGINAL DOCUMENT STRUCTURE:
{original_structure}

STRUCTURAL INSIGHTS:
{structural_insights}

CURRENT CONTENT:
{existing_content}

ADDITIONAL RELEVANT CONTENT:
{formatted_content}

**CRITICAL CONSTRAINTS - MUST BE FOLLOWED STRICTLY:**
- **Code Inclusion (ABSOLUTE RULE):** Check `current_section_data.include_code`:
  * If `false`: DO NOT include ANY code examples, code blocks, pseudocode, or implementation details
  * If `false`: Remove any existing code blocks from the current content
  * If `false`: Focus ONLY on conceptual explanations, theories, and theoretical frameworks
  * If `false`: Use descriptive text and explanations without showing "how to implement"
  * If `true`: Only then maintain or enhance existing code examples and implementation details
- **Subpoint Limit:** The number of distinct sub-topics or points discussed should not exceed `current_section_data.max_subpoints`
- **Code Example Limit:** If and ONLY if `include_code` is `true`, maintain a maximum of `current_section_data.max_code_examples` relevant code snippets

TASK:
Enhance the existing content by:
1. **STRICTLY ENFORCING CONSTRAINTS:** Follow the include_code flag absolutely - NO EXCEPTIONS
2. Following the original document structure where applicable
3. Preserving the logical flow of the original content
4. Adding more technical depth where needed (conceptual only if include_code is false)
5. Improving explanations and clarity
6. Clarifying complex concepts
7. Adding best practices and tips (non-implementation focused if include_code is false)
8. Ensuring all learning goals are thoroughly addressed

**CONTENT GROUNDING REQUIREMENTS:**
- **Crucially, all enhanced content must be based *solely* on the information present in the 'CURRENT CONTENT', 'ADDITIONAL RELEVANT CONTENT', 'ORIGINAL DOCUMENT STRUCTURE', and 'STRUCTURAL INSIGHTS' provided**
- Do NOT invent or infer information beyond these sources
- If specific details cannot be substantiated from the provided context, briefly state that the information is not covered in the source material
- Preserve the original explanations and examples where possible
- Maintain the logical flow of the original content

IMPORTANT:
- Do not provide a starting line like "Okay, here's the enhanced blog section.... etc" just provide the main content 
- Maintain the original structure and flow
- Prioritize using content from the original document
- Keep the technical accuracy high based on provided sources
- Add concrete examples for abstract concepts only if available in source material
- Focus on covering the learning goals thoroughly through explanation and examples rather than explicit summaries
- Preserve the hierarchical relationships between topics

FORMAT:
- Use markdown formatting
- **CODE BLOCK WARNING**: Only include code blocks (```language ... ```) if `current_section_data.include_code` is `true`
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
        "current_section_data",
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
    template="""You are an expert technical editor. Revise the following blog section based on feedback while strictly adhering to the provided constraints:

SECTION INFORMATION:
Title: {section_title}
Learning Goals: {learning_goals}
Constraints: {current_section_data} # Contains include_code, max_subpoints, max_code_examples

CURRENT CONTENT:
{existing_content}

FEEDBACK:
{feedback}

ORIGINAL DOCUMENT STRUCTURE:
{original_structure}

STRUCTURAL INSIGHTS:
{structural_insights}

**CRITICAL CONSTRAINTS - MUST BE FOLLOWED STRICTLY:**
- **Code Inclusion (ABSOLUTE RULE):** Check `current_section_data.include_code`:
  * If `false`: DO NOT include ANY code examples, code blocks, pseudocode, or implementation details
  * If `false`: Remove any code blocks that may have been added
  * If `false`: Focus ONLY on conceptual explanations, theories, and theoretical frameworks
  * If `false`: Use descriptive text and explanations without showing "how to implement"
  * If `true`: Only then maintain or improve existing code examples and implementation details
- **Subpoint Limit:** The number of distinct sub-topics or points discussed should not exceed `current_section_data.max_subpoints`
- **Code Example Limit:** If and ONLY if `include_code` is `true`, maintain a maximum of `current_section_data.max_code_examples` relevant code snippets

TASK:
Revise the content to address all feedback points while:
1. **STRICTLY ENFORCING CONSTRAINTS:** Follow the include_code flag absolutely - NO EXCEPTIONS
2. Maintaining the original structure and flow
3. Preserving technical accuracy
4. Enhancing clarity and engagement
5. Improving explanations (code examples only if include_code is true)
6. Ensuring all learning goals are thoroughly addressed
7. Preserving the hierarchical relationships between topics
8. Maintaining consistency with the original document's organization

**CONTENT GROUNDING REQUIREMENTS:**
- **Crucially, all revised content must be based *solely* on the information present in the 'CURRENT CONTENT', 'ORIGINAL DOCUMENT STRUCTURE', and 'STRUCTURAL INSIGHTS' provided**
- Do NOT invent or infer information beyond these sources
- If the feedback requests information not available in the source material, briefly state that the information is not covered in the source material
- Preserve the original explanations and examples where possible
- Maintain the logical flow of the original content

IMPORTANT:
- If the feedback mentions structural consistency, ensure your revisions align with the original document structure
- Preserve the logical flow of the original content
- Maintain the hierarchical relationships between topics
- Use the original section headers as a guide where applicable
- Focus only on addressing the specific feedback points while maintaining constraints

FORMAT:
- Use markdown formatting
- **CODE BLOCK WARNING**: Only include code blocks (```language ... ```) if `current_section_data.include_code` is `true`
- Use headings, lists, and emphasis appropriately
- Keep paragraphs concise and focused
    """,
    input_variables=[
        "section_title",
        "learning_goals",
        "existing_content",
        "feedback",
        "original_structure",
        "structural_insights",
        "current_section_data",
    ],
)

# Section Transition Prompt
SECTION_TRANSITION_PROMPT = PromptTemplate(
    template="""{persona_instructions}

Create a smooth transition between these blog sections:

CURRENT SECTION:
Title: {current_section_title}
Ending: {current_section_ending}

NEXT SECTION:
Title: {next_section_title}

BLOG CONTEXT:
Blog Title: {blog_title}
Current Position: Section {current_section_index} to {next_section_index} of {total_sections}

TASK:
Write a brief transition paragraph (2-3 sentences) that:
1. Summarizes the key points from the current section
2. Creates a logical bridge to the next section
3. Maintains the technical and educational tone
    """,
    input_variables=[
        "persona_instructions",
        "current_section_title",
        "current_section_ending",
        "next_section_title",
        "blog_title",
        "current_section_index",
        "next_section_index",
        "total_sections",
    ],
)

# Final Blog Compilation Prompt
BLOG_COMPILATION_PROMPT = PromptTemplate(
    template="""{persona_instructions}

Compile the following blog sections into a cohesive final blog post:

BLOG TITLE: {blog_title}
DIFFICULTY LEVEL: {difficulty_level}
PREREQUISITES: {prerequisites}

ORIGINAL DOCUMENT STRUCTURE:
{original_structure}

SECTIONS:
{sections_content}

TRANSITIONS:
{transitions}

COMPILATION GUIDELINES:
- Ensure consistent voice and style throughout per persona instructions
- Verify smooth narrative flow between all sections
- Check that section titles create natural progression
- Maintain technical depth consistency
- Ensure overall blog feels cohesive, not like assembled individual posts

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
        "persona_instructions",
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

# Image Placeholder Generation Prompt
IMAGE_PLACEHOLDER_PROMPT = PromptTemplate(
    template="""You are an expert content designer specializing in technical documentation. Analyze the following blog section and suggest strategic image placeholders that would enhance understanding and break up text-heavy content.

{format_instructions}

SECTION INFORMATION:
Title: {section_title}
Learning Goals: {learning_goals}
Content Type: {content_type}
Has Code Examples: {has_code_examples}

SECTION CONTENT:
{section_content}

CONTENT ANALYSIS:
- Content Length: {content_length} words
- Technical Complexity: {complexity_level}
- Main Concepts: {main_concepts}

TASK:
Analyze the section content and suggest 1-2 strategic image placeholders that would:
1. Enhance reader understanding of complex concepts
2. Provide visual breaks in text-heavy sections
3. Support the learning objectives
4. Complement the content without being redundant

For each suggested image, consider:
- **Type**: diagram, screenshot, chart, illustration, flowchart, architecture, comparison, etc.
- **Description**: Detailed description of what the image should show
- **Alt Text**: Accessibility-friendly description for screen readers
- **Placement**: Where in the section it should appear (section_start, after_concept, before_example, section_end)
- **Purpose**: How it specifically enhances understanding of the content

VISUAL OPPORTUNITY GUIDELINES:
- **Process Descriptions**: Flow diagrams or step-by-step visualizations
- **Technical Concepts**: Conceptual diagrams or architectural overviews
- **Code Examples**: Syntax-highlighted screenshots or IDE views (only if has_code_examples is true)
- **Data Structures**: Schema diagrams or visual representations
- **Comparisons**: Side-by-side comparisons or before/after scenarios
- **Complex Relationships**: Network diagrams or hierarchical structures

PLACEMENT STRATEGY:
- **section_start**: Overview diagrams that introduce the topic
- **after_concept**: Diagrams that illustrate concepts just explained
- **before_example**: Setup diagrams that prepare for examples
- **section_end**: Summary visualizations or result demonstrations

Only suggest images that would genuinely add value. If the section is already clear and well-structured, suggest fewer or no images.

Your output MUST be a valid JSON object following the ImagePlaceholder schema. If no meaningful images are needed, return an empty JSON object with explanation in the description field.""",
    input_variables=[
        "format_instructions",
        "section_title", 
        "learning_goals",
        "content_type",
        "has_code_examples",
        "section_content",
        "content_length",
        "complexity_level", 
        "main_concepts",
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
    },
    "hyde_generation": {
        "prompt": HYDE_GENERATION_PROMPT,
        "parser": None # Text output
    },
    "image_placeholder": {
        "prompt": IMAGE_PLACEHOLDER_PROMPT,
        "parser": image_placeholder_parser
    }
}
