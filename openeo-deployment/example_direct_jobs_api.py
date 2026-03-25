# ABOUTME: Direct programmatic example of OpenEO jobs API interaction.
# Shows both direct API calls and Claude AI-assisted workflow.

"""
Direct OpenEO Jobs API Interaction

This example shows:
1. Direct programmatic use of JobTools (no AI)
2. AI-assisted workflow using Claude
3. Visualization of results
"""

import asyncio
import os
import json

os.environ["ANTHROPIC_API_KEY"] = "YOUR_ANTHROPIC_API_KEY"


# ============================================================================
# OPTION 1: Direct Programmatic API (No AI)
# ============================================================================

async def direct_api_example():
    """
    Use JobTools directly without AI assistance.
    Full control over the workflow.
    """
    from openeo_ai.tools.job_tools import JobTools
    from openeo_ai.tools.openeo_tools import OpenEOTools
    from openeo_ai.tools.validation_tools import ValidationTools

    print("\n" + "="*70)
    print("OPTION 1: Direct Programmatic API (No AI)")
    print("="*70)

    # Initialize tools
    openeo_url = "http://localhost:8000/openeo/1.1.0"
    job_tools = JobTools(openeo_url=openeo_url)
    openeo_tools = OpenEOTools(openeo_url=openeo_url)
    validation = ValidationTools()

    # Step 1: List available collections
    print("\n📦 Step 1: List Collections")
    try:
        collections = await openeo_tools.list_collections()
        print(f"   Found {len(collections)} collections")
        for c in collections[:3]:
            print(f"   - {c['id']}: {c['title']}")
    except Exception as e:
        print(f"   (Server not running: {e})")
        collections = []

    # Step 2: Create a process graph
    print("\n📝 Step 2: Create Process Graph")
    process_graph = {
        "load": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l2a",
                "spatial_extent": {
                    "west": 11.0,
                    "south": 46.0,
                    "east": 11.05,
                    "north": 46.05
                },
                "temporal_extent": ["2024-07-01", "2024-07-15"],
                "bands": ["red", "nir"]
            }
        },
        "ndvi": {
            "process_id": "ndvi",
            "arguments": {
                "data": {"from_node": "load"},
                "nir": "nir",
                "red": "red"
            }
        },
        "save": {
            "process_id": "save_result",
            "arguments": {
                "data": {"from_node": "ndvi"},
                "format": "GTiff"
            },
            "result": True
        }
    }
    print(f"   Created NDVI process graph with {len(process_graph)} nodes")

    # Step 3: Validate the graph
    print("\n✅ Step 3: Validate Process Graph")
    validation_result = await validation.validate(process_graph)
    print(f"   Valid: {validation_result['valid']}")
    if validation_result['warnings']:
        print(f"   Warnings: {len(validation_result['warnings'])}")
    if validation_result['suggestions']:
        print(f"   Suggestions: {len(validation_result['suggestions'])}")
        for s in validation_result['suggestions'][:2]:
            print(f"   - {s[:60]}...")

    # Step 4: Create batch job (requires running server)
    print("\n🚀 Step 4: Create Batch Job")
    try:
        job = await job_tools.create(
            title="NDVI Analysis Alps",
            description="Calculate NDVI for alpine region",
            process_graph=process_graph
        )
        print(f"   Job created: {job['id']}")
        print(f"   Status: {job['status']}")

        # Step 5: Start the job
        print("\n▶️ Step 5: Start Job")
        result = await job_tools.start(job['id'])
        print(f"   Job started: {result['status']}")

        # Step 6: Monitor status
        print("\n📊 Step 6: Monitor Status")
        status = await job_tools.get_status(job['id'])
        print(f"   Current status: {status.get('status', 'unknown')}")

    except Exception as e:
        print(f"   (Server not running: {e})")
        print("   → In production, this would create and start the job")


# ============================================================================
# OPTION 2: AI-Assisted Workflow (Natural Language)
# ============================================================================

async def ai_assisted_example():
    """
    Use Claude AI to handle the workflow.
    Natural language interface, AI selects appropriate tools.
    """
    from openeo_ai.sdk.client import OpenEOAIClient

    print("\n" + "="*70)
    print("OPTION 2: AI-Assisted Workflow (Natural Language)")
    print("="*70)

    client = OpenEOAIClient()

    # Single natural language request
    prompt = """
    I need to create a batch job for NDVI analysis:
    - Location: Small area in the Alps (11.0-11.05°E, 46.0-46.05°N)
    - Time: July 1-15, 2024
    - Data: Sentinel-2

    Please:
    1. Generate the process graph
    2. Validate it
    3. Explain what API calls would be made to create and start the job
    """

    print(f"\n💬 User Request:\n{prompt}")
    print("\n🤖 AI Assistant Response:")
    print("-" * 50)

    async for response in client.chat(prompt, user_id="demo"):
        if response.get("type") == "text":
            # Print response in chunks for readability
            text = response['content']
            print(text)
        elif response.get("type") == "tool_result":
            print(f"\n[Tool Used: {response['tool']}]")


