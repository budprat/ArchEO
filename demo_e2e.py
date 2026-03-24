#!/usr/bin/env python3
"""
Earth-Agent E2E Demo
====================
Demonstrates the full ReAct loop: LLM reasoning -> MCP tool call -> observe -> repeat -> answer.
Uses Claude via langchain-anthropic with MCP tool servers (Statistics + Analysis).
"""
import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

# Load env before anything else
from dotenv import load_dotenv
load_dotenv()

from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage

# ── Configuration ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.resolve()
DEMO_OUTPUT_DIR = PROJECT_ROOT / "demo_output"
DEMO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Temp dir for MCP tools (some tools write output files here)
TEMP_DIR = DEMO_OUTPUT_DIR / "tmp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# The Python executable from our venv
VENV_PYTHON = str(PROJECT_ROOT / ".venv" / "bin" / "python")

# MCP servers to boot — only Statistics and Analysis (numerical, no GeoTIFF needed)
TOOLS_DIR = str(PROJECT_ROOT / "agent" / "tools")

MCP_SERVERS = {
    "Statistics": {
        "command": VENV_PYTHON,
        "args": [
            str(PROJECT_ROOT / "agent" / "tools" / "Statistics.py"),
            "--temp_dir",
            str(TEMP_DIR),
        ],
        "transport": "stdio",
        "cwd": TOOLS_DIR,  # So `from utils import ...` works
    },
    "Analysis": {
        "command": VENV_PYTHON,
        "args": [
            str(PROJECT_ROOT / "agent" / "tools" / "Analysis.py"),
            "--temp_dir",
            str(TEMP_DIR),
        ],
        "transport": "stdio",
        "cwd": TOOLS_DIR,
    },
}

# Demo question — exercises multiple numerical tools
DEMO_QUESTION = (
    "Given monthly temperature readings in Kelvin for a location over one year:\n"
    "[285.3, 287.1, 292.5, 298.0, 305.2, 310.1, 312.4, 311.8, 306.5, 299.2, 291.0, 286.5]\n\n"
    "Please perform the following analyses:\n"
    "1. Convert each value from Kelvin to Celsius (subtract 273.15)\n"
    "2. Compute the mean of the Celsius values\n"
    "3. Compute the coefficient of variation of the Celsius values\n"
    "4. Fit a linear trend to the Celsius time series and report slope + intercept\n"
    "5. Run a Mann-Kendall test to determine if there is a statistically significant trend\n\n"
    "Use the available tools for each computation. Show your reasoning at each step."
)

SYSTEM_PROMPT = (
    "You are Earth-Agent, an AI assistant specialized in Earth science data analysis. "
    "You have access to statistical and analytical tools via MCP. "
    "Use these tools to perform computations — do NOT compute results manually. "
    "Think step-by-step, call tools as needed, and provide a clear final summary."
)

# ── ANSI Colors ──────────────────────────────────────────────────────────────

class C:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    RESET = "\033[0m"


def print_header(text, color=C.CYAN):
    print(f"\n{color}{C.BOLD}{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}{C.RESET}\n")


def print_step(label, content, color=C.GREEN):
    tag = f"{color}{C.BOLD}[{label}]{C.RESET}"
    # Indent multi-line content
    lines = str(content).split("\n")
    print(f"{tag} {lines[0]}")
    for line in lines[1:]:
        print(f"  {' ' * len(label)}  {line}")


# ── Main Demo ────────────────────────────────────────────────────────────────

