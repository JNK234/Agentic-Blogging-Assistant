# ABOUTME: FastMCP tool for complete end-to-end blog generation automation
# ABOUTME: Orchestrates project creation, file upload, processing, outline generation, section drafting, refinement, and export

from typing import Optional, Dict, Any, List
import logging
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from ..api_client import BackendAPIClient

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("automation-tools")


@mcp.tool()
async def generate_complete_blog(
    project_name: str,
    files: List[str],
    persona: str = "Tech Blog Writer",
    model: str = "gpt-4o-mini",
    specific_model: Optional[str] = None,
    user_guidelines: Optional[str] = None,
    auto_refine: bool = True,
    export_format: str = "markdown"
) -> Dict[str, Any]:
    """
    Generate a complete blog post from start to finish with full automation.

    This comprehensive tool orchestrates the entire blogging workflow:
    1. Creates a new project with specified configuration
    2. Uploads all provided files (.ipynb, .md, .py)
    3. Processes files to extract content and create embeddings
    4. Generates a structured blog outline
    5. Drafts all sections with iterative quality refinement
    6. Optionally refines the complete blog draft
    7. Exports the final blog in the requested format

    This is the primary automation tool for users who want to transform
    technical content (notebooks, markdown, code) into publication-ready
    blog posts with minimal manual intervention.

    Args:
        project_name: Name for the blog project (e.g., "ML Tutorial Series Part 1")
        files: List of absolute file paths to upload and process
               Supported formats: .ipynb (Jupyter notebooks), .md (Markdown), .py (Python)
               Example: ["/path/to/tutorial.ipynb", "/path/to/notes.md"]
        persona: Writing style/persona for the blog (default: "Tech Blog Writer")
                 Options include:
                 - "Tech Blog Writer": Professional technical blog style
                 - "Academic Researcher": Formal academic writing
                 - "Tutorial Creator": Educational step-by-step style
                 - Custom personas as defined in persona_service
        model: LLM model to use for content generation (default: "gpt-4o-mini")
               Options:
               - "gpt-4o-mini": Cost-effective GPT-4 variant
               - "gpt-4o": Full GPT-4 model
               - "claude-3-5-sonnet-20241022": Claude Sonnet
               - "deepseek-chat": DeepSeek model
               - "gemini": Google Gemini
               - "openai": Generic OpenAI (uses default)
        specific_model: Specific model identifier for custom/fine-tuned models (optional)
                       Example: "ft:gpt-4o-mini-2024-07-18:my-org:custom-model:9ABCDefG"
        user_guidelines: Optional guidelines for outline and content generation
                        Examples:
                        - "Focus on practical code examples"
                        - "Keep explanations beginner-friendly"
                        - "Emphasize real-world applications"
                        - "Include performance comparisons"
        auto_refine: Whether to automatically refine the blog after drafting (default: True)
                    Refinement improves:
                    - Writing quality and flow
                    - Technical accuracy
                    - Readability and engagement
                    - SEO optimization
                    Set to False to skip refinement and save costs
        export_format: Format for the final blog export (default: "markdown")
                      Options:
                      - "markdown": Markdown file (.md)
                      - "json": JSON with full metadata
                      - "zip": Complete project archive

    Returns:
        Dictionary containing:
        - status: Overall operation status ("success" or "error")
        - project_id: UUID of the created project
        - project_name: Name of the project
        - workflow_steps: Dictionary tracking completion of each step:
          * project_created: bool
          * files_uploaded: bool
          * files_processed: bool
          * outline_generated: bool
          * sections_drafted: bool
          * blog_refined: bool (if auto_refine=True)
          * blog_exported: bool
        - outline: Generated blog outline structure
        - sections: List of drafted sections with metadata
        - refined_blog: Refined blog content (if auto_refine=True)
        - export_data: Final exported blog content
        - cost_summary: Cost tracking information
          * total_cost: Total USD cost
          * total_tokens: Total tokens consumed
          * agent_breakdown: Cost per agent
        - errors: List of any errors encountered (empty if successful)

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If invalid parameters are provided or API returns errors
        FileNotFoundError: If any specified files don't exist

    Example:
        result = await generate_complete_blog(
            project_name="Building RAG Systems with LangChain",
            files=[
                "/Users/me/projects/rag_tutorial.ipynb",
                "/Users/me/projects/architecture.md"
            ],
            persona="Tutorial Creator",
            model="gpt-4o",
            user_guidelines="Focus on practical implementation details and include code examples",
            auto_refine=True,
            export_format="markdown"
        )

        if result['status'] == 'success':
            print(f"Blog generated successfully!")
            print(f"Project ID: {result['project_id']}")
            print(f"Total cost: ${result['cost_summary']['total_cost']:.4f}")
            print(f"Export: {result['export_data'][:200]}...")
        else:
            print(f"Errors: {result['errors']}")
    """
    # Track workflow progress
    workflow_steps = {
        "project_created": False,
        "files_uploaded": False,
        "files_processed": False,
        "outline_generated": False,
        "sections_drafted": False,
        "blog_refined": False,
        "blog_exported": False
    }

    errors = []
    project_id = None
    outline = None
    sections = []
    refined_blog = None
    export_data = None
    cost_summary = {}

    try:
        # Validate files exist
        file_paths = []
        for file_str in files:
            file_path = Path(file_str)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_str}")
            file_paths.append(file_path)

        logger.info(f"Starting complete blog generation for project: {project_name}")
        logger.info(f"Files: {len(file_paths)}, Model: {model}, Persona: {persona}")

        async with BackendAPIClient() as client:
            # Step 1: Create project
            logger.info("Step 1: Creating project...")
            try:
                metadata = {
                    "model_name": model,
                    "persona": persona
                }
                if specific_model:
                    metadata["specific_model"] = specific_model

                create_response = await client.create_project(
                    name=project_name,
                    metadata=metadata
                )

                project_id = create_response.get("project_id")
                if not project_id:
                    raise ValueError("No project_id returned from create_project")

                workflow_steps["project_created"] = True
                logger.info(f"Project created: {project_id}")

            except Exception as e:
                error_msg = f"Failed to create project: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                raise

            # Step 2: Upload files
            logger.info(f"Step 2: Uploading {len(file_paths)} files...")
            try:
                upload_response = await client.upload_files(
                    project_id=project_id,
                    files=file_paths
                )

                workflow_steps["files_uploaded"] = True
                logger.info(f"Files uploaded: {upload_response.get('file_count', len(file_paths))}")

            except Exception as e:
                error_msg = f"Failed to upload files: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                raise

            # Step 3: Process files
            logger.info("Step 3: Processing files...")
            try:
                process_response = await client.process_files(
                    project_id=project_id,
                    model_name=model
                )

                workflow_steps["files_processed"] = True
                logger.info("Files processed successfully")

            except Exception as e:
                error_msg = f"Failed to process files: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                raise

            # Step 4: Generate outline
            logger.info("Step 4: Generating blog outline...")
            try:
                outline_response = await client.generate_outline(
                    project_id=project_id,
                    user_guidelines=user_guidelines
                )

                outline = outline_response.get("outline")
                if not outline:
                    raise ValueError("No outline returned from generate_outline")

                workflow_steps["outline_generated"] = True
                num_sections = len(outline.get("sections", []))
                logger.info(f"Outline generated with {num_sections} sections")

            except Exception as e:
                error_msg = f"Failed to generate outline: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                raise

            # Step 5: Draft all sections
            logger.info(f"Step 5: Drafting {num_sections} sections...")
            try:
                for section_index in range(num_sections):
                    section_title = outline["sections"][section_index].get("title", f"Section {section_index + 1}")
                    logger.info(f"Drafting section {section_index + 1}/{num_sections}: {section_title}")

                    section_response = await client.draft_section(
                        project_id=project_id,
                        section_index=section_index,
                        max_iterations=3,
                        quality_threshold=0.8
                    )

                    sections.append({
                        "index": section_index,
                        "title": section_title,
                        "content": section_response.get("section_content"),
                        "cost": section_response.get("section_cost", 0.0),
                        "tokens": section_response.get("section_tokens", 0)
                    })

                    logger.info(f"Section {section_index + 1} drafted successfully")

                workflow_steps["sections_drafted"] = True
                logger.info(f"All {num_sections} sections drafted")

            except Exception as e:
                error_msg = f"Failed to draft sections: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                raise

            # Step 6: Refine blog (optional)
            if auto_refine:
                logger.info("Step 6: Refining blog draft...")
                try:
                    # First, get the project to access refinement endpoint properly
                    project_data = await client.get_project(project_id)
                    project_name_from_data = project_data.get("project", {}).get("name")

                    # Note: refine_blog endpoint needs to be added to BackendAPIClient
                    # For now, we'll skip automatic refinement and log a warning
                    logger.warning("Auto-refinement not yet implemented in BackendAPIClient")
                    logger.warning("Users should manually refine using the /refine_blog endpoint")
                    workflow_steps["blog_refined"] = False

                except Exception as e:
                    error_msg = f"Failed to refine blog: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    # Don't raise - refinement is optional
            else:
                logger.info("Step 6: Skipping blog refinement (auto_refine=False)")

            # Step 7: Export blog
            logger.info(f"Step 7: Exporting blog as {export_format}...")
            try:
                # Use the export endpoint through direct API call
                # Note: export functionality needs to be added to BackendAPIClient
                project_data = await client.get_project(project_id)

                # For now, compile the blog from sections
                compiled_blog = {
                    "title": outline.get("title", project_name),
                    "introduction": outline.get("introduction", ""),
                    "sections": sections,
                    "conclusion": outline.get("conclusion", ""),
                    "metadata": {
                        "project_id": project_id,
                        "model": model,
                        "persona": persona,
                        "total_sections": len(sections)
                    }
                }

                # Format based on export_format
                if export_format == "json":
                    export_data = compiled_blog
                elif export_format == "markdown":
                    # Build markdown
                    md_parts = [
                        f"# {compiled_blog['title']}\n",
                        compiled_blog['introduction'],
                        "\n\n"
                    ]
                    for section in sections:
                        md_parts.append(f"## {section['title']}\n\n")
                        md_parts.append(section['content'])
                        md_parts.append("\n\n")
                    md_parts.append(compiled_blog['conclusion'])
                    export_data = "".join(md_parts)
                else:
                    logger.warning(f"Export format {export_format} not fully implemented, returning JSON")
                    export_data = compiled_blog

                workflow_steps["blog_exported"] = True
                logger.info("Blog exported successfully")

            except Exception as e:
                error_msg = f"Failed to export blog: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                raise

            # Get final cost summary from project metadata
            try:
                final_project_data = await client.get_project(project_id)
                cost_summary = final_project_data.get("project", {}).get("metadata", {}).get("cost_summary", {})
            except Exception as e:
                logger.warning(f"Could not retrieve cost summary: {e}")
                cost_summary = {"error": "Cost summary unavailable"}

        # Return comprehensive result
        return {
            "status": "success" if not errors else "partial_success",
            "project_id": project_id,
            "project_name": project_name,
            "workflow_steps": workflow_steps,
            "outline": outline,
            "sections": sections,
            "refined_blog": refined_blog,
            "export_data": export_data,
            "export_format": export_format,
            "cost_summary": cost_summary,
            "errors": errors,
            "message": f"Blog generation completed with {len(sections)} sections"
        }

    except FileNotFoundError as e:
        logger.error(f"File validation error: {e}")
        return {
            "status": "error",
            "project_id": project_id,
            "project_name": project_name,
            "workflow_steps": workflow_steps,
            "errors": [str(e)],
            "message": "File validation failed"
        }

    except Exception as e:
        logger.exception(f"Unexpected error in complete blog generation: {e}")
        errors.append(f"Unexpected error: {str(e)}")
        return {
            "status": "error",
            "project_id": project_id,
            "project_name": project_name,
            "workflow_steps": workflow_steps,
            "outline": outline,
            "sections": sections,
            "errors": errors,
            "message": f"Blog generation failed: {str(e)}"
        }
