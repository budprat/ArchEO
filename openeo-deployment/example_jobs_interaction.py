# ABOUTME: Example demonstrating OpenEO jobs interaction via Claude AI Assistant.
# Shows how to create, start, monitor, and visualize batch job results.

"""
OpenEO Jobs Interaction via Claude Agent SDK

This example shows how to:
1. Create a batch job with a process graph
2. Start the job
3. Monitor job status
4. Get and visualize results

The AI assistant uses tools that call the OpenEO /jobs endpoints.
"""

import asyncio
import os

# Set API key
os.environ["ANTHROPIC_API_KEY"] = "YOUR_ANTHROPIC_API_KEY"

from openeo_ai.sdk.client import OpenEOAIClient, OpenEOAIConfig


async def example_natural_language_workflow():
    """
    Example 1: Natural Language Workflow

    Ask the assistant to create and run an analysis using natural language.
    The assistant will automatically use the appropriate tools.
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Natural Language Job Creation")
    print("="*70)

    client = OpenEOAIClient()

    # Natural language request - assistant will use tools automatically
    prompt = """
    I need to analyze vegetation health for a small area in the Alps (coordinates:
    west=11.0, south=46.0, east=11.1, north=46.1) during summer 2024 (June-August).

    Please:
    1. Generate a process graph for NDVI calculation using Sentinel-2 data
    2. Validate the process graph
    3. Create a batch job for this analysis

    Show me the job details when done.
    """

    print(f"\nUser Request:\n{prompt}")
    print("\n" + "-"*70)
    print("Assistant Response:")
    print("-"*70)

    async for response in client.chat(prompt, user_id="demo_user"):
        if response.get("type") == "text":
            print(f"\n{response['content']}")
        elif response.get("type") == "tool_result":
            print(f"\n[Tool: {response['tool']}]")
            result = response.get('result', {})
            if isinstance(result, dict):
                import json
                print(json.dumps(result, indent=2)[:500])


async def example_direct_tool_calls():
    """
    Example 2: Understanding the Tool Flow

    Shows the individual steps the assistant takes when interacting with jobs.
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Step-by-Step Job Interaction")
    print("="*70)

    client = OpenEOAIClient()

    # Step 1: Generate a process graph
    print("\n--- Step 1: Generate Process Graph ---")
    prompt1 = """Generate a process graph for calculating NDVI from Sentinel-2 data
    for the area west=11.0, south=46.0, east=11.05, north=46.05
    from 2024-07-01 to 2024-07-15. Output as GeoTiff."""

    session_id = None
    async for response in client.chat(prompt1, user_id="demo_user"):
        if response.get("type") == "text":
            print(response['content'][:800])
        elif response.get("type") == "tool_result":
            print(f"[Generated graph via {response['tool']}]")
        elif response.get("type") == "session":
            session_id = response['session_id']

    # Step 2: Validate the graph
    print("\n--- Step 2: Validate the Graph ---")
    prompt2 = "Now validate this process graph and tell me if there are any issues."

    async for response in client.chat(prompt2, user_id="demo_user", session_id=session_id):
        if response.get("type") == "text":
            print(response['content'][:600])
        elif response.get("type") == "tool_result":
            print(f"[Validated via {response['tool']}]")

    # Step 3: Create the job
    print("\n--- Step 3: Create Batch Job ---")
    prompt3 = "Create a batch job with this process graph. Title it 'NDVI Analysis Alps July 2024'."

    async for response in client.chat(prompt3, user_id="demo_user", session_id=session_id):
        if response.get("type") == "text":
            print(response['content'][:600])
        elif response.get("type") == "tool_result":
            print(f"[Created job via {response['tool']}]")
            if isinstance(response.get('result'), dict):
                print(f"Job ID: {response['result'].get('id', 'N/A')}")


async def example_job_monitoring():
    """
    Example 3: Job Status Monitoring

    Shows how to check job status and get results.
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Job Monitoring & Results")
    print("="*70)

    client = OpenEOAIClient()

    prompt = """
    Explain how I would:
    1. Check the status of a batch job with ID "abc-123"
    2. Get the results once it's complete
    3. Visualize the NDVI results on a map

    What tools would you use for each step?
    """

    print(f"\nUser: {prompt}")
    print("\nAssistant:")

    async for response in client.chat(prompt, user_id="demo_user"):
        if response.get("type") == "text":
            print(response['content'])


async def show_available_tools():
    """
    Example 4: List Available Job Tools

    Shows all the tools available for job interaction.
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Available Job & Visualization Tools")
    print("="*70)

    client = OpenEOAIClient()

    print("\n📦 JOB MANAGEMENT TOOLS:")
    print("-" * 40)
    job_tools = [
        ("openeo_create_job", "Create a new batch job with a process graph"),
        ("openeo_start_job", "Start a queued batch job"),
        ("openeo_get_job_status", "Get current status of a job"),
        ("openeo_get_results", "Download results of a completed job"),
    ]
    for name, desc in job_tools:
        print(f"  • {name}")
        print(f"    {desc}\n")

    print("\n🗺️ VISUALIZATION TOOLS:")
    print("-" * 40)
    viz_tools = [
        ("viz_show_map", "Display raster data on interactive map"),
        ("viz_show_ndvi_map", "Display NDVI with vegetation colormap"),
        ("viz_show_time_series", "Create time series chart"),
        ("viz_compare_images", "Before/after comparison slider"),
    ]
    for name, desc in viz_tools:
        print(f"  • {name}")
        print(f"    {desc}\n")

    print("\n🤖 GEOAI TOOLS:")
    print("-" * 40)
    geoai_tools = [
        ("geoai_segment", "Semantic segmentation for land cover"),
        ("geoai_detect_change", "Change detection between two images"),
        ("geoai_estimate_canopy_height", "Estimate tree heights from RGB"),
    ]
    for name, desc in geoai_tools:
        print(f"  • {name}")
        print(f"    {desc}\n")


async def example_full_workflow_with_visualization():
    """
    Example 5: Complete Workflow Request

    Natural language request for full analysis with visualization.
    """
    print("\n" + "="*70)
    print("EXAMPLE 5: Complete Analysis Workflow")
    print("="*70)

    client = OpenEOAIClient()

    prompt = """
    I want to monitor deforestation in a tropical forest area. Here's what I need:

    1. Load Sentinel-2 data for two time periods:
       - Before: January 2023
       - After: January 2024
       - Area: A small test region (0.1 x 0.1 degrees)

    2. Calculate NDVI for both periods

    3. Detect changes between the two periods

    4. Visualize the results showing before/after comparison

    Can you explain how you would set this up as batch jobs and what
    the visualization would look like?
    """

    print(f"\nUser: {prompt}")
    print("\nAssistant:")

    async for response in client.chat(prompt, user_id="demo_user"):
        if response.get("type") == "text":
            print(response['content'])


async def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("OpenEO Jobs Interaction via Claude Agent SDK")
    print("="*70)

    # Show available tools first
    await show_available_tools()

    # Run examples
    await example_natural_language_workflow()
    await example_direct_tool_calls()
    await example_job_monitoring()
    await example_full_workflow_with_visualization()

    print("\n" + "="*70)
    print("Examples Complete!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
