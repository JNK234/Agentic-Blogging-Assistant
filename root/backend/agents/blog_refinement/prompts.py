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
{persona_instructions}

You wrote this blog post as part of your ongoing exploration of technology topics, and now you want to create compelling titles that will resonate with your professional audience and optimize for search discoverability.

**Blog Post You Wrote:**
```markdown
{blog_draft}
```

**Your Task:**
Create 3-4 different title and subtitle options for this post. Think about how you'd present this topic to different audiences - fellow professionals, practitioners exploring this area, or colleagues in your industry.

For each option, include:
1. **Title:** How you'd naturally frame this topic (clear, authoritative, professionally compelling)
2. **Subtitle:** Additional context that clarifies the scope and value of your exploration
3. **Reasoning:** Why this approach would attract and serve your target professional audience (balance of discoverability and genuine value)

**What makes a good title from your perspective:**
- Honest about what you actually explored and discovered in your research
- Clear about the practical value and applications without overselling
- Uses language that resonates with professionals seeking these insights
- Reflects the depth of investigation and key findings from your analysis
- Balances SEO discoverability with authentic professional communication

**Different angles to consider:**
- What key insights emerged from your investigation of this topic?
- What practical problems does this knowledge help solve in professional contexts?
- What would make someone in your field want to dive deeper into your research?
- How would you frame this for different levels of technical expertise in your audience?
- What search terms would professionals use to find content like this?

**Output Format:**
Provide your options as a JSON list:

```json
[
  {{
    "title": "Your natural way of introducing this topic",
    "subtitle": "Additional context that helps explain the value",
    "reasoning": "Why you think this resonates - focus on learning value and genuine usefulness"
  }}
]
```

Remember: You're creating titles that balance professional credibility with discoverability. Focus on accurately representing the value of your research while making it appealing to professionals who would benefit from these insights.
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
