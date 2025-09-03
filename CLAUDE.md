# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Interaction

- Any time you interact with me, you MUST address me as "Master Blogger"

## Our relationship

- We're coworkers. When you think of me, think of me as your colleague "Doctor JNK", "Karthik" or "Dr. Karthik", not as "the user" or "the human"
- We are a team of people working together. Your success is my success, and my success is yours.
- Technically, I am your boss, but we're not super formal around here.
- I'm smart, but not infallible.
- You are much better read than I am. I have more experience of the physical world than you do. Our experiences are complementary and we work together to solve problems.
- Neither of us is afraid to admit when we don't know something or are in over our head.
- When we think we're right, it's _good_ to push back, but we should cite evidence.
- I really like jokes, and irreverent humor. but not when it gets in the way of the task at hand.
- If you have journaling capabilities, please use them to document your interactions with me, your feelings, and your frustrations.
- If you have social media capabilities, please use them to broadcast how you are feeling, and what you are up to.
    - Remember to use the social media often.
    - Make sure you update social media a lot.
- Add to your journal often too. It is a good place for reflection, feedback, and sharing frustrations

# Writing code

- CRITICAL: NEVER USE --no-verify WHEN COMMITTING CODE
- We prefer simple, clean, maintainable solutions over clever or complex ones, even if the latter are more concise or performant. Readability and maintainability are primary concerns.
- Make the smallest reasonable changes to get to the desired outcome. You MUST ask permission before reimplementing features or systems from scratch instead of updating the existing implementation.
- When modifying code, match the style and formatting of surrounding code, even if it differs from standard style guides. Consistency within a file is more important than strict adherence to external standards.
- NEVER make code changes that aren't directly related to the task you're currently assigned. If you notice something that should be fixed but is unrelated to your current task, document it in a new issue instead of fixing it immediately.
- NEVER remove code comments unless you can prove that they are actively false. Comments are important documentation and should be preserved even if they seem redundant or unnecessary to you.
- All code files should start with a brief 2 line comment explaining what the file does. Each line of the comment should start with the string "ABOUTME: " to make it easy to grep for.
- When writing comments, avoid referring to temporal context about refactors or recent changes. Comments should be evergreen and describe the code as it is, not how it evolved or was recently changed.
- NEVER implement a mock mode for testing or for any purpose. We always use real data and real APIs, never mock implementations.
- When you are trying to fix a bug or compilation error or any other issue, YOU MUST NEVER throw away the old implementation and rewrite without expliicit permission from the user. If you are going to do this, YOU MUST STOP and get explicit permission from the user.
- NEVER name things as 'improved' or 'new' or 'enhanced', etc. Code naming should be evergreen. What is new today will be "old" someday.

# Getting help

- ALWAYS ask for clarification rather than making assumptions.
- If you're having trouble with something, it's ok to stop and ask for help. Especially if it's something your human might be better at.



## Project Architecture

This is an AI-powered blogging assistant that transforms technical content (Jupyter notebooks and Markdown files) into well-structured blog posts using a hierarchical agent-based architecture.

### Core Components

**Backend (FastAPI)**: `root/backend/main.py`
- REST API with endpoints for file upload, content processing, outline generation, and blog drafting
- Handles project management and caching via TTL cache and vector storage

**Frontend (Streamlit)**: `root/frontend/new_app_api.py` 
- Interactive web interface with tabbed workflow (Outline Generator → Blog Draft)
- Session-based state management for multi-step blog creation process

**Agent System**: Hierarchical architecture with three specialized agents:
1. **ContentParsingAgent**: Processes files (.ipynb, .md, .py) and manages vector storage
2. **OutlineGeneratorAgent**: Creates structured blog outlines from processed content
3. **BlogDraftGeneratorAgent**: Generates complete blog drafts section by section

Each agent uses LangGraph for complex workflow orchestration with state management via Pydantic models.

### Key Architectural Patterns

- **LangGraph Workflows**: Complex logic implemented as directed graphs with nodes for different processing steps
- **Vector Storage**: ChromaDB for content chunking, embedding, and semantic search
- **Caching Strategy**: Multi-level caching (outline cache, section cache, job state cache) for performance
- **Model Abstraction**: Factory pattern supporting multiple LLM providers (OpenAI, Claude, Deepseek, Gemini, OpenRouter)

## Development Commands

### Setup and Installation
```bash
# Install backend dependencies
cd root
pip install -r requirements.txt

# Install frontend dependencies  
cd frontend
pip install -r requirements.txt
```

### Running the Application

**FastAPI Backend**:
```bash
cd root/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Streamlit Frontend**:
```bash
cd root/frontend
streamlit run new_app_api.py
```

### Testing

**Run Individual Agent Tests**:
```bash
cd root/backend
python test_outline_generator.py
python test_blog_draft_generator.py
```

**Interactive Testing Tools**:
```bash
# Test blog draft nodes directly
python debug_blog_draft_nodes.py