# ============================================================================
# OPTION 3: Hybrid Approach (Best of Both)
# ============================================================================

async def hybrid_example():
    """
    Combine AI assistance with programmatic control.
    Use AI for complex decisions, direct API for execution.
    """
    from openeo_ai.sdk.client import OpenEOAIClient
    from openeo_ai.tools.job_tools import JobTools
    from openeo_ai.tools.validation_tools import ValidationTools

    print("\n" + "="*70)
    print("OPTION 3: Hybrid Approach")
    print("="*70)

    client = OpenEOAIClient()

    # Step 1: Use AI to generate optimal process graph
    print("\n🤖 Step 1: AI generates process graph")
    prompt = """Generate ONLY a JSON process graph for NDVI calculation.
    Use Sentinel-2, area: west=11, south=46, east=11.05, north=46.05,
    dates: 2024-07-01 to 2024-07-15.
    Return ONLY the JSON, no explanation."""

    process_graph = None
    async for response in client.chat(prompt, user_id="demo"):
        if response.get("type") == "tool_result":
            result = response.get('result')
            if isinstance(result, dict):
                process_graph = result
                print(f"   AI generated graph with {len(result)} nodes")

    # Step 2: Programmatically validate
    print("\n✅ Step 2: Programmatic validation")
    if process_graph:
        validation = ValidationTools()
        result = await validation.validate(process_graph)
        print(f"   Valid: {result['valid']}")

    # Step 3: Programmatically create job (with full control)
    print("\n🔧 Step 3: Programmatic job creation")
    print("   → job_tools.create(title, description, process_graph)")
    print("   → job_tools.start(job_id)")
    print("   → job_tools.get_status(job_id)")
    print("   → job_tools.get_results(job_id)")


# ============================================================================
# API Endpoint Reference
# ============================================================================

def show_api_reference():
    """Show the OpenEO Jobs API endpoints used."""
    print("\n" + "="*70)
    print("OpenEO /jobs API Endpoint Reference")
    print("="*70)

    endpoints = [
        ("POST", "/jobs", "Create a new batch job", "openeo_create_job"),
        ("GET", "/jobs", "List all jobs", "-"),
        ("GET", "/jobs/{id}", "Get job details/status", "openeo_get_job_status"),
        ("PATCH", "/jobs/{id}", "Update job metadata", "-"),
        ("DELETE", "/jobs/{id}", "Delete a job", "-"),
        ("POST", "/jobs/{id}/results", "Start job processing", "openeo_start_job"),
        ("GET", "/jobs/{id}/results", "Get job results", "openeo_get_results"),
        ("DELETE", "/jobs/{id}/results", "Cancel job", "-"),
        ("GET", "/jobs/{id}/logs", "Get job logs", "-"),
    ]

    print("\n┌─────────┬──────────────────────────┬─────────────────────────┬────────────────────┐")
    print("│ Method  │ Endpoint                 │ Description             │ AI Tool            │")
    print("├─────────┼──────────────────────────┼─────────────────────────┼────────────────────┤")
    for method, endpoint, desc, tool in endpoints:
        print(f"│ {method:<7} │ {endpoint:<24} │ {desc:<23} │ {tool:<18} │")
    print("└─────────┴──────────────────────────┴─────────────────────────┴────────────────────┘")


async def main():
    show_api_reference()
    await direct_api_example()
    await ai_assisted_example()
    await hybrid_example()

    print("\n" + "="*70)
    print("Summary: Three Ways to Interact with OpenEO Jobs")
    print("="*70)
    print("""
    1. DIRECT API: Full programmatic control
       → from openeo_ai.tools.job_tools import JobTools
       → job_tools.create(), start(), get_status(), get_results()

    2. AI-ASSISTED: Natural language interface
       → from openeo_ai.sdk.client import OpenEOAIClient
       → client.chat("Create NDVI job for...")

    3. HYBRID: AI for complex tasks, direct API for execution
       → Use AI to generate/validate process graphs
       → Use direct API for job management
    """)


if __name__ == "__main__":
    asyncio.run(main())
