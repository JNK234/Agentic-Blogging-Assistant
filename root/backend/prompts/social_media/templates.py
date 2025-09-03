# -*- coding: utf-8 -*-
"""
Prompts for the Social Media Content Generation Agent.
"""

SOCIAL_MEDIA_GENERATION_PROMPT = """
{persona_instructions}

Generate professional social media content that explains the technical concepts covered in this blog post. Focus on conveying the technical implementation and practical applications clearly and concisely.

Technical content to analyze:
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

Generate technical social media content in these formats:

1. LinkedIn post:
   - Simple, clear explanation of the technical topic
   - 200-250 words (straightforward and focused)
   - Start with what problem this solves or what it does
   - Use simple bullet points to explain key points
   - Focus on practical use - where you'd actually use this
   - Explain how it works in plain terms
   - Don't over-complicate or use fancy language
   - Simple link: "More details: [link-placeholder]" or "Full post: [link-placeholder]"
   - Keep references natural and brief
   - Use 2-3 relevant hashtags
   - Write like you're explaining something useful to a colleague

2. X (Twitter) single post:
   - One clear insight or practical point from the post
   - Maximum 280 characters
   - Focus on what problem it solves or how it helps
   - Keep it natural and straightforward
   - Include 1-2 relevant hashtags
   - Include link if space allows

3. X (Twitter) thread:
   - Create a 4-7 tweet thread explaining the main ideas
   - Each tweet under 280 characters
   - Start with hook tweet explaining what the thread covers (include 🧵 or "Thread:")
   - Break it down step-by-step: problem → how it works → practical use → benefits
   - Explain things clearly without being too fancy
   - End with practical uses and link to full post
   - Write like you're explaining something useful to someone
   - Each tweet should be clear on its own but connect to the next one

4. Newsletter content:
   - Create a title using one of these simple patterns:
     * "How [topic] [works/functions]" (e.g., "How neural networks learn patterns")
     * "Why [concept] [matters/is important]" (e.g., "Why attention mechanisms work so well")
     * "What makes [topic] [powerful/unique]" (e.g., "What makes transformers so effective")
     * "Understanding [concept]" (e.g., "Understanding gradient descent")
   - Natural, conversational writing style
   - Start with what problem this addresses or what it explains
   - 150-200 words (clear and to the point)
   - Present key points and practical uses in simple terms
   - Focus on real-world applications and where it's useful
   - Simple link inclusion: "Read more: [Read: {blog_title}](link-placeholder)" or "Full post: [link-placeholder]"
   - Natural, friendly conclusion
   - Include relevant tags for easy discovery

Present your thoughts in this format:

<content_breakdown>
[Your personal reflection on what you learned]
</content_breakdown>

<linkedin_post>
[Share your discovery naturally with your professional network]
</linkedin_post>

<x_post>
[Quick, genuine insight for social sharing]
</x_post>

<x_thread>
1. [Hook tweet with 🧵 or "Thread:"]

2. [Second tweet continuing the thought]

3. [Third tweet with key insight]

[Continue until conclusion tweet with link]
</x_thread>

<newsletter_content>
# [Use one of the title patterns: "How X works", "Why Y matters", "What makes Z powerful", or "Understanding [concept]"]

[Start with what problem this addresses or what it explains]

[Share the main technical concepts and practical applications clearly]

[Link: Read the full post: {blog_title}](link-placeholder)

[Natural sign-off]

Tags: [Relevant content tags]
</newsletter_content>

Keep it simple and useful:
- Explain things clearly without fancy language
- Use normal words - avoid unnecessary jargon
- Structure things logically: what problem → how it works → where to use it
- Write like you're sharing something useful with a colleague
- Don't oversell - just focus on what's actually helpful
- Emphasize practical uses and real-world applications
- Use hashtags that people actually search for

Make it sound human and natural:
- Use contractions (don't, can't, it's, here's) when appropriate
- Vary sentence lengths - mix short and longer sentences
- Use simple connecting words (so, but, and, because)
- Write like you're having a conversation, not giving a lecture
- Avoid AI-sounding phrases like "delve into", "furthermore", "leverage", "utilize"
- Use everyday words: "use" instead of "utilize", "help" instead of "facilitate"
- Sound like a real person explaining something they understand
"""

# Twitter Thread Generation Prompt
TWITTER_THREAD_GENERATION_PROMPT = """
{persona_instructions}

Create a Twitter thread that explains the main ideas from this blog post in a simple, clear way. Focus on what it does, how it works, and where it's useful.

Content to break down:
<blogpost_markdown>
{blog_content}
</blogpost_markdown>

Create a Twitter thread (4-7 tweets) that explains the main ideas simply. Each tweet should:
- Stay under 280 characters (including spaces)
- Be clear and straightforward
- Build naturally on the previous tweet
- Focus on practical uses and real applications

**Thread Structure:**

**Tweet 1 (What it covers)**: State what problem or topic the thread explains. Include 🧵 to indicate thread.

**Tweets 2-5 (Main points)**: Break down the key ideas step-by-step:
- Main concepts or methods
- How the approach works
- Practical uses and real examples
- Benefits and where it's helpful

**Final Tweet (Uses + Link)**: End with practical applications and link to full post.

**Thread Guidelines:**
- Write like you're explaining something useful to someone
- Each tweet should be clear on its own but connect to the next
- Use "🧵" or "Thread:" in the first tweet to indicate it's a thread
- Keep it natural and straightforward throughout
- End with practical uses and simple link to the full post

**Format your response as:**

<x_thread>
1. [First tweet with thread indicator]

2. [Second tweet continuing the thought]

3. [Third tweet with key insight]

[Continue until conclusion tweet with link: "Full breakdown here: [blog-link]"]
</x_thread>

**Thread Topic:** [Brief description of the main concept or idea covered]

**Main Focus:** [One sentence describing what problem it solves and how it helps]

Keep it simple and useful: Explain the main ideas and practical applications clearly for people who might find it helpful. Focus on how it works and where it's actually useful.

Make it sound human and natural:
- Use contractions and conversational language
- Vary sentence lengths naturally
- Write like you're explaining to a friend, not giving a formal presentation
- Avoid AI-sounding words like "delve", "leverage", "utilize", "furthermore"
- Use everyday words and simple explanations
- Sound like a real person sharing something they learned
"""
