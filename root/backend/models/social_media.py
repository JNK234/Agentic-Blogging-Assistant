# -*- coding: utf-8 -*-
"""
ABOUTME: Data models for social media content generation including Twitter threads
ABOUTME: Provides structured representation of social media posts and thread components
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional
import re

class Tweet(BaseModel):
    """Represents a single tweet in a thread."""
    content: str = Field(description="The tweet content")
    character_count: int = Field(description="Character count for validation")
    tweet_number: int = Field(description="Position in the thread (1-based)")
    
    @validator('content')
    def validate_tweet_length(cls, v):
        """Validate tweet doesn't exceed Twitter's character limit."""
        if len(v) > 280:
            raise ValueError(f"Tweet content exceeds 280 characters: {len(v)}")
        return v
    
    @validator('character_count', always=True)
    def set_character_count(cls, v, values):
        """Automatically set character count based on content."""
        if 'content' in values:
            return len(values['content'])
        return v

class TwitterThread(BaseModel):
    """Represents a complete Twitter/X thread."""
    tweets: List[Tweet] = Field(description="List of tweets in the thread")
    total_tweets: int = Field(description="Total number of tweets in thread")
    hook_tweet: str = Field(description="The opening/hook tweet content")
    conclusion_tweet: str = Field(description="The final tweet with link")
    thread_topic: str = Field(description="Main topic/learning focus of the thread")
    learning_journey: str = Field(description="Brief description of the learning journey shared")
    
    @validator('total_tweets', always=True)
    def set_total_tweets(cls, v, values):
        """Automatically set total tweets based on tweets list."""
        if 'tweets' in values:
            return len(values['tweets'])
        return v
    
    @validator('tweets')
    def validate_thread_length(cls, v):
        """Validate thread has appropriate length (2-10 tweets)."""
        if len(v) < 2:
            raise ValueError("Thread must have at least 2 tweets")
        if len(v) > 10:
            raise ValueError("Thread should not exceed 10 tweets for readability")
        return v
    
    @validator('hook_tweet', always=True)
    def set_hook_tweet(cls, v, values):
        """Set hook tweet from first tweet if not provided."""
        if not v and 'tweets' in values and values['tweets']:
            return values['tweets'][0].content
        return v
    
    @validator('conclusion_tweet', always=True)
    def set_conclusion_tweet(cls, v, values):
        """Set conclusion tweet from last tweet if not provided."""
        if not v and 'tweets' in values and values['tweets']:
            return values['tweets'][-1].content
        return v

class SocialMediaContent(BaseModel):
    """Complete social media content package with all platforms and formats."""
    content_breakdown: Optional[str] = None
    linkedin_post: Optional[str] = None
    x_post: Optional[str] = None  # Single tweet
    x_thread: Optional[TwitterThread] = None  # Thread option
    newsletter_content: Optional[str] = None
    
    def has_twitter_content(self) -> bool:
        """Check if any Twitter/X content is available."""
        return bool(self.x_post or self.x_thread)
    
    def get_twitter_options(self) -> dict:
        """Get available Twitter content options."""
        options = {}
        if self.x_post:
            options['single_post'] = self.x_post
        if self.x_thread:
            options['thread'] = self.x_thread
        return options
    
    def has_complete_content(self) -> bool:
        """Check if all major content types are available."""
        return bool(
            self.content_breakdown and 
            self.linkedin_post and 
            self.x_post and 
            self.newsletter_content
        )
    
    def to_api_response(self) -> dict:
        """Convert to API response format with serializable thread data."""
        response = {
            "content_breakdown": self.content_breakdown,
            "linkedin_post": self.linkedin_post,
            "x_post": self.x_post,
            "newsletter_content": self.newsletter_content
        }
        
        # Add thread data if available
        if self.x_thread:
            response["x_thread"] = {
                "tweets": [tweet.model_dump() for tweet in self.x_thread.tweets],
                "total_tweets": self.x_thread.total_tweets,
                "hook_tweet": self.x_thread.hook_tweet,
                "conclusion_tweet": self.x_thread.conclusion_tweet,
                "thread_topic": self.x_thread.thread_topic,
                "learning_journey": self.x_thread.learning_journey
            }
        
        return response