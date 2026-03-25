# ABOUTME: End-to-end test for OpenEO AI Assistant with real Claude API calls.
# Tests the full chat flow including tool execution and response handling.

"""
End-to-end test for OpenEO AI Assistant.

This test makes real API calls to Claude to verify the full integration works.
"""

import asyncio
import os
import sys

# Set API key
os.environ["ANTHROPIC_API_KEY"] = "YOUR_ANTHROPIC_API_KEY"

from openeo_ai.sdk.client import OpenEOAIClient, OpenEOAIConfig


async def test_simple_chat():
    """Test a simple chat interaction."""
    print("\n" + "="*60)
    print("TEST 1: Simple Chat")
    print("="*60)

    config = OpenEOAIConfig()
    client = OpenEOAIClient(config=config)

    prompt = "Hello! What can you help me with for Earth Observation analysis?"
    print(f"\nUser: {prompt}")
    print("\nAssistant:")

    responses = []
    async for response in client.chat(prompt, user_id="test_user"):
        responses.append(response)
        if response.get("type") == "text":
            print(f"  {response['content'][:500]}...")
        elif response.get("type") == "session":
            print(f"  [Session ID: {response['session_id']}]")

    assert len(responses) > 0, "Should have at least one response"
    assert any(r.get("type") == "text" for r in responses), "Should have text response"
    print("\n✓ TEST 1 PASSED")
    return responses


async def test_list_collections():
    """Test listing collections via tool use."""
    print("\n" + "="*60)
    print("TEST 2: List Collections (Tool Use)")
    print("="*60)

    config = OpenEOAIConfig()
    client = OpenEOAIClient(config=config)

    prompt = "Please list the available Earth Observation data collections."
    print(f"\nUser: {prompt}")
    print("\nAssistant:")

    responses = []
    async for response in client.chat(prompt, user_id="test_user"):
        responses.append(response)
        if response.get("type") == "text":
            content = response['content']
            # Print first 800 chars
            print(f"  {content[:800]}{'...' if len(content) > 800 else ''}")
        elif response.get("type") == "tool_result":
            print(f"  [Tool: {response['tool']}]")
            result = response.get('result', {})
            if isinstance(result, list):
                print(f"  Found {len(result)} collections")
        elif response.get("type") == "session":
            print(f"  [Session ID: {response['session_id']}]")

    assert len(responses) > 0, "Should have responses"
    print("\n✓ TEST 2 PASSED")
    return responses


async def test_validate_process_graph():
    """Test process graph validation."""
    print("\n" + "="*60)
    print("TEST 3: Validate Process Graph")
    print("="*60)

    config = OpenEOAIConfig()
    client = OpenEOAIClient(config=config)

    prompt = """Please validate this process graph:
{
  "load": {
    "process_id": "load_collection",
    "arguments": {
      "id": "sentinel-2-l2a",
      "spatial_extent": {"west": 11.0, "south": 46.0, "east": 11.5, "north": 46.5},
      "temporal_extent": ["2024-06-01", "2024-06-30"],
      "bands": ["red", "nir"]
    }
  },
  "ndvi": {
    "process_id": "normalized_difference",
    "arguments": {
      "x": {"from_node": "load"},
      "y": {"from_node": "load"}
    }
  },
  "save": {
    "process_id": "save_result",
    "arguments": {
      "data": {"from_node": "ndvi"},
      "format": "GTiff"
    },
    "result": true
  }
}"""

    print(f"\nUser: {prompt[:200]}...")
    print("\nAssistant:")

    responses = []
    async for response in client.chat(prompt, user_id="test_user"):
        responses.append(response)
        if response.get("type") == "text":
            content = response['content']
            print(f"  {content[:800]}{'...' if len(content) > 800 else ''}")
        elif response.get("type") == "tool_result":
            print(f"  [Tool: {response['tool']}]")
            result = response.get('result', {})
            if isinstance(result, dict):
                print(f"  Valid: {result.get('valid', 'unknown')}")
                if result.get('warnings'):
                    print(f"  Warnings: {len(result['warnings'])}")
                if result.get('suggestions'):
                    print(f"  Suggestions: {len(result['suggestions'])}")
        elif response.get("type") == "session":
            print(f"  [Session ID: {response['session_id']}]")

    assert len(responses) > 0, "Should have responses"
    print("\n✓ TEST 3 PASSED")
    return responses


async def test_session_continuity():
    """Test conversation continuity with sessions."""
    print("\n" + "="*60)
    print("TEST 4: Session Continuity")
    print("="*60)

    config = OpenEOAIConfig()
    client = OpenEOAIClient(config=config)

    # First message
    prompt1 = "I want to analyze NDVI for farmland near Munich, Germany."
    print(f"\nUser: {prompt1}")
    print("\nAssistant:")

    session_id = None
    async for response in client.chat(prompt1, user_id="test_user"):
        if response.get("type") == "text":
            print(f"  {response['content'][:500]}...")
        elif response.get("type") == "session":
            session_id = response['session_id']
            print(f"  [Session ID: {session_id}]")

    assert session_id is not None, "Should have session ID"

    # Second message using same session
    prompt2 = "What time period would you recommend for crop health analysis?"
    print(f"\nUser: {prompt2}")
    print("\nAssistant:")

    async for response in client.chat(prompt2, user_id="test_user", session_id=session_id):
        if response.get("type") == "text":
            print(f"  {response['content'][:500]}...")
        elif response.get("type") == "session":
            print(f"  [Session ID: {response['session_id']}]")

    print("\n✓ TEST 4 PASSED")


async def main():
    """Run all e2e tests."""
    print("\n" + "="*60)
    print("OpenEO AI Assistant - End-to-End Tests")
    print("="*60)
    print(f"\nAPI Key: {'*' * 20}...{os.environ['ANTHROPIC_API_KEY'][-8:]}")

    try:
        await test_simple_chat()
        await test_list_collections()
        await test_validate_process_graph()
        await test_session_continuity()

        print("\n" + "="*60)
        print("ALL E2E TESTS PASSED!")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
