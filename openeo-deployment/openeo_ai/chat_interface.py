# ABOUTME: Interactive terminal chat interface for OpenEO AI Assistant.
# Provides conversational Earth Observation analysis with visualization output.

"""
OpenEO AI Chat Interface

Interactive terminal-based chat for Earth Observation analysis.
Supports natural language queries, job management, and result visualization.
Integrates all OpenEO, GeoAI, and visualization tools.
"""

import asyncio
import json
import os
import sys
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# Rich for terminal UI (install with: pip install rich)
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt
    from rich.tree import Tree
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from .sdk.client import OpenEOAIClient, OpenEOAIConfig, TOOL_DEFINITIONS


class ChatInterface:
    """
    Interactive chat interface for OpenEO AI Assistant.

    Features:
    - Natural language Earth Observation analysis
    - Session persistence across conversations
    - Visualization output (maps, charts)
    - Job management and monitoring
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        output_dir: str = "outputs"
    ):
        """
        Initialize chat interface.

        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            output_dir: Directory for saving visualizations and results
        """
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key

        self.config = OpenEOAIConfig()
        self.client = OpenEOAIClient(config=self.config)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.session_id: Optional[str] = None
        self.user_id = "chat_user"
        self.history: list = []

        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None

    def print(self, *args, **kwargs):
        """Print with rich if available, else plain print."""
        if self.console:
            self.console.print(*args, **kwargs)
        else:
            print(*args, **kwargs)

    def print_markdown(self, text: str):
        """Print markdown formatted text."""
        if self.console:
            self.console.print(Markdown(text))
        else:
            print(text)

    def print_panel(self, content: str, title: str = "", style: str = "blue"):
        """Print a bordered panel."""
        if self.console:
            self.console.print(Panel(content, title=title, border_style=style))
        else:
            print(f"\n{'='*50}")
            if title:
                print(f" {title}")
                print(f"{'='*50}")
            print(content)
            print(f"{'='*50}\n")

    def print_json(self, data: dict, title: str = ""):
        """Print formatted JSON."""
        formatted = json.dumps(data, indent=2)
        if self.console:
            syntax = Syntax(formatted, "json", theme="monokai", line_numbers=False)
            if title:
                self.console.print(Panel(syntax, title=title, border_style="green"))
            else:
                self.console.print(syntax)
        else:
            if title:
                print(f"\n{title}:")
            print(formatted)

    def print_welcome(self):
        """Print welcome message."""
        welcome = """
# OpenEO AI Assistant

Welcome! I can help you with Earth Observation data analysis.

## What I can do:
- **Data Discovery**: Find satellite data (Sentinel-2, Landsat, DEMs)
- **Process Graphs**: Generate analysis workflows from natural language
- **Job Management**: Create, run, and monitor batch jobs
- **Visualization**: Display results on maps and charts
- **AI Analysis**: Segmentation, change detection, canopy height

## Commands:
- Type your question or request naturally
- `/help` - Show this help message
- `/tools` - List all available AI tools
- `/collections` - List available data collections
- `/validate <json>` - Validate a process graph
- `/job create <title>` - Create a new batch job
- `/job start <id>` - Start a batch job
- `/status <job_id>` - Check job status
- `/results <job_id>` - Get job results
- `/segment <path>` - Run AI segmentation
- `/detect-change <before> <after>` - Detect changes
- `/canopy <path>` - Estimate canopy height
- `/map <path>` - Show map visualization
- `/history` - Show conversation history
- `/save` - Save current session
- `/clear` - Clear conversation history
- `/quit` or `/exit` - Exit the chat