async def run_demo():
    """Run the full E2E ReAct demo."""

    print_header("EARTH-AGENT E2E DEMO", C.CYAN)
    print(f"{C.DIM}Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Model: claude-sonnet-4-20250514")
    print(f"Tools: Statistics + Analysis MCP servers{C.RESET}\n")

    # ── 1. Initialize LLM ────────────────────────────────────────────────
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print(f"{C.RED}ERROR: ANTHROPIC_API_KEY not set. Add it to .env{C.RESET}")
        sys.exit(1)

    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=api_key,
        temperature=0.1,
        max_tokens=4096,
    )
    print(f"{C.GREEN}✓ LLM initialized{C.RESET}")

    # ── 2. Boot MCP servers & create agent ────────────────────────────────
    print(f"{C.YELLOW}⏳ Booting MCP tool servers...{C.RESET}")

    trajectory = {
        "timestamp": datetime.now().isoformat(),
        "model": "claude-sonnet-4-20250514",
        "question": DEMO_QUESTION,
        "steps": [],
    }

    client = MultiServerMCPClient(MCP_SERVERS)
    tools = await client.get_tools()
    tool_names = [t.name for t in tools]
    print(f"{C.GREEN}✓ Loaded {len(tools)} tools: {', '.join(tool_names)}{C.RESET}")

    # Create ReAct agent
    agent = create_react_agent(llm, tools)

    # ── 3. Run the agent ──────────────────────────────────────────────
    print_header("QUESTION", C.YELLOW)
    print(DEMO_QUESTION)
    print_header("REACT LOOP", C.MAGENTA)

    step_count = 0
    response = await agent.ainvoke(
        {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=DEMO_QUESTION),
            ]
        },
        config={"recursion_limit": 30},
    )

    # ── 4. Process & display results ──────────────────────────────────
    for msg in response["messages"]:
        if msg.type == "system":
            continue

        elif msg.type == "human":
            print_step("QUESTION", msg.content[:100] + "...", C.YELLOW)
            trajectory["steps"].append({
                "type": "human",
                "content": msg.content,
            })

        elif msg.type == "ai":
            # Text reasoning
            if msg.content and isinstance(msg.content, str) and msg.content.strip():
                step_count += 1
                print_step("THINK", msg.content, C.CYAN)
                trajectory["steps"].append({
                    "type": "think",
                    "step": step_count,
                    "content": msg.content,
                })
            elif msg.content and isinstance(msg.content, list):
                # Claude sometimes returns content as list of blocks
                for block in msg.content:
                    if isinstance(block, dict):
                        if block.get("type") == "text" and block.get("text", "").strip():
                            step_count += 1
                            print_step("THINK", block["text"], C.CYAN)
                            trajectory["steps"].append({
                                "type": "think",
                                "step": step_count,
                                "content": block["text"],
                            })
                        elif block.get("type") == "tool_use":
                            tool_name = block.get("name", "unknown")
                            tool_input = block.get("input", {})
                            print_step("TOOL CALL", f"{tool_name}({json.dumps(tool_input, default=str)[:200]})", C.GREEN)
                            trajectory["steps"].append({
                                "type": "tool_call",
                                "tool": tool_name,
                                "input": tool_input,
                            })

            # Tool calls via additional_kwargs
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.get("name", tc.get("function", {}).get("name", "unknown"))
                    tool_args = tc.get("args", {})
                    print_step("TOOL CALL", f"{tool_name}({json.dumps(tool_args, default=str)[:200]})", C.GREEN)
                    trajectory["steps"].append({
                        "type": "tool_call",
                        "tool": tool_name,
                        "input": tool_args,
                    })

        elif msg.type == "tool":
            result_str = str(msg.content)[:500]
            print_step("TOOL RESULT", result_str, C.BLUE)
            trajectory["steps"].append({
                "type": "tool_result",
                "tool": getattr(msg, "name", "unknown"),
                "content": msg.content,
            })

    # ── 5. Extract & display final answer ────────────────────────────
    print_header("FINAL ANSWER", C.GREEN)
    # The last AI message is the final answer
    final_msgs = [m for m in response["messages"] if m.type == "ai"]
    if final_msgs:
        final = final_msgs[-1]
        if isinstance(final.content, str):
            final_text = final.content
        elif isinstance(final.content, list):
            final_text = "\n".join(
                b.get("text", "") if isinstance(b, dict) else str(b)
                for b in final.content
            )
        else:
            final_text = str(final.content)
        print(final_text)
        trajectory["final_answer"] = final_text
    else:
        print(f"{C.RED}No final answer found{C.RESET}")
        trajectory["final_answer"] = None

    # ── 6. Save trajectory ────────────────────────────────────────────────
    traj_path = DEMO_OUTPUT_DIR / "trajectory.json"
    with open(traj_path, "w") as f:
        json.dump(trajectory, f, indent=2, default=str)
    print(f"\n{C.DIM}Trajectory saved to: {traj_path}{C.RESET}")

    # Summary stats
    tool_calls = [s for s in trajectory["steps"] if s["type"] == "tool_call"]
    think_steps = [s for s in trajectory["steps"] if s["type"] == "think"]
    print(f"\n{C.BOLD}📊 Summary:{C.RESET}")
    print(f"  • Thinking steps: {len(think_steps)}")
    print(f"  • Tool calls: {len(tool_calls)}")
    if tool_calls:
        print(f"  • Tools used: {', '.join(set(t['tool'] for t in tool_calls))}")
    print()


if __name__ == "__main__":
    asyncio.run(run_demo())
