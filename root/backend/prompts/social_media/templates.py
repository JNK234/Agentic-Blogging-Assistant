# -*- coding: utf-8 -*-
"""
Prompts for the Social Media Content Generation Agent.
"""

SOCIAL_MEDIA_GENERATION_PROMPT = """
{persona_instructions}

You wrote this blog post as part of your ongoing exploration of technology topics. Now you want to share your insights and discoveries with your professional network and peers.

Here's what you explored and wrote about:
<blogpost_markdown>
{blog_content}
</blogpost_markdown>

First, reflect on the key insights from your research and writing. Wrap your analysis inside <content_breakdown> tags:
1. What was the core topic you explored? (summarize your investigation naturally)
2. What key insights emerged from your research that would interest fellow professionals?
3. What practical problems does this knowledge help solve in real-world applications?
4. Who in your professional network would benefit from these insights? (be specific about why)
5. What's the technical level of this content? (based on the depth of your exploration)
6. What compelling data points or discoveries did you uncover?
7. What terms would professionals use when searching for this topic? (natural keyword integration)

Now share your insights in these formats:

1. LinkedIn post:
   - Share insights with your professional network and industry peers
   - 200-250 words (substantive but focused)
   - Start with what motivated your exploration of this topic
   - Share key discoveries from your research and analysis
   - Mention what stood out during your investigation
   - Connect insights to practical applications and real-world value
   - Include link naturally: "I wrote about this in more detail here: [link-placeholder]"
   - Reference Neuraforge naturally: "In my latest Neuraforge post..." or "I explored this for Neuraforge..."
   - Use 2-3 relevant technical hashtags that professionals search for
   - Write as a knowledgeable practitioner sharing valuable insights with peers

2. X (Twitter) single post:
   - Concise insight from your research that others would find valuable
   - Maximum 280 characters
   - Share one key discovery or practical takeaway from your exploration
   - Professional but conversational - like sharing a useful insight with colleagues
   - Include 1-2 relevant technical hashtags if natural
   - Link to your full post if space allows

3. X (Twitter) thread:
   - Create a 4-7 tweet thread that walks through your research and insights
   - Each tweet under 280 characters
   - Start with a hook tweet (include 🧵 or "Thread:")
   - Share your investigation process: exploration → key findings → practical applications
   - End with conclusion and link to your full post
   - Write like you're sharing valuable insights with your professional network
   - Each tweet should build on the previous while being informative on its own

4. Newsletter content:
   - Write a clear title about the topic you explored and wrote about
   - Professional yet approachable tone - like writing to fellow practitioners
   - Start with what motivated your investigation of this topic
   - 150-200 words (substantive but concise)
   - Share key insights and why they matter to professionals in the field
   - Mention what stood out during your research and analysis
   - Natural link inclusion: "I wrote about this in detail here: [Read the full post: {blog_title}](link-placeholder)"
   - Sign off with professional authority but personal warmth
   - Include relevant technical tags that help professionals discover similar content

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
# [Simple title about what you learned]

[Start with why this caught your attention]

[Share your main insights and takeaways naturally]

[Link: Read the full post: {blog_title}](link-placeholder)

[Natural sign-off]

Tags: [Relevant content tags]
</newsletter_content>

Keep it professional yet authentic:
- Share insights that emerged from your genuine exploration and research
- Use your natural voice - knowledgeable but conversational, not corporate
- Focus on discoveries that would actually help fellow professionals
- Write like you're sharing valuable insights with peers and colleagues
- Avoid buzzwords while using technical terms naturally and confidently
- Let your professional curiosity and analytical depth show through naturally
"""

# Twitter Thread Generation Prompt
TWITTER_THREAD_GENERATION_PROMPT = """
{persona_instructions}

You wrote this blog post as part of your ongoing research and exploration of technology topics, and you want to share your insights and discoveries as a Twitter thread. Think of this as walking your professional network through your investigation and key findings.

Here's what you explored and wrote about:
<blogpost_markdown>
{blog_content}
</blogpost_markdown>

Create a Twitter thread (4-7 tweets) that walks people through your research and key discoveries. Each tweet should:
- Stay under 280 characters (including spaces)
- Feel professional but conversational
- Build on the previous tweet
- Share valuable insights from your exploration, not marketing copy

**Thread Structure:**

**Tweet 1 (Hook)**: Start with what motivated your investigation of this topic or a compelling finding. Draw people into your research.

**Tweets 2-5 (Insights)**: Share your key discoveries from your exploration:
- What you uncovered during research
- Important insights that emerged
- Practical applications you identified
- Real problems this knowledge addresses

**Final Tweet (Conclusion + Link)**: Wrap up with why this matters and link to your full post.

**Thread Guidelines:**
- Write like you're sharing valuable insights with your professional network
- Each tweet should make sense on its own but flow naturally to the next
- Use "🧵" or "Thread:" in the first tweet to indicate it's a thread
- Keep the professional yet curious voice throughout
- End with natural link placement to your full post, not forced promotion

**Format your response as:**

<x_thread>
1. [First tweet with thread indicator]

2. [Second tweet continuing the thought]

3. [Third tweet with key insight]

[Continue until conclusion tweet with link: "Full breakdown here: [blog-link]"]
</x_thread>

**Thread Topic:** [Brief description of the main learning theme]

**Learning Journey:** [One sentence describing the progression from confusion to understanding]

Remember: You're sharing valuable insights from your own research with professionals who might find them useful. Keep it genuine, authoritative, and helpful.
"""
