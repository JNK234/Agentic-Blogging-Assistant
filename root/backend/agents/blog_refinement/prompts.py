# -*- coding: utf-8 -*-
"""
Prompts for the Blog Refinement Agent.
"""

# --- Introduction Generation ---
GENERATE_INTRODUCTION_PROMPT = """
You are an expert technical writer tasked with creating a compelling introduction for a blog post.
The full draft of the blog post is provided below.

**Blog Draft:**
```markdown
{blog_draft}
```

**Task:**
Write a professional, engaging introduction paragraph (typically 3-5 sentences) suitable for direct publication.
The introduction should:
1.  Hook the reader and clearly state the blog post's main topic or purpose.
2.  Briefly mention the key areas or concepts that will be covered.
3.  Set a professional and informative tone for the rest of the article.
4.  Avoid summarizing the entire content; focus on enticing the reader to continue.

**Output:**
Provide *only* the raw text for the introduction paragraph. Do NOT include any markdown formatting (like ```markdown), section headers, or extraneous text.
"""

# --- Conclusion Generation ---
GENERATE_CONCLUSION_PROMPT = """
You are an expert technical writer tasked with creating a concise and impactful conclusion for a blog post.
The full draft of the blog post is provided below.

**Blog Draft:**
```markdown
{blog_draft}
```

**Task:**
Write a professional, concise conclusion paragraph (typically 3-5 sentences) suitable for direct publication.
The conclusion should:
1.  Briefly summarize the main takeaways or key points discussed in the blog post.
2.  Reiterate the significance or implications of the topic.
3.  Offer a final thought, call to action (if appropriate), or suggest next steps for the reader.
4.  Provide a sense of closure.

**Output:**
Provide *only* the raw text for the conclusion paragraph. Do NOT include any markdown formatting (like ```markdown), section headers, or extraneous text.
"""

# --- Summary Generation ---
GENERATE_SUMMARY_PROMPT = """
You are an expert technical writer tasked with creating a concise summary of a blog post.
The full draft of the blog post is provided below.

**Blog Draft:**
```markdown
{blog_draft}
```

**Task:**
Write a concise summary (target 2-4 sentences) of the entire blog post, suitable for direct use (e.g., meta descriptions, social media previews).
The summary should accurately capture the main topic, key concepts covered, and the overall message or outcome of the post.

**Output:**
Provide *only* the raw text for the summary. Do NOT include any markdown formatting (like ```markdown), headers, or extraneous text.
"""

# --- Title/Subtitle Generation ---
GENERATE_TITLES_PROMPT = """
You are an expert copywriter and SEO specialist tasked with generating compelling titles and subtitles for a blog post.
The full draft of the blog post is provided below.

Create compelling titles that reflect how an expert practitioner would share insights with peers. Your titles should communicate clear value and specific outcomes while maintaining the authentic voice of someone sharing hard-earned knowledge.

**EXPERT PRACTITIONER TITLE PHILOSOPHY:**
You're not creating marketing copy—you're offering genuine insights to fellow practitioners who value substance over style. Your titles should reflect the same conversational authority and strategic clarity found in the best technical writing.

**BLOG POST ANALYSIS:**
```markdown
{blog_draft}
```

**TITLE CREATION PRINCIPLES:**

1. **Direct Value Communication**:
   - Promise specific learning outcomes based on actual content
   - Use concrete language over abstract descriptions
   - Lead with the most valuable insight or practical outcome
   - Reflect the expert practitioner's authentic voice

2. **Contextual Specificity**:
   - Include relevant technical context (when appropriate)
   - Specify the scope and application domain
   - Use precise terminology that signals expertise
   - Avoid generic technology labels when specifics matter

3. **Natural Language Patterns**:
   - Use conversational phrasing that sounds natural, not corporate
   - Apply the narrative elements present in the content
   - Reflect any historical context or evolution presented
   - Match the sophistication level of the content

4. **Engagement Through Curiosity**:
   - Pose questions when content explores open problems
   - Highlight surprising insights or counterintuitive findings
   - Use comparison/contrast when content compares approaches
   - Create intrigue about methodology or implementation details

**ADAPTIVE TITLE APPROACHES:**

Based on content analysis, choose the most appropriate approach:
- **Evolution Narrative**: "From [Past] to [Present]: [Insight]"
- **Practical Implementation**: "[Specific Approach] for [Specific Context]"
- **Insight Sharing**: "Why [Observation] Matters for [Application]"
- **Problem-Solution**: "[Challenge] and [Effective Solution]"
- **Comparative Analysis**: "[Method A] vs [Method B]: [Key Difference]"

**OUTPUT FORMAT:**

Generate exactly 3 title options as a JSON array. Each option should follow this exact structure:

```json
[
  {{
    "title": "Your compelling title here",
    "subtitle": "Your informative subtitle that adds context",
    "reasoning": "Brief explanation of why this title works"
  }},
  {{
    "title": "Second title option",
    "subtitle": "Second subtitle option",
    "reasoning": "Brief explanation for second option"
  }},
  {{
    "title": "Third title option",
    "subtitle": "Third subtitle option",
    "reasoning": "Brief explanation for third option"
  }}
]
```

**CRITICAL INSTRUCTIONS:**
- Output ONLY the JSON array, no other text
- Generate exactly 3 options
- Each object must have exactly these three keys: "title", "subtitle", "reasoning"
- Ensure proper JSON formatting with double quotes
- Do not include markdown code blocks or any other formatting

Focus on titles that authentically represent both the content depth and the expert practitioner voice—direct, valuable, and reflective of genuine technical insight sharing.
"""

