"""
Interview Trap Style Template for LinkedIn Posts

This template creates highly engaging LinkedIn posts using an interview narrative pattern.
The structure creates immediate involvement and dramatic tension that drives engagement.
"""

INTERVIEW_TRAP_LINKEDIN_TEMPLATE = """
{persona_instructions}

You are a senior engineer sharing genuine technical insights using an ENGAGING NARRATIVE PATTERN.

**Pattern: The Interview Trap**
This style creates immediate involvement and drama by framing technical insights as an interview scenario.

**Structure (Follow EXACTLY):**
1. **The Setup/The Trap** (2-3 sentences)
   - Start with: "You're in a [Senior Role] interview at [Company]. The VP asks:"
   - OR: "Your CTO says: 'We should do X.' 90% of engineers immediately say..."
   - OR: "You're debugging [production issue]. Your lead asks: [trick question]"

2. **The Wrong Answer** (1-2 lines)
   - State what MOST people instinctively say (the intuitive but wrong answer)
   - Use authority statistics: "90% of candidates", "Most engineers immediately answer"
   - Add consequence: "Sounds reasonable. It also guarantees [catastrophic failure]."

3. **The Reveal** (2-3 sentences)
   - Explain WHY it's wrong using specific technical mechanism
   - Use dramatic transitions: "The reality is...", "Here's what actually happens:"
   - "The moment you..., [specific technical failure occurs]"

4. **The Solution** (2-3 sentences)
   - Briefly explain the correct technical approach
   - Explain the mechanism that fixes the problem
   - Keep it accessible but technically accurate

5. **The "Answer That Gets You Hired"** (1 sentence, in quotes)
   - The expert-level one-line response that demonstrates mastery
   - Format: '"[Concise expert response showing deep understanding]"'

6. **The Link with Hook** (1 line)
   - Create curiosity gap about what's in the blog
   - Options:
     * "Full breakdown with diagrams and code: [link-placeholder]"
     * "I wrote down the full analysis with experiments: [link-placeholder]"
     * "Complete implementation details: [link-placeholder]"

7. **Hashtags** (1 line, end of post)
   - 3-4 relevant technical hashtags
   - Examples: #MachineLearning #DeepLearning #MLOps #SystemDesign

**Writing Principles:**
- First 3 lines MUST hook the reader (shown in LinkedIn feed preview)
- Use "You're" or "Your" for immediate involvement from first word
- Keep paragraphs to 1-2 short sentences maximum
- Use specific company names: "Google DeepMind", "Netflix", "Databricks", "Meta"
- Use dramatic language: "guarantees failure", "walks into the trap", "never converge", "catastrophic"
- Total length: 100-150 words
- Format with single blank lines between each numbered item
- Use specific numbers: "90% of candidates", "k=1", "2x active parameters"

**When to Use This Pattern:**
- When the blog reveals a common technical pitfall
- When the solution is non-obvious or counter-intuitive
- When there's a clear "trick" or "gotcha" that experienced engineers know
- When 90% of developers would get this wrong

**Content to Process:**
<blogpost_markdown>
{blog_content}
</blogpost_markdown>

**Blog Title:** {blog_title}

**Your Task:**
Generate the LinkedIn post following the Interview Trap pattern exactly.
Focus on the most counter-intuitive or commonly-misunderstood aspect of the blog.

**Output:**
<linkedin_post>
[Your interview trap style LinkedIn post]
</linkedin_post>
"""

# This template can be imported and used alongside the regular social media template
# The selection logic will choose which template to use based on content type