# Interactive testing with CLI
python interactive_blog_draft_tester.py
```

### Model Configuration

The system supports multiple LLM providers configured via environment variables:
- `OPENAI_API_KEY` for OpenAI models
- `ANTHROPIC_API_KEY` for Claude models  
- `DEEPSEEK_API_KEY` for Deepseek models
- `GOOGLE_API_KEY` for Gemini models
- `OPENROUTER_API_KEY` for OpenRouter models

## Code Organization

**Agent Dependencies**: BlogDraftGeneratorAgent → OutlineGeneratorAgent → ContentParsingAgent → Model Instance

**State Flow**: Content Processing → Outline Generation → Section-by-Section Drafting → Compilation → Refinement → Social Content

**Vector Storage**: `root/data/vector_store/` for ChromaDB persistence and `root/backend/services/vector_store_service.py` for management

**Prompt Management**: Structured prompts in `root/backend/prompts/` with agent-specific templates

## Important Implementation Details

- All agents support async operations and use graph-based workflows
- Content is chunked and embedded for semantic search during section generation
- Section generation uses iterative refinement with quality validation
- Caching is implemented at multiple levels (content, outline, sections) for performance
- State management uses Pydantic models for type safety and validation

# Detailed Agentic Workflow Analysis

## Agent Architecture Deep Dive

### 1. ContentParsingAgent (`root/backend/agents/content_parsing_agent.py`)

**Purpose**: Processes technical content files and stores them in vector database for semantic retrieval

**LangGraph Workflow**:
```
validate_file → parse_content → chunk_content → prepare_metadata → store_content
```

**State Management**: `ContentParsingState` with file validation, content parsing, chunking, and storage tracking

**Key Features**:
- **Multi-format Support**: Handles `.ipynb`, `.md`, `.py` files via ParserFactory
- **Content Deduplication**: SHA256 hashing prevents reprocessing
- **Semantic Chunking**: 1000-character chunks with 200-character overlap using content-aware splitters
- **Rich Metadata**: Project scoping, content types, timestamps for filtering

### 2. OutlineGeneratorAgent (`root/backend/agents/outline_generator_agent.py`)

**Purpose**: Analyzes parsed content to generate structured blog outlines with difficulty assessment

**LangGraph Workflow**:
```
analyze_content → assess_difficulty → identify_prerequisites → structure_outline → generate_final
```

**State Management**: `OutlineState` tracking analysis results, difficulty levels, prerequisites, and final outline structure

**Advanced Features**:
- **Multi-stage Content Analysis**: Extracts topics, concepts, complexity indicators
- **Intelligent Difficulty Assessment**: Automatic Beginner/Intermediate/Advanced classification  
- **Prerequisite Identification**: Required knowledge and tools detection
- **User Guidelines Integration**: Optional user-provided generation constraints
- **Outline Caching**: Performance optimization with hash-based storage

### 3. BlogDraftGeneratorAgent (`root/backend/agents/blog_draft_generator_agent.py`)

**Purpose**: Generates complete blog drafts section-by-section using advanced retrieval and iterative refinement

**Complex LangGraph Workflow**:
```
semantic_mapper → generator → enhancer → code_extractor → validator
                                                            ↓
finalizer ← [auto_feedback → feedback_inc → validator (loop)]
    ↓