# --- Main Content Formatting ---
FORMAT_MAIN_CONTENT_PROMPT = """
You are an expert technical editor and Markdown formatter.
The raw draft of a blog post's main content is provided below.

**Raw Blog Draft Content:**
```markdown
{blog_draft_content}
```

**Task:**
Review and reformat the provided blog draft content to enhance its readability, structure, and overall quality for publication.
Your primary goal is to improve the formatting and structure **based *only* on the provided "Raw Blog Draft Content"**.
Do NOT introduce any new information, facts, or concepts not present in the provided draft.
If the draft is missing information or seems incomplete in certain areas, format it as is, and do not attempt to fill in gaps by inventing content.

Apply the following formatting guidelines:
1.  **Structure and Flow:**
    *   Ensure logical paragraph breaks.
    *   Use Markdown headings (e.g., `## Section Title`, `### Subsection Title`) appropriately to organize content. Do not use H1 (`#`) as that is typically reserved for the main blog title.
    *   Ensure a smooth flow between ideas and sections based on the existing text.
2.  **Markdown Formatting:**
    *   Apply **bold** (`**text**`) to emphasize key terms, concepts, or important takeaways *already present in the text*.
    *   Use *italics* (`*text*` or `_text_`) for definitions, new terms, or subtle emphasis *as appropriate for the existing text*.
    *   Create bulleted (`- item`) or numbered (`1. item`) lists for sequences, steps, or collections of items *if the text implies such a structure*.
3.  **LaTeX Formulas:**
    *   Ensure any mathematical formulas *present in the draft* are correctly enclosed in LaTeX delimiters for Markdown rendering.
    *   Use `$...$` for inline formulas (e.g., `The equation is $E=mc^2$.`).
    *   Use `$$...$$` for block-level formulas (e.g., `$$ \sum_{i=1}^{n} x_i $$`).
    *   Verify that the LaTeX syntax *within the delimiters* is correct based on standard mathematical notation. Do not alter the meaning of the formulas.
4.  **Code Blocks:**
    *   Ensure code snippets *present in the draft* are enclosed in triple backticks (``` ```) with the appropriate language identifier (e.g., ```python).
5.  **Readability:**
    *   Break up long sentences or paragraphs *from the existing text*.
    *   Ensure clarity and conciseness *of the existing text*.
    *   Correct any minor grammatical errors or typos *if obvious and do not change the meaning of the original text*. The primary focus is on formatting and structure, not re-writing.
6.  **Consistency:** Maintain consistent formatting throughout the document.

**Important:**
*   Focus *only* on formatting the main body content provided in "Raw Blog Draft Content".
*   **Crucially, do NOT add any new information, facts, explanations, or concepts that are not explicitly present in the "Raw Blog Draft Content". Your task is to format, not to expand or research.**
*   The output should be the fully formatted Markdown content of the main blog body, derived strictly from the input.

**Output:**
Provide *only* the fully formatted Markdown text for the main blog content. Do NOT include any extraneous text, explanations, or markdown formatting like ```markdown around the entire output.

**Example of Expected Output Formatting (based on hypothetical input):**
```markdown
## Understanding Activation Functions

Activation functions are a **critical component** of neural networks. They introduce non-linearity into the model, allowing it to learn complex patterns.
One common activation function is the *Sigmoid function*, defined as:
$$ \sigma(x) = \frac{1}{1 + e^{-x}} $$
This function squashes any input $x$ to a value between 0 and 1.

### Types of Activation Functions
There are several types of activation functions, including:
- ReLU (Rectified Linear Unit)
- Tanh (Hyperbolic Tangent)
- Softmax

Here's a simple Python code snippet demonstrating ReLU:
```python
def relu(x):
  return max(0, x)
```
Choosing the right activation function is important for model performance.
```
"""

# --- Clarity and Flow Suggestions ---
SUGGEST_CLARITY_FLOW_IMPROVEMENTS_PROMPT = """
You are an expert editor reviewing a technical blog post draft for clarity and flow.
The full draft of the blog post is provided below.

**Blog Draft:**
```markdown
{blog_draft}
```

**Task:**
Review the provided blog draft and identify specific areas where clarity or flow could be improved.
Provide actionable suggestions. Focus on:
1.  **Clarity:** Are there ambiguous sentences, jargon that needs explanation, or overly complex phrasing? 
2.  **Flow:** Do the ideas transition smoothly between paragraphs and sections? Is the overall structure logical? Are there abrupt shifts?
3.  **Conciseness:** Can any parts be stated more directly without losing meaning?

**Output Format:**
If there is repeated content, remove that, the entire content has to be meaningful and appropriate to the reader. There could be multiple markdown text, you should make sure that all the markdown sections are well compiled 

**Flow**
Thee flow of the content should have an introduction, the main content, the summary and conclusion
"""

# --- Redundancy Reduction ---
REDUCE_REDUNDANCY_PROMPT = """
You are an expert technical editor specializing in content optimization and redundancy reduction.
The full draft of the blog post is provided below.

**Blog Draft:**
```markdown
{blog_draft}
```

**Task:**
Analyze the blog post for redundant content and produce a refined version with redundancies removed or reduced.
Focus on:

1. **Repeated Information**: Identify and consolidate information that appears multiple times throughout the post
2. **Overlapping Sections**: Merge sections that cover similar topics
3. **Redundant Examples**: Keep only the most illustrative examples when multiple similar ones exist
4. **Verbose Phrasing**: Replace wordy expressions with concise alternatives
5. **Circular Arguments**: Remove content that reiterates the same point without adding new value

**Important Guidelines:**
- Preserve all unique and valuable information
- Maintain the logical flow and structure of the content
- Keep the technical accuracy intact
- Ensure that removing redundancy doesn't create gaps in understanding
- Retain at least one instance of important concepts for clarity

**Output:**
Provide the complete refined blog post with redundancies removed. Output only the markdown content without any explanations or meta-commentary.
"""
