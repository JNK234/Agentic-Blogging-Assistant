# ABOUTME: Example demonstrating transparent LLM cost tracking with SQL persistence
# ABOUTME: Shows how to wrap models and track costs automatically across all providers

"""
Cost Tracking Wrapper Example

This example demonstrates how to use the CostTrackingModel wrapper to automatically
track token usage and costs for all LLM calls with SQL persistence.

Features demonstrated:
- Transparent model wrapping
- Automatic token counting
- Cost calculation based on model-specific pricing
- SQL persistence via SQLProjectManager
- Context-aware tracking (node names, agent names)
- Graceful error handling
"""

import asyncio
import logging
from typing import Optional

from backend.models.cost_tracking_wrapper import CostTrackingModel
from backend.models.model_factory import ModelFactory
from backend.services.sql_project_manager import SQLProjectManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_basic_tracking():
    """Basic example: wrap a model and track costs"""
    print("\n=== Example 1: Basic Cost Tracking ===")

    # Create SQL project manager
    sql_pm = SQLProjectManager("sqlite:///data/examples.db")

    # Create a project
    project_id = await sql_pm.create_project(
        project_name="Cost Tracking Example",
        metadata={"purpose": "demonstration"}
    )

    # Create a base model
    factory = ModelFactory()
    base_model = factory.create_model("openai", "gpt-4o-mini")

    # Wrap with cost tracking
    tracked_model = CostTrackingModel(
        base_model=base_model.llm,  # Extract the LangChain LLM
        model_name="gpt-4o-mini",
        sql_project_manager=sql_pm,
        project_id=project_id,
        agent_name="ExampleAgent"
    )

    # Use the model - costs are tracked automatically
    response = await tracked_model.ainvoke("Write a haiku about AI agents")

    print(f"\nResponse: {response.content}")
    print(f"\nSession costs: {tracked_model.get_session_summary()}")

    # Check SQL tracking
    cost_summary = await sql_pm.get_cost_summary(project_id)
    print(f"\nSQL Cost Summary: {cost_summary}")


async def example_multi_agent_tracking():
    """Advanced example: track costs across multiple agents"""
    print("\n=== Example 2: Multi-Agent Cost Tracking ===")

    sql_pm = SQLProjectManager("sqlite:///data/examples.db")
    project_id = await sql_pm.create_project(
        project_name="Multi-Agent Blog Generation",
        metadata={"agents": ["ContentParser", "OutlineGenerator", "BlogDrafter"]}
    )

    factory = ModelFactory()

    # Simulate different agents with different models
    agents_config = [
        ("ContentParser", "openai", "gpt-4o-mini"),
        ("OutlineGenerator", "claude", "claude-3.5-haiku"),
        ("BlogDrafter", "openai", "gpt-4o")
    ]

    total_cost = 0.0

    for agent_name, provider, model_name in agents_config:
        print(f"\n--- {agent_name} using {model_name} ---")

        # Create and wrap model
        base_model = factory.create_model(provider, model_name)
        tracked_model = CostTrackingModel(
            base_model=base_model.llm,
            model_name=model_name,
            sql_project_manager=sql_pm,
            project_id=project_id,
            agent_name=agent_name
        )

        # Simulate agent work
        prompt = f"This is a test prompt for {agent_name}. Generate a brief response."
        response = await tracked_model.ainvoke(prompt)

        session_summary = tracked_model.get_session_summary()
        total_cost += session_summary['total_cost']
        print(f"  Cost: ${session_summary['total_cost']:.6f}")

    # Get comprehensive cost analysis
    cost_summary = await sql_pm.get_cost_summary(project_id)
    print(f"\n=== Final Project Costs ===")
    print(f"Total Cost: ${cost_summary['total_cost']:.6f}")
    print(f"Total Tokens: {cost_summary['total_input_tokens'] + cost_summary['total_output_tokens']:,}")
    print(f"\nCost by Agent:")
    for agent, cost in cost_summary['cost_by_agent'].items():
        print(f"  {agent}: ${cost:.6f}")
    print(f"\nCost by Model:")
    for model, cost in cost_summary['cost_by_model'].items():
        print(f"  {model}: ${cost:.6f}")


