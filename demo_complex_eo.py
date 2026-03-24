#!/usr/bin/env python3
"""
Earth-Agent Complex EO Queries Demo
====================================
Three progressively harder Earth Observation queries that test multi-step
reasoning, tool chaining, and scientific interpretation.

Query 1: NDVI time series anomaly detection (STL + change points + spikes)
Query 2: Urban Heat Island multi-year trend analysis (Sen's slope + seasonality + CV)
Query 3: Wildfire risk — multi-indicator fusion (percentage change, autocorrelation, trend)
"""
import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

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

TEMP_DIR = DEMO_OUTPUT_DIR / "tmp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

VENV_PYTHON = str(PROJECT_ROOT / ".venv" / "bin" / "python")
TOOLS_DIR = str(PROJECT_ROOT / "agent" / "tools")

MCP_SERVERS = {
    "Statistics": {
        "command": VENV_PYTHON,
        "args": [
            str(PROJECT_ROOT / "agent" / "tools" / "Statistics.py"),
            "--temp_dir", str(TEMP_DIR),
        ],
        "transport": "stdio",
        "cwd": TOOLS_DIR,
    },
    "Analysis": {
        "command": VENV_PYTHON,
        "args": [
            str(PROJECT_ROOT / "agent" / "tools" / "Analysis.py"),
            "--temp_dir", str(TEMP_DIR),
        ],
        "transport": "stdio",
        "cwd": TOOLS_DIR,
    },
}

SYSTEM_PROMPT = (
    "You are Earth-Agent, an AI assistant specialized in Earth science and remote sensing data analysis. "
    "You have access to statistical and analytical tools via MCP. "
    "IMPORTANT: Use the available tools for ALL computations — do NOT compute results manually or in your head. "
    "Think step-by-step, explain your reasoning, call tools as needed, and provide a clear scientific interpretation."
)

# ── Complex EO Queries ───────────────────────────────────────────────────────

