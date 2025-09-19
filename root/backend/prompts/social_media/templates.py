# -*- coding: utf-8 -*-
"""
Prompts for the Social Media Content Generation Agent.
"""

SOCIAL_MEDIA_GENERATION_PROMPT = """
{persona_instructions}

Share what you learned from this blog post in a clear, factual way. Focus on explaining the concepts simply and building understanding step-by-step.

Content to share:
<blogpost_markdown>
{blog_content}
</blogpost_markdown>

First, understand what the blog post covers. Wrap your analysis inside <content_breakdown> tags:
1. What main concepts or ideas are explained in the post?
2. What problem does this solve and how does it work?
3. What are the key points or methods described?
4. What practical examples or details are shown?
5. How complex is this - what do you need to know beforehand?
6. Where would someone actually use this in real work?
7. What terms and topics should be included for people to find this content?

Generate social media content in these formats:

1. LinkedIn post:
   - State what you learned directly: "Learned that [concept] works by..."
   - 200-250 words of clear, factual explanation
   - Build the concept step-by-step:
     • What it is (one simple sentence)
     • How it works (break it down clearly)
     • Where you use it (practical applications)
     • Why it matters (the value it provides)
   - Use bullet points to list key components or steps
   - No emotional language or hype words
   - Simple link: "Full post: [link-placeholder]"
   - Use 2-3 relevant technical hashtags
   - Write like you're sharing notes with a colleague

2. X (Twitter) single post:
   - State the key finding: "Found that [concept] does [what]"
   - Maximum 280 characters
   - Focus on the core mechanism or insight
   - Simple, factual language
   - Include 1-2 relevant hashtags
   - Include link if space allows

3. X (Twitter) thread:
   - Create a 4-7 tweet thread building the concept clearly
   - Each tweet under 280 characters
   - Structure:
     • Tweet 1: "Learned how [concept] works. Thread:"
     • Tweet 2: Simple explanation of what it is
     • Tweet 3: How it actually works (key mechanism)
     • Tweet 4: Where/when you use it
     • Tweet 5+: Additional details if needed
     • Final: Link to full post
   - Each tweet builds on the previous one
   - No hype, just clear explanation

4. Newsletter content:
   - Title: "Understanding [concept]" or "How [concept] works"
   - Start with what you learned: "I've been exploring [topic]..."
   - 150-200 words of clear explanation
   - Structure:
     • Opening: What you investigated and why
     • Core concept explained simply
     • Key insight or mechanism
     • Practical application
   - Build understanding progressively
   - No assumptions about prior knowledge
   - Simple link: "Full analysis: [{blog_title}](link-placeholder)"
   - Factual closing, not emotional
   - Include relevant technical tags

Present your content in this format:

<content_breakdown>
[Factual analysis of what the content covers]
</content_breakdown>

<linkedin_post>
[Clear, step-by-step explanation of what you learned]
</linkedin_post>

<x_post>
[Single factual insight]
</x_post>

<x_thread>
1. [Opening statement about what you learned]

2. [Simple explanation of the concept]

3. [How it works]

[Continue building understanding]
</x_thread>

<newsletter_content>
# [Clear, descriptive title]

[What you explored and learned]

[Core concepts explained progressively]

[Full analysis: {blog_title}](link-placeholder)

[Factual closing]

Tags: [Technical tags]
</newsletter_content>

Writing guidelines for clarity:
- State facts directly: "X does Y" not "X can leverage Y"
- Build concepts step-by-step without assuming knowledge
- Use bullet points to break down complex ideas
- Explain technical terms on first use
- Focus on mechanism and application, not emotion
- Use simple, clear language throughout
- No hype words or emotional amplifiers

Language to use:
- "Learned that...", "Found that...", "Discovered..."
- "This works by...", "The mechanism is...", "It does..."
- "Use this for...", "Apply this when...", "Helpful for..."
- Clear transitions: "First...", "Then...", "This means..."

Language to avoid:
- "Mind-blowing", "game-changing", "revolutionary", "amazing"
- "Delve into", "leverage", "utilize", "facilitate"
- "Fascinating", "exciting", "incredible"
- Excessive exclamation points or emojis
- Corporate buzzwords or marketing language
"""

# Twitter Thread Generation Prompt
TWITTER_THREAD_GENERATION_PROMPT = """
{persona_instructions}

Create a Twitter thread that builds understanding of this concept step-by-step. Focus on clear explanation without emotional language.

Content to explain:
<blogpost_markdown>
{blog_content}
</blogpost_markdown>

Create a Twitter thread (4-7 tweets) that explains the concept clearly. Each tweet should:
- Stay under 280 characters
- State facts directly
- Build on the previous tweet
- Focus on how things work and where to use them

**Thread Structure:**

**Tweet 1**: "Learned how [concept] works. Thread:" or "Found that [concept] does [what]. Thread:"

**Tweets 2-5**: Build the explanation:
- What it is (simple definition)
- How it works (core mechanism)
- Where you use it (applications)
- Why it matters (practical value)

**Final Tweet**: Link to full post with brief summary

**Writing Guidelines:**
- State what you learned factually
- Build concept understanding progressively
- No hype or emotional language
- Each tweet should be self-contained but connected
- Use "Thread:" in first tweet as indicator

**Format your response as:**

<x_thread>
1. [Opening tweet with "Thread:" indicator]

2. [What the concept is]

3. [How it works]

[Continue building understanding]

[Final tweet with link: "Full post: [blog-link]"]
</x_thread>

**Thread Topic:** [The concept being explained]

**Core Insight:** [One sentence about the key mechanism or finding]

Focus on clarity: Build understanding step-by-step. Explain the concept, how it works, and where to use it. Keep language simple and direct. No emotional amplifiers or hype.
"""