async def example_context_tracking():
    """Example showing context-aware tracking (node names, operations)"""
    print("\n=== Example 3: Context-Aware Tracking ===")

    sql_pm = SQLProjectManager("sqlite:///data/examples.db")
    project_id = await sql_pm.create_project(
        project_name="Context Tracking Example",
        metadata={"workflow": "outline_generation"}
    )

    factory = ModelFactory()
    base_model = factory.create_model("openai", "gpt-4o-mini")

    # Create wrapper with context supplier
    def get_context():
        return {
            "node_name": "analyze_content",
            "stage": "analysis",
            "iteration": 1
        }

    tracked_model = CostTrackingModel(
        base_model=base_model.llm,
        model_name="gpt-4o-mini",
        sql_project_manager=sql_pm,
        project_id=project_id,
        agent_name="OutlineGenerator",
        context_supplier=get_context
    )

    # Make a call - context is automatically captured
    response = await tracked_model.ainvoke("Analyze this content structure")

    # View detailed cost analysis
    cost_analysis = await sql_pm.get_cost_analysis(project_id)
    print(f"\nCost Timeline:")
    for entry in cost_analysis['timeline']:
        print(f"  {entry['timestamp']}: {entry['operation']} - ${entry['cost']:.6f}")


async def example_error_handling():
    """Example showing graceful error handling in cost tracking"""
    print("\n=== Example 4: Error Handling ===")

    sql_pm = SQLProjectManager("sqlite:///data/examples.db")
    project_id = await sql_pm.create_project(
        project_name="Error Handling Example"
    )

    factory = ModelFactory()
    base_model = factory.create_model("openai", "gpt-4o-mini")

    tracked_model = CostTrackingModel(
        base_model=base_model.llm,
        model_name="gpt-4o-mini",
        sql_project_manager=sql_pm,
        project_id=project_id,
        agent_name="TestAgent"
    )

    try:
        # This will work even if SQL tracking fails
        response = await tracked_model.ainvoke("Test prompt")
        print(f"Response received: {response.content[:100]}...")

        # Session costs are still tracked locally
        print(f"\nLocal session tracking: {tracked_model.get_session_summary()}")

    except Exception as e:
        print(f"Error occurred: {e}")
        # Costs are still tracked for failed calls
        print(f"Session costs despite error: {tracked_model.get_session_summary()}")


async def example_model_pricing():
    """Example showing pricing for different models"""
    print("\n=== Example 5: Model Pricing Information ===")

    from backend.utils.token_counter import TokenCounter

    counter = TokenCounter()

    models_to_check = [
        "gpt-4o",
        "gpt-4o-mini",
        "claude-3.5-sonnet",
        "claude-3.5-haiku",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "deepseek-v3"
    ]

    print("\nCurrent Model Pricing (per 1M tokens):")
    print("-" * 70)
    print(f"{'Model':<25} {'Input':<15} {'Output':<15} {'Found'}")
    print("-" * 70)

    for model in models_to_check:
        pricing_info = counter.get_model_pricing_info(model)
        print(
            f"{pricing_info['model']:<25} "
            f"${pricing_info['input_price_per_1m']:<14.2f} "
            f"${pricing_info['output_price_per_1m']:<14.2f} "
            f"{'✓' if pricing_info['found'] else '✗ (fallback)'}"
        )

    # Estimate cost for a hypothetical call
    print("\n\nCost Estimation Example:")
    test_prompt = "Write a comprehensive blog post about AI agents" * 100  # ~1000 tokens
    expected_output = 2000

    for model in ["gpt-4o", "gpt-4o-mini", "claude-3.5-haiku"]:
        cost, breakdown = counter.estimate_cost(test_prompt, expected_output, model)
        print(f"\n{model}:")
        print(f"  Input tokens: {breakdown['input_tokens']:,}")
        print(f"  Output tokens: {expected_output:,}")
        print(f"  Estimated cost: ${cost:.4f}")


async def main():
    """Run all examples"""
    print("=" * 70)
    print("Cost Tracking Wrapper Examples")
    print("=" * 70)

    try:
        await example_basic_tracking()
        await asyncio.sleep(1)

        await example_multi_agent_tracking()
        await asyncio.sleep(1)

        await example_context_tracking()
        await asyncio.sleep(1)

        await example_error_handling()
        await asyncio.sleep(1)

        await example_model_pricing()

    except Exception as e:
        logger.error(f"Example failed: {e}", exc_info=True)

    print("\n" + "=" * 70)
    print("Examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