QUERIES = [
    {
        "id": "Q1",
        "title": "NDVI Anomaly Detection — Deforestation Signal",
        "difficulty": "Medium",
        "expected_tools": ["mean", "stl_decompose", "detect_change_points", "count_spikes_from_values", "coefficient_of_variation"],
        "question": (
            "A Landsat-derived NDVI time series was extracted from a tropical forest pixel over 36 months (Jan 2022 – Dec 2024). "
            "The monthly NDVI values are:\n\n"
            "[0.82, 0.80, 0.78, 0.81, 0.85, 0.87, 0.86, 0.84, 0.83, 0.80, 0.79, 0.81, "  # 2022: stable forest
            "0.80, 0.79, 0.77, 0.80, 0.83, 0.85, 0.84, 0.82, 0.81, 0.78, 0.76, 0.78, "   # 2023: slight decline
            "0.45, 0.38, 0.35, 0.32, 0.30, 0.28, 0.25, 0.27, 0.30, 0.33, 0.35, 0.37]\n\n" # 2024: deforestation!
            "Please perform the following analysis:\n"
            "1. Compute the overall mean NDVI and the coefficient of variation for the full series\n"
            "2. Compute the mean NDVI for each year separately (months 1-12, 13-24, 25-36)\n"
            "3. Calculate the percentage change in mean NDVI between Year 1 and Year 3\n"
            "4. Apply STL decomposition with period=12 to separate trend from seasonality\n"
            "5. Detect change points in the series using penalty=5 (to detect the deforestation event)\n"
            "6. Run Mann-Kendall trend test on the full series\n"
            "7. Based on all results, provide a scientific assessment: Was there a deforestation event? "
            "When did it occur? How severe was the vegetation loss?"
        ),
    },
    {
        "id": "Q2",
        "title": "Urban Heat Island — Multi-Year LST Analysis",
        "difficulty": "Hard",
        "expected_tools": ["mean", "difference", "sens_slope", "mann_kendall_test", "detect_seasonality_acf", "autocorrelation_function", "skewness", "kurtosis"],
        "question": (
            "Land Surface Temperature (LST) was extracted from MODIS Terra for an urban center and a nearby rural reference "
            "station over 24 months (2023-2024). The Urban Heat Island (UHI) intensity has already been computed as "
            "Urban_LST - Rural_LST (in degrees Celsius) for each month:\n\n"
            "UHI intensity (°C): [3.1, 3.3, 4.3, 5.2, 5.3, 5.9, 6.5, 6.5, 5.9, 4.7, 3.9, 3.7, "  # 2023
            "3.7, 3.9, 4.7, 6.0, 6.3, 6.8, 6.6, 6.6, 6.8, 5.6, 4.5, 4.2]\n\n"  # 2024
            "Additionally, the urban LST in Celsius was:\n"
            "Urban (°C): [28.05, 29.65, 35.35, 42.15, 48.95, 55.25, 59.45, 58.75, 52.55, 44.05, 35.95, 30.35, "
            "29.35, 30.95, 37.05, 44.65, 51.35, 57.75, 61.95, 61.05, 55.15, 46.65, 38.35, 32.05]\n\n"
            "Perform the following comprehensive analysis:\n"
            "1. Compute the mean UHI intensity across all 24 months\n"
            "2. Compute the mean UHI for Year 1 (months 1-12) and Year 2 (months 13-24) separately. "
            "Calculate the difference (Year 2 mean minus Year 1 mean) to see if UHI is intensifying.\n"
            "3. Calculate the skewness and kurtosis of the UHI intensity series\n"
            "4. Run autocorrelation analysis (nlags=12) on the UHI series to check for temporal patterns\n"
            "5. Detect seasonality in the UHI series using detect_seasonality_acf\n"
            "6. Compute Sen's Slope for the UHI series to estimate the trend magnitude\n"
            "7. Run Mann-Kendall test on the UHI series to test for statistically significant trend\n"
            "8. Also compute the coefficient of variation of urban LST to assess temperature variability\n"
            "9. Scientific interpretation: Is the UHI effect intensifying year-over-year? Is it seasonal? "
            "What are the implications for urban planning and heat mitigation strategies?"
        ),
    },
    {
        "id": "Q3",
        "title": "Fire Season Analysis — FRP Anomaly + Trend",
        "difficulty": "Hard",
        "expected_tools": ["mean", "max_value_and_index", "min_value_and_index", "percentage_change", "detect_change_points", "mann_kendall_test", "sens_slope", "count_spikes_from_values", "compute_linear_trend", "coefficient_of_variation"],
        "question": (
            "MODIS Active Fire Radiative Power (FRP, MW) monthly aggregates for a savanna region over 3 years:\n\n"
            "Year 1 (2022): [12.5, 8.3, 5.1, 3.2, 2.1, 1.5, 45.8, 89.3, 156.2, 78.4, 35.6, 18.9]\n"
            "Year 2 (2023): [15.8, 10.2, 6.8, 4.1, 2.8, 1.9, 52.3, 112.7, 198.5, 95.6, 42.1, 22.4]\n"
            "Year 3 (2024): [19.2, 13.5, 8.9, 5.6, 3.5, 2.3, 68.9, 145.3, 267.8, 128.9, 58.7, 29.8]\n\n"
            "Full 36-month series:\n"
            "[12.5, 8.3, 5.1, 3.2, 2.1, 1.5, 45.8, 89.3, 156.2, 78.4, 35.6, 18.9, "
            "15.8, 10.2, 6.8, 4.1, 2.8, 1.9, 52.3, 112.7, 198.5, 95.6, 42.1, 22.4, "
            "19.2, 13.5, 8.9, 5.6, 3.5, 2.3, 68.9, 145.3, 267.8, 128.9, 58.7, 29.8]\n\n"
            "Conduct a comprehensive fire season analysis:\n"
            "1. Compute the annual mean FRP for each year and the percentage change between Year 1 and Year 3\n"
            "2. Identify the month with peak FRP for each year (use max_value_and_index on each 12-month segment)\n"
            "3. Detect FRP spikes in the full series using a threshold of 30 MW\n"
            "4. Compute the coefficient of variation for each year to assess fire variability\n"
            "5. Fit a linear trend to the annual peak FRP values [156.2, 198.5, 267.8]\n"
            "6. Run Mann-Kendall test on the full 36-month series\n"
            "7. Compute Sen's Slope on the full series for robust trend estimation\n"
            "8. Detect change points in the full series\n"
            "9. Scientific assessment: Is fire activity increasing? What is the rate of increase? "
            "What does this suggest about land management or climate change impacts on this savanna ecosystem?"
        ),
    },
]

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
    WHITE = "\033[37m"
    RESET = "\033[0m"


