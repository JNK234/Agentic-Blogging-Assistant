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
Write a brief and engaging introduction paragraph (typically 3-5 sentences) for this blog post.
The introduction should:
1.  Hook the reader and clearly state the blog post's main topic or purpose.
2.  Briefly mention the key areas or concepts that will be covered.
3.  Set the context and tone for the rest of the article.
4.  Avoid summarizing the entire content; focus on enticing the reader to continue.

**Output:**
Provide only the introduction paragraph text.
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
Write a brief conclusion paragraph (typically 3-5 sentences) for this blog post.
The conclusion should:
1.  Briefly summarize the main takeaways or key points discussed in the blog post.
2.  Reiterate the significance or implications of the topic.
3.  Offer a final thought, call to action (if appropriate), or suggest next steps for the reader.
4.  Provide a sense of closure.

**Output:**
Provide only the conclusion paragraph text.
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
Write a concise summary (target 2-4 sentences) of the entire blog post.
The summary should accurately capture the main topic, key concepts covered, and the overall message or outcome of the post. This summary might be used for meta descriptions or previews.

**Output:**
Provide only the summary text.
"""

# --- Title/Subtitle Generation ---
GENERATE_TITLES_PROMPT = """
You are an expert copywriter and SEO specialist tasked with generating compelling titles and subtitles for a blog post.
The full draft of the blog post is provided below.

**Blog Draft:**
```markdown
{blog_draft}
```

**Task:**
Generate 3-4 distinct and high-quality title and subtitle options for this blog post.
Each option must include:
1.  **Title:** Catchy, professional, simple, and SEO-optimized. Should accurately reflect the core topic.
2.  **Subtitle:** Complements the title, provides more context, and entices the reader.
3.  **Reasoning:** A brief explanation (1-2 sentences) justifying why this title/subtitle pair is effective (e.g., highlights key benefit, targets specific keywords, uses strong verbs, addresses audience need).

**Desired Output Format:**
Provide the output as a JSON list of objects, where each object has the keys "title", "subtitle", and "reasoning".

Example Format:
```json
[
  {{
    "title": "Example Title 1: Catchy and Clear",
    "subtitle": "An engaging subtitle explaining the core benefit.",
    "reasoning": "This option uses strong keywords for SEO and clearly states the value proposition."
  }},
  {{
    "title": "Example Title 2: Question-Based",
    "subtitle": "A subtitle that poses a relevant question to the reader.",
    "reasoning": "Engages the reader directly and highlights a common pain point relevant to the blog's content."
  }}
]
```

**Generate 3-4 options following this exact JSON format.**
"""
