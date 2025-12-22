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

**QUESTION-BASED COMPARISON PATTERN - PRIMARY APPROACH:**

This pattern works exceptionally well for technical content comparing two approaches, revealing a counter-intuitive finding, or challenging conventional wisdom. It creates immediate curiosity while remaining grounded in the actual topic.

**Pattern:** "{Question Word} {Topic A} {Verb} {Topic B}?"
- Question Word: What, When, Can, Why, Does
- Topic A: The subject/technique being discussed
- Verb: Make, Work, Use, Need, Help, Hurt, Replace, Cost
- Topic B: The comparison point or outcome

**Examples for different content types:**
- Performance comparisons: "What Makes X Faster Than Y?"
- Feasibility questions: "Can X Work Without Y?"
- Timing/conditions: "When Does X Hurt More Than Y?"
- Mechanism questions: "Why Does X Need Y?"
- Cost-benefit: "Does X Always Cost More Than Y?"

**Subtitle Formula:** {Technical difference} + {specific metric} + {what's preserved or the trade-off}
- Keep it factual and specific
- Include numbers when available (8% savings, 90% reduction, 3x faster)
- Mention what stays the same or what the benefit is

**REFERENCE EXAMPLES:**

For RMSNorm content:
- Title: "What Makes RMSNorm Faster Than LayerNorm?"
- Subtitle: "Eliminating mean subtraction cuts computation by 8% while preserving the re-scaling benefits"

For MoE routing content:
- Title: "Can MoE Use Single-Expert Routing?"
- Subtitle: "k=1 selection blocks gradient flow, requiring k≥2 to train all experts effectively"

For KV-Cache content:
- Title: "When Does KV-Cache Hurt More Than Help?"
- Subtitle: "Caching costs 3.2GB for 1K tokens—recomputation reduces memory by 60% with 15% latency trade-off"

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
   - Pose questions when content compares two approaches
   - Highlight surprising insights or counterintuitive findings
   - Use comparison/contrast when evaluating alternatives
   - Create intrigue about methodology or implementation details

**PRIORITY APPROACHES:**

1. **Question-Based Comparison** (HIGHEST PRIORITY): Use when content compares two approaches, techniques, or reveals counter-intuitive findings
   - Pattern: "{Question} {Topic A} {Verb} {Topic B}?"
   - Creates immediate engagement while staying grounded in content

2. **Insight Revelation**: Use when content uncovers a non-obvious mechanism or failure mode
   - Pattern: "{What/Why} {Topic} {Unexpected Outcome}?"

3. **Problem-Solution**: Use as fallback when content focuses on solving a specific problem
   - Pattern: "{How} {Problem} {Solution}?"

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
- Generate 3 options following the Question-Based Comparison pattern
- Each should be different: vary the question word, comparison point, or angle
- Keep titles concise (5-8 words is ideal)
- Keep subtitles factual and specific (15-25 words)
- Output ONLY the JSON array, no other text
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

# --- Content Enhancement and Flow Optimization ---
SUGGEST_CLARITY_FLOW_IMPROVEMENTS_PROMPT = """
You are an expert technical editor tasked with enhancing a blog post draft for clarity, flow, and engagement.
The full draft is provided below.

**Blog Draft:**
```markdown
{blog_draft}
```

**Task:**
Review and improve the draft while **PRESERVING ALL CONTENT AND WORD COUNT**. Focus on:

1. **Remove Duplicates**: Identify and remove exact duplicate headings/sections (keep first instance)
2. **Improve Transitions**: Add connecting sentences between sections that feel disconnected
3. **Fix Flow Issues**: Rephrase awkward transitions, ensure logical progression
4. **Format Consistency**: Standardize heading levels, code blocks, LaTeX formatting
5. **Language Polish**: Fix grammar, typos, clarify ambiguous sentences (without removing detail)

**CRITICAL CONSTRAINTS**:
- DO NOT remove any technical details, examples, or explanations
- Maintain approximately the same word count (±5%)
- DO NOT summarize or consolidate sections
- Preserve all code blocks, formulas, and tables
- Keep every unique piece of information

**Output:**
Provide the COMPLETE enhanced draft, outputting ONLY the fully formatted markdown content.
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