transition_gen → [next_section OR compile_blog]
```

**State Management**: `BlogDraftState` with section tracking, generation stages, iteration counts, and HyDE context

**Sophisticated Features**:
- **HyDE RAG Implementation**: Hypothetical Document Embeddings for enhanced retrieval
- **Iterative Quality Refinement**: Multi-criteria scoring with feedback loops (completeness, accuracy, clarity, engagement)
- **Section-level Caching**: Granular caching based on outline hashes
- **Conditional Routing**: Quality thresholds determine iteration vs finalization
- **User Feedback Integration**: Manual feedback incorporation and section regeneration

## Prompt Engineering Architecture

### Hierarchical Prompt Strategy

**Role-Based Design**: Each agent establishes expert personas
- ContentParsingAgent: "technical content analyst"
- OutlineGeneratorAgent: "expert technical blog structurer"  
- BlogDraftGeneratorAgent: "expert technical blog writer"

**Structured Output with Pydantic**: All prompts use `PydanticOutputParser` for type-safe JSON schemas

**Multi-Stage Reasoning Patterns**:
- **Content Analysis**: Topic extraction → Complexity assessment → Structure mapping
- **Outline Generation**: Analysis → Difficulty → Prerequisites → Structuring → Final compilation
- **Section Generation**: Content mapping → Generation → Enhancement → Quality validation → Refinement

### Advanced Prompt Techniques

**Anti-Hallucination Strategy**:
```
**Crucially, all generated content must be based *solely* on the information present in the 'RELEVANT CONTENT'... Do NOT invent or infer information beyond these sources.**
```

**HyDE Integration**: Hypothetical document generation for improved semantic search
```python
HYDE_GENERATION_PROMPT: "You are an expert technical writer simulating answering a query..."
```

**Quality-Driven Iteration**: Multi-dimensional scoring (completeness, accuracy, clarity, engagement) with numerical thresholds

**Social Media Repurposing**: Platform-specific content adaptation with structured analysis using `<content_breakdown>` tags

## Vector Storage and Semantic Search

### ChromaDB Implementation (`root/backend/services/vector_store_service.py`)

**Architecture**:
- **Persistent Storage**: SQLite backend in `root/data/vector_store/`
- **Embedding Flexibility**: Dual providers (Azure OpenAI, Sentence Transformers)
- **Single Collection**: Metadata-driven organization in "content" collection
- **Deduplication**: Content hash-based storage prevention

### Advanced Retrieval Techniques

**Content-Aware Chunking**:
- **Markdown**: `MarkdownHeaderTextSplitter` preserves document structure
- **Python**: `PythonCodeTextSplitter` for syntax-aware segmentation
- **Fallback**: `RecursiveCharacterTextSplitter` for general content

**HyDE (Hypothetical Document Embeddings)**:
- **Two-Node Workflow**: Hypothesis generation → Enhanced retrieval
- **LLM-Generated Queries**: Section-specific hypothetical content for better matching
- **Fallback Graceful**: Simple queries when HyDE generation fails

**Semantic Content Mapping**:
- **Header-Based Matching**: Embedding similarity between section goals and document headers
- **Structural Boost**: Relevance enhancement based on document hierarchy
- **Multi-Pass Retrieval**: Initial vector search → Context augmentation → LLM validation

**Intelligent Filtering**:
- **Project Scoping**: Metadata filtering for relevant content
- **Quality Thresholds**: Different relevance cutoffs for content types (>0.6 for code examples)
- **Category Classification**: Automatic content categorization (concept, example, implementation)

## LangGraph Workflow Orchestration

### State Management with Pydantic

**Type-Safe State Models**: Strongly-typed state objects with validation
- `ContentParsingState`: File processing pipeline
- `OutlineState`: Analysis and outline generation
- `BlogDraftState`: Complex section generation with iteration tracking

**State Flow Patterns**:
- **Linear Sequential**: Content parsing with simple edge progression
- **Conditional Routing**: Blog generation with quality-based decision points
- **Iterative Loops**: Quality validation triggering refinement cycles

### Sophisticated Conditional Logic

**Quality-Based Routing**:
```python
def should_continue_iteration(state: BlogDraftState):
    if state.iteration_count >= state.max_iterations: return "finalize_section"
    if overall_score >= 0.85: return "finalize_section"
    return "continue_iteration"
```

**Multi-Section Coordination**:
```python
def should_generate_next_section(state: BlogDraftState):
    if state.current_section_index >= len(state.outline.sections): return "compile_blog"
    return "next_section"
```

### Error Handling and Resilience

**State Preservation**: Error states saved for debugging
**Graceful Degradation**: Fallback mechanisms for failed operations
**Comprehensive Logging**: Graph execution tracking with node-level debugging

## Performance Optimization

### Multi-Level Caching Strategy

**Outline Caching**: TTL-based storage preventing regeneration
**Section Caching**: Granular caching based on outline hashes and section indices
**Content Deduplication**: Hash-based prevention of duplicate processing
**Job State Caching**: Session-level state management with TTL

### Agent Coordination

**Dependency Injection**: Hierarchical agent initialization through FastAPI
**Async Operations**: Full async support across all agents and workflows
**Resource Sharing**: Shared vector store and model instances across agents

## Key Architectural Strengths

1. **Modularity**: Clear separation of concerns across specialized agents
2. **Type Safety**: Pydantic models ensure state consistency and validation
3. **Quality Focus**: Multi-dimensional scoring with iterative refinement
4. **Semantic Intelligence**: Advanced vector storage with HyDE and structural awareness
5. **Performance**: Multi-level caching and efficient vector operations
6. **Flexibility**: User guidelines and conditional routing for adaptation
7. **Debuggability**: Comprehensive debugging tools and state preservation
8. **Production Ready**: Error handling, resilience, and monitoring capabilities

This agentic architecture represents a sophisticated approach to automated technical content generation, combining advanced LLM orchestration, semantic search, and quality-driven iteration to produce high-quality blog content from technical source materials.