## Example queries:
- "Show me available Sentinel-2 data collections"
- "Create NDVI analysis for Munich area in summer 2024"
- "Validate my process graph"
- "What's the status of job abc-123?"
- "Run segmentation on my GeoTIFF file"
"""
        self.print_markdown(welcome)

    def print_thinking(self):
        """Show thinking indicator."""
        if self.console:
            return self.console.status("[bold blue]Thinking...", spinner="dots")
        return None

    async def process_message(self, user_input: str) -> None:
        """
        Process user message and display response.

        Args:
            user_input: User's message
        """
        # Handle commands
        if user_input.startswith("/"):
            await self._handle_command(user_input)
            return

        # Add to history
        self.history.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat()
        })

        # Show thinking indicator
        self.print("\n[bold blue]🤖 Assistant:[/bold blue]" if self.console else "\n🤖 Assistant:")

        # Process through AI
        full_response = ""
        tool_results = []
        visualizations = []

        try:
            async for response in self.client.chat(
                user_input,
                user_id=self.user_id,
                session_id=self.session_id
            ):
                resp_type = response.get("type")

                if resp_type == "text":
                    content = response.get("content", "")
                    full_response += content
                    self.print_markdown(content)

                elif resp_type == "tool_result":
                    tool_name = response.get("tool", "unknown")
                    result = response.get("result", {})
                    tool_results.append((tool_name, result))

                    self.print(f"\n[dim]📦 Tool: {tool_name}[/dim]" if self.console else f"\n📦 Tool: {tool_name}")

                    # Format tool result with specialized display
                    self._display_tool_result(tool_name, result)

                elif resp_type == "visualization":
                    viz = response.get("content", {})
                    visualizations.append(viz)
                    await self._display_visualization(viz)

                elif resp_type == "tool_error":
                    error = response.get("error", "Unknown error")
                    self.print(f"\n[red]❌ Tool Error: {error}[/red]" if self.console else f"\n❌ Tool Error: {error}")

                elif resp_type == "session":
                    self.session_id = response.get("session_id")

        except Exception as e:
            self.print(f"\n[red]Error: {e}[/red]" if self.console else f"\nError: {e}")

        # Add response to history
        self.history.append({
            "role": "assistant",
            "content": full_response,
            "tools_used": [t[0] for t in tool_results],
            "visualizations": len(visualizations),
            "timestamp": datetime.now().isoformat()
        })

    def _summarize_result(self, tool_name: str, result: dict) -> str:
        """Summarize large tool results."""
        if "collections" in str(tool_name).lower():
            if isinstance(result, list):
                return f"   Found {len(result)} collections"
        if "valid" in result:
            valid = result.get("valid", False)
            warnings = len(result.get("warnings", []))
            suggestions = len(result.get("suggestions", []))
            return f"   Valid: {valid}, Warnings: {warnings}, Suggestions: {suggestions}"
        if "id" in result and "status" in result:
            return f"   Job ID: {result['id']}, Status: {result['status']}"
        return f"   Result: {str(result)[:200]}..."

    def _display_tool_result(self, tool_name: str, result: Any) -> None:
        """Display tool result with appropriate formatting."""
        if not self.console:
            if isinstance(result, dict):
                print(json.dumps(result, indent=2)[:500])
            else:
                print(f"Result: {result}")
            return

        # Handle different tool result types
        if "list_collections" in tool_name:
            self._display_collections_result(result)
        elif "validate" in tool_name:
            self._display_validation_result(result)
        elif "job" in tool_name and isinstance(result, dict):
            self._display_job_result(result)
        elif "segment" in tool_name:
            self._display_segmentation_result(result)
        elif isinstance(result, dict):
            if len(str(result)) < 1000:
                self.print_json(result)
            else:
                self.print(self._summarize_result(tool_name, result))
        else:
            self.print(f"   {result}")

    def _display_collections_result(self, result: Any) -> None:
        """Display collections in a table."""
        if not isinstance(result, list):
            self.print_json(result if isinstance(result, dict) else {"result": result})
            return

        table = Table(title=f"Available Collections ({len(result)})")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Description", max_width=50)

        for coll in result[:10]:  # Show first 10
            table.add_row(
                coll.get("id", "N/A"),
                coll.get("title", "N/A")[:30],
                (coll.get("description", "")[:50] + "...") if len(coll.get("description", "")) > 50 else coll.get("description", "")
            )

        if len(result) > 10:
            table.add_row("...", f"and {len(result) - 10} more", "")

        self.console.print(table)

    def _display_validation_result(self, result: Any) -> None:
        """Display validation result."""
        if not isinstance(result, dict):
            self.print(f"Validation: {result}")
            return

        valid = result.get("valid", False)
        status = "[green]✓ Valid[/green]" if valid else "[red]✗ Invalid[/red]"
        self.console.print(f"\n{status}")

        errors = result.get("errors", [])
        warnings = result.get("warnings", [])
        suggestions = result.get("suggestions", [])

        if errors:
            self.console.print("\n[red]Errors:[/red]")
            for err in errors:
                self.console.print(f"  • {err}")

        if warnings:
            self.console.print("\n[yellow]Warnings:[/yellow]")
            for warn in warnings[:5]:
                self.console.print(f"  • {warn}")
            if len(warnings) > 5:
                self.console.print(f"  ... and {len(warnings) - 5} more")

        if suggestions:
            self.console.print("\n[blue]Suggestions:[/blue]")
            for sug in suggestions[:3]:
                self.console.print(f"  • {sug}")
            if len(suggestions) > 3:
                self.console.print(f"  ... and {len(suggestions) - 3} more")

    def _display_job_result(self, result: dict) -> None:
        """Display job information."""
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="dim")
        table.add_column("Value")

        job_id = result.get("id", result.get("job_id", "N/A"))
        status = result.get("status", "N/A")

        status_colors = {
            "created": "blue",
            "queued": "yellow",
            "running": "cyan",
            "finished": "green",
            "error": "red",
            "canceled": "dim"
        }
        status_color = status_colors.get(status.lower() if isinstance(status, str) else "", "white")

        table.add_row("Job ID", str(job_id))
        table.add_row("Status", f"[{status_color}]{status}[/{status_color}]")

        if "title" in result:
            table.add_row("Title", result["title"])
        if "created" in result:
            table.add_row("Created", result["created"])
        if "progress" in result:
            table.add_row("Progress", f"{result['progress']}%")

        self.console.print(table)

    def _display_segmentation_result(self, result: Any) -> None:
        """Display segmentation result."""
        if not isinstance(result, dict):
            self.print(f"Segmentation: {result}")
            return

        self.console.print("\n[green]✓ Segmentation Complete[/green]")

        if "output_path" in result:
            self.console.print(f"   Output: {result['output_path']}")

        if "classes" in result:
            classes = result["classes"]
            table = Table(title="Detected Classes")
            table.add_column("Class")
            table.add_column("Pixels", justify="right")
            table.add_column("Percentage", justify="right")

            for cls in classes[:8]:
                table.add_row(
                    cls.get("name", "Unknown"),
                    str(cls.get("pixels", "N/A")),
                    f"{cls.get('percentage', 0):.1f}%"
                )

            self.console.print(table)

    async def _display_visualization(self, viz: dict) -> None:
        """
        Display or save visualization.

        Args:
            viz: Visualization component spec
        """
        viz_type = viz.get("type", "unknown")
        spec = viz.get("spec", {})
        title = spec.get("title", "Visualization")

        if self.console:
            self.console.print(Panel(
                f"Type: {viz_type}\nTitle: {title}",
                title="📊 Visualization",
                border_style="green"
            ))
        else:
            self.print(f"\n📊 Visualization: {title}")
            self.print(f"   Type: {viz_type}")

        if viz_type == "map":
            # Save map data
            layers = spec.get("layers", [])
            saved_files = []
            for i, layer in enumerate(layers):
                if "url" in layer and layer["url"].startswith("data:image"):
                    # Extract base64 image
                    img_data = layer["url"].split(",")[1]
                    img_path = self.output_dir / f"map_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}.png"
                    img_path.write_bytes(base64.b64decode(img_data))
                    saved_files.append(str(img_path))

            if saved_files:
                self.print(f"   [green]✓ Saved {len(saved_files)} file(s):[/green]" if self.console else f"   ✓ Saved {len(saved_files)} file(s):")
                for f in saved_files:
                    self.print(f"     {f}")

            # Show map info in a table
            if self.console:
                table = Table(show_header=False, box=None)
                table.add_column("Property", style="dim")
                table.add_column("Value")

                center = spec.get("center", [0, 0])
                table.add_row("Center", f"{center[0]:.4f}, {center[1]:.4f}")
                table.add_row("Zoom", str(spec.get("zoom", "auto")))

                if "colorbar" in spec:
                    cb = spec["colorbar"]
                    table.add_row("Value Range", f"{cb.get('min', 'N/A')} to {cb.get('max', 'N/A')}")
                    if "label" in cb:
                        table.add_row("Label", cb["label"])

                self.console.print(table)
            else:
                center = spec.get("center", [0, 0])
                self.print(f"   Center: {center[0]:.4f}, {center[1]:.4f}")
                if "colorbar" in spec:
                    cb = spec["colorbar"]
                    self.print(f"   Range: {cb.get('min', 'N/A')} to {cb.get('max', 'N/A')}")

        elif viz_type == "chart":
            chart_type = spec.get("chart_type", "unknown")
            self.print(f"   Chart Type: {chart_type}")

            if "statistics" in spec:
                stats = spec["statistics"]
                if self.console:
                    table = Table(title="Statistics", show_header=True)
                    table.add_column("Metric")
                    table.add_column("Value", justify="right")
                    for key, val in stats.items():
                        if isinstance(val, float):
                            table.add_row(key.title(), f"{val:.4f}")
                        else:
                            table.add_row(key.title(), str(val))
                    self.console.print(table)
                else:
                    self.print(f"   Stats: min={stats.get('min', 'N/A'):.2f}, max={stats.get('max', 'N/A'):.2f}, mean={stats.get('mean', 'N/A'):.2f}")

            # Save chart data if available
            if "data" in spec:
                data_path = self.output_dir / f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                data_path.write_text(json.dumps(spec["data"], indent=2))
                self.print(f"   [green]✓ Chart data saved: {data_path}[/green]" if self.console else f"   ✓ Chart data saved: {data_path}")

        elif viz_type == "comparison_slider":
            if self.console:
                table = Table(show_header=False, box=None)
                table.add_column("", style="dim")
                table.add_column("Label")
                table.add_row("Before", spec.get('before', {}).get('label', 'N/A'))
                table.add_row("After", spec.get('after', {}).get('label', 'N/A'))
                self.console.print(table)
            else:
                self.print(f"   Before: {spec.get('before', {}).get('label', 'N/A')}")
                self.print(f"   After: {spec.get('after', {}).get('label', 'N/A')}")

        elif viz_type == "segmentation":
            classes = spec.get("classes", [])
            if classes:
                self.print(f"   Detected {len(classes)} classes:")
                for cls in classes[:5]:  # Show first 5
                    name = cls.get("name", "Unknown")
                    color = cls.get("color", "#000000")
                    self.print(f"     • {name} ({color})")
                if len(classes) > 5:
                    self.print(f"     ... and {len(classes) - 5} more")

    async def _handle_command(self, command: str) -> None:
        """Handle slash commands."""
        cmd = command.strip()
        cmd_lower = cmd.lower()

        if cmd_lower in ["/quit", "/exit", "/q"]:
            self.print("\n[yellow]Goodbye! 👋[/yellow]" if self.console else "\nGoodbye! 👋")
            sys.exit(0)

        elif cmd_lower == "/help":
            self.print_welcome()

        elif cmd_lower == "/tools":
            self._show_tools()

        elif cmd_lower == "/collections":
            await self.process_message("List all available Earth Observation data collections with their descriptions.")

        elif cmd_lower.startswith("/validate "):
            # Direct process graph validation
            graph_json = cmd.replace("/validate ", "", 1).strip()
            await self.process_message(f"Please validate this process graph: {graph_json}")

        elif cmd_lower.startswith("/job "):
            await self._handle_job_command(cmd.replace("/job ", "", 1).strip())

        elif cmd_lower.startswith("/status "):
            job_id = cmd.replace("/status ", "", 1).strip()
            await self.process_message(f"What is the status of job {job_id}?")

        elif cmd_lower.startswith("/results "):
            job_id = cmd.replace("/results ", "", 1).strip()
            await self.process_message(f"Get the results for job {job_id}")

        elif cmd_lower.startswith("/segment "):
            path = cmd.replace("/segment ", "", 1).strip()
            await self.process_message(f"Run semantic segmentation on the file at {path}")

        elif cmd_lower.startswith("/detect-change "):
            args = cmd.replace("/detect-change ", "", 1).strip().split()
            if len(args) >= 2:
                await self.process_message(f"Detect changes between {args[0]} (before) and {args[1]} (after)")
            else:
                self.print("[yellow]Usage: /detect-change <before_path> <after_path>[/yellow]" if self.console else "Usage: /detect-change <before_path> <after_path>")

        elif cmd_lower.startswith("/canopy "):
            path = cmd.replace("/canopy ", "", 1).strip()
            await self.process_message(f"Estimate canopy height for the RGB image at {path}")

        elif cmd_lower.startswith("/map "):
            path = cmd.replace("/map ", "", 1).strip()
            await self.process_message(f"Show a map visualization of the raster file at {path}")

        elif cmd_lower == "/history":
            self._show_history()

        elif cmd_lower == "/clear":
            self.history = []
            self.session_id = None
            self.print("[green]✓ Conversation cleared[/green]" if self.console else "✓ Conversation cleared")

        elif cmd_lower == "/save":
            self._save_session()

        elif cmd_lower == "/session":
            self.print(f"Session ID: {self.session_id or 'None'}")
            self.print(f"Messages: {len(self.history)}")

        else:
            self.print(f"[yellow]Unknown command: {cmd}[/yellow]" if self.console else f"Unknown command: {cmd}")
            self.print("Type /help for available commands")

    async def _handle_job_command(self, subcommand: str) -> None:
        """Handle /job subcommands."""
        parts = subcommand.split(maxsplit=1)
        action = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        if action == "create":
            if args:
                await self.process_message(f"Create a batch job titled '{args}'")
            else:
                self.print("[yellow]Usage: /job create <title>[/yellow]" if self.console else "Usage: /job create <title>")

        elif action == "start":
            if args:
                await self.process_message(f"Start the batch job with ID {args}")
            else:
                self.print("[yellow]Usage: /job start <job_id>[/yellow]" if self.console else "Usage: /job start <job_id>")

        elif action == "list":
            await self.process_message("List all my batch jobs")

        else:
            self.print("[yellow]Job commands: create <title>, start <id>, list[/yellow]" if self.console else "Job commands: create <title>, start <id>, list")

    def _show_tools(self) -> None:
        """Display all available AI tools."""
        if self.console:
            # Group tools by category
            categories = {
                "Data Discovery": [],
                "Process Graphs": [],
                "Job Management": [],
                "GeoAI Analysis": [],
                "Visualization": []
            }

            for tool in TOOL_DEFINITIONS:
                name = tool["name"]
                desc = tool["description"][:80] + "..." if len(tool["description"]) > 80 else tool["description"]

                if name.startswith("openeo_list") or name.startswith("openeo_get_collection"):
                    categories["Data Discovery"].append((name, desc))
                elif name.startswith("openeo_validate") or name.startswith("openeo_generate"):
                    categories["Process Graphs"].append((name, desc))
                elif name.startswith("openeo_") and ("job" in name or "result" in name):
                    categories["Job Management"].append((name, desc))
                elif name.startswith("geoai_"):
                    categories["GeoAI Analysis"].append((name, desc))
                elif name.startswith("viz_"):
                    categories["Visualization"].append((name, desc))

            tree = Tree("[bold blue]Available AI Tools[/bold blue]")

            for category, tools in categories.items():
                if tools:
                    branch = tree.add(f"[bold cyan]{category}[/bold cyan]")
                    for name, desc in tools:
                        branch.add(f"[green]{name}[/green]: {desc}")

            self.console.print(tree)
            self.console.print("\n[dim]These tools are used automatically when you ask questions naturally.[/dim]")
        else:
            print("\n=== Available AI Tools ===\n")
            for tool in TOOL_DEFINITIONS:
                print(f"• {tool['name']}")
                print(f"  {tool['description'][:100]}...")
                print()

    def _show_history(self) -> None:
        """Display conversation history."""
        if not self.history:
            self.print("No conversation history.")
            return

        if self.console:
            table = Table(title="Conversation History")
            table.add_column("Time", style="dim")
            table.add_column("Role", style="bold")
            table.add_column("Content", max_width=60)

            for msg in self.history[-10:]:  # Last 10 messages
                time = msg.get("timestamp", "")[:19]
                role = msg.get("role", "").upper()
                content = msg.get("content", "")[:100]
                if len(msg.get("content", "")) > 100:
                    content += "..."
                table.add_row(time, role, content)

            self.console.print(table)
        else:
            for msg in self.history[-10:]:
                print(f"[{msg.get('timestamp', '')[:19]}] {msg.get('role', '').upper()}: {msg.get('content', '')[:100]}")

    def _save_session(self) -> None:
        """Save session to file."""
        session_file = self.output_dir / f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data = {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "history": self.history,
            "saved_at": datetime.now().isoformat()
        }
        session_file.write_text(json.dumps(data, indent=2))
        self.print(f"[green]✓ Session saved: {session_file}[/green]" if self.console else f"✓ Session saved: {session_file}")

    async def run(self) -> None:
        """Run the interactive chat loop."""
        self.print_welcome()

        while True:
            try:
                # Get user input
                if self.console:
                    user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
                else:
                    user_input = input("\nYou: ")

                if not user_input.strip():
                    continue

                await self.process_message(user_input.strip())

            except KeyboardInterrupt:
                self.print("\n[yellow]Interrupted. Type /quit to exit.[/yellow]" if self.console else "\nInterrupted. Type /quit to exit.")
            except EOFError:
                break


async def main():
    """Main entry point for chat interface."""
    import argparse

    parser = argparse.ArgumentParser(description="OpenEO AI Chat Interface")
    parser.add_argument("--api-key", help="Anthropic API key")
    parser.add_argument("--output-dir", default="outputs", help="Output directory for visualizations")
    args = parser.parse_args()

    chat = ChatInterface(
        api_key=args.api_key,
        output_dir=args.output_dir
    )
    await chat.run()


def run_chat():
    """Entry point for running chat from command line."""
    asyncio.run(main())


if __name__ == "__main__":
    run_chat()