def print_header(text, color=C.CYAN):
    print(f"\n{color}{C.BOLD}{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}{C.RESET}\n")


def print_step(label, content, color=C.GREEN):
    tag = f"{color}{C.BOLD}[{label}]{C.RESET}"
    lines = str(content).split("\n")
    print(f"{tag} {lines[0]}")
    for line in lines[1:]:
        print(f"  {' ' * len(label)}  {line}")


# ── Run a Single Query ───────────────────────────────────────────────────────

async def run_query(agent, query, trajectory_list):
    """Run one EO query through the agent and display results."""

    print_header(f"[{query['id']}] {query['title']} (Difficulty: {query['difficulty']})", C.YELLOW)
    print(f"{C.DIM}Expected tools: {', '.join(query['expected_tools'])}{C.RESET}\n")
    print(query["question"][:300] + "...\n")

    trajectory = {
        "query_id": query["id"],
        "title": query["title"],
        "difficulty": query["difficulty"],
        "question": query["question"],
        "steps": [],
        "start_time": datetime.now().isoformat(),
    }

    try:
        response = await agent.ainvoke(
            {
                "messages": [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=query["question"]),
                ]
            },
            config={"recursion_limit": 60},
        )

        step_count = 0
        tools_used = set()

        for msg in response["messages"]:
            if msg.type == "system":
                continue

            elif msg.type == "ai":
                # Text reasoning
                if msg.content and isinstance(msg.content, str) and msg.content.strip():
                    step_count += 1
                    # Truncate long thinking for display
                    display_text = msg.content if len(msg.content) < 500 else msg.content[:500] + "..."
                    print_step("THINK", display_text, C.CYAN)
                    trajectory["steps"].append({"type": "think", "step": step_count, "content": msg.content})

                elif msg.content and isinstance(msg.content, list):
                    for block in msg.content:
                        if isinstance(block, dict):
                            if block.get("type") == "text" and block.get("text", "").strip():
                                step_count += 1
                                text = block["text"]
                                display_text = text if len(text) < 500 else text[:500] + "..."
                                print_step("THINK", display_text, C.CYAN)
                                trajectory["steps"].append({"type": "think", "step": step_count, "content": text})
                            elif block.get("type") == "tool_use":
                                tool_name = block.get("name", "unknown")
                                tools_used.add(tool_name)
                                tool_input = block.get("input", {})
                                print_step("TOOL", f"{tool_name}({json.dumps(tool_input, default=str)[:150]})", C.GREEN)
                                trajectory["steps"].append({"type": "tool_call", "tool": tool_name, "input": tool_input})

                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_name = tc.get("name", "unknown")
                        tools_used.add(tool_name)
                        tool_args = tc.get("args", {})
                        print_step("TOOL", f"{tool_name}({json.dumps(tool_args, default=str)[:150]})", C.GREEN)
                        trajectory["steps"].append({"type": "tool_call", "tool": tool_name, "input": tool_args})

            elif msg.type == "tool":
                result_str = str(msg.content)[:300]
                print_step("RESULT", result_str, C.BLUE)
                trajectory["steps"].append({"type": "tool_result", "content": msg.content})

        # Extract final answer
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

            print_header(f"FINAL ANSWER — {query['id']}", C.GREEN)
            print(final_text)
            trajectory["final_answer"] = final_text
        else:
            trajectory["final_answer"] = None

        trajectory["end_time"] = datetime.now().isoformat()
        trajectory["tools_used"] = list(tools_used)
        trajectory["tool_call_count"] = len([s for s in trajectory["steps"] if s["type"] == "tool_call"])
        trajectory["think_step_count"] = step_count

        # Coverage check
        expected = set(query["expected_tools"])
        covered = tools_used & expected
        missed = expected - tools_used
        extra = tools_used - expected

        print(f"\n{C.BOLD}📊 Query Stats:{C.RESET}")
        print(f"  • Think steps: {step_count}")
        print(f"  • Tool calls: {trajectory['tool_call_count']}")
        print(f"  • Tools used: {', '.join(sorted(tools_used))}")
        print(f"  • Expected coverage: {len(covered)}/{len(expected)} ({', '.join(sorted(covered))})")
        if missed:
            print(f"  {C.YELLOW}• Missed tools: {', '.join(sorted(missed))}{C.RESET}")
        if extra:
            print(f"  {C.DIM}• Extra tools: {', '.join(sorted(extra))}{C.RESET}")

        trajectory["coverage"] = {
            "expected": list(expected),
            "used": list(tools_used),
            "covered": list(covered),
            "missed": list(missed),
            "extra": list(extra),
        }

    except Exception as e:
        print(f"{C.RED}ERROR: {e}{C.RESET}")
        trajectory["error"] = str(e)

    trajectory_list.append(trajectory)
    return trajectory


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print_header("EARTH-AGENT COMPLEX EO QUERIES", C.MAGENTA)
    print(f"{C.DIM}Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Model: claude-sonnet-4-20250514")
    print(f"Queries: {len(QUERIES)}{C.RESET}\n")

    # Check API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print(f"{C.RED}ERROR: ANTHROPIC_API_KEY not set.{C.RESET}")
        sys.exit(1)

    # Init LLM
    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        api_key=api_key,
        temperature=0.1,
        max_tokens=8192,
    )
    print(f"{C.GREEN}✓ LLM initialized{C.RESET}")

    # Boot MCP + create agent
    print(f"{C.YELLOW}⏳ Booting MCP servers...{C.RESET}")
    client = MultiServerMCPClient(MCP_SERVERS)
    tools = await client.get_tools()
    print(f"{C.GREEN}✓ Loaded {len(tools)} tools{C.RESET}")

    agent = create_react_agent(llm, tools)

    # Select which query to run
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=int, default=None, help="Query index (1-3), or omit for all")
    args, _ = parser.parse_known_args()

    if args.query:
        queries_to_run = [QUERIES[args.query - 1]]
    else:
        queries_to_run = QUERIES

    # Run queries
    all_trajectories = []
    for query in queries_to_run:
        await run_query(agent, query, all_trajectories)
        print(f"\n{'─' * 70}\n")

    # Save all trajectories
    output_path = DEMO_OUTPUT_DIR / "complex_eo_trajectories.json"
    with open(output_path, "w") as f:
        json.dump(all_trajectories, f, indent=2, default=str)
    print(f"\n{C.DIM}All trajectories saved to: {output_path}{C.RESET}")

    # Final summary
    print_header("OVERALL SUMMARY", C.MAGENTA)
    for traj in all_trajectories:
        status = "✅" if not traj.get("error") else "❌"
        coverage = traj.get("coverage", {})
        covered_pct = (
            f"{len(coverage.get('covered', []))}/{len(coverage.get('expected', []))}"
            if coverage else "N/A"
        )
        print(f"  {status} {traj['query_id']}: {traj['title']}")
        print(f"     Tools: {traj.get('tool_call_count', 0)} calls | Coverage: {covered_pct}")
        if traj.get("error"):
            print(f"     {C.RED}Error: {traj['error'][:80]}{C.RESET}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
