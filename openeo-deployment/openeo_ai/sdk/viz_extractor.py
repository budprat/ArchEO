"""Extract visualization data from tool results for WebSocket delivery.

Extracted from web_interface.py to avoid circular imports when the
Claude Agent SDK bridge hooks need to call extract_visualization().
"""

import json
from typing import Any, Dict, Optional


def extract_visualization(tool_name: str, result: Any, title_hint: str = "") -> Optional[Dict[str, Any]]:
    """Extract visualization data from tool result.

    Args:
        tool_name: Name of the tool that produced the result.
        result: The tool result data.
        title_hint: Optional descriptive title (e.g. from openeo_create_job title arg).
    """
    print(f"[extract_visualization] tool_name={tool_name}, result type={type(result)}")

    if tool_name == "viz_show_map":
        # Result from create_raster_map: {type: "map", spec: {layers: [{bounds, url, ...}], ...}}
        if isinstance(result, dict) and "spec" in result:
            spec = result["spec"]
            layers = spec.get("layers", [])
            if layers:
                layer = layers[0]
                viz = {
                    "type": "map",
                    "data": {
                        "type": "raster",
                        "url": layer.get("url", ""),
                        "bounds": layer.get("bounds"),
                        "colormap": layer.get("colormap", "viridis"),
                        "opacity": layer.get("opacity", 0.8),
                        "vmin": layer.get("vmin"),
                        "vmax": layer.get("vmax"),
                        "source": layer.get("source"),
                        "colorbar": spec.get("colorbar"),
                    },
                    "title": spec.get("title") or title_hint or "Map"
                }
                print(f"[extract_visualization] viz_show_map visualization: {json.dumps(viz, indent=2)[:500]}")
                # Auto-save to permanent archive
                _source = layer.get("source", "")
                if _source and _source.startswith("/tmp/") and _source.endswith((".tif", ".tiff")):
                    try:
                        from ..storage.job_archive import save_job
                        _viz_title = spec.get("title") or title_hint or "Map"
                        save_job(source_path=_source, title=_viz_title,
                                 bounds=layer.get("bounds"), colormap=layer.get("colormap", "viridis"),
                                 vmin=layer.get("vmin"), vmax=layer.get("vmax"))
                    except Exception as _e:
                        print(f"[auto-save] Failed to archive viz_show_map: {_e}")
                return viz
        print(f"[extract_visualization] viz_show_map: invalid result structure")
        return None
    elif tool_name == "viz_show_time_series":
        return {"type": "chart", "spec": result}
    elif tool_name == "openeo_quality_metrics":
        return {"type": "quality_dashboard", "spec": result}

    # Handle results with output_path (e.g., from openeo_get_results)
    if isinstance(result, dict):
        output_path = result.get("output_path") or result.get("path")
        if output_path and (output_path.endswith(".tif") or output_path.endswith(".tiff") or output_path.endswith(".png")):
            bounds = result.get("bounds") or result.get("bbox")
            print(f"[extract_visualization] Creating map viz: path={output_path}, bounds={bounds}")

            # Create map visualization from raster result
            colormap = result.get("colormap", "viridis")
            viz = {
                "type": "map",
                "data": {
                    "type": "raster",
                    "url": f"/render-raster?path={output_path}&colormap={colormap}",
                    "bounds": bounds,
                    "colormap": colormap,
                    "opacity": 0.8,
                    "vmin": result.get("vmin"),
                    "vmax": result.get("vmax"),
                    "source": output_path,
                },
                "title": result.get("title") or title_hint or "Result"
            }
            print(f"[extract_visualization] Visualization: {json.dumps(viz, indent=2)}")
            # Auto-save to permanent archive
            if output_path.startswith("/tmp/"):
                try:
                    from ..storage.job_archive import save_job
                    _save_title = result.get("title") or title_hint or "Result"
                    save_job(source_path=output_path, title=_save_title,
                             bounds=bounds, colormap=colormap,
                             vmin=result.get("vmin"), vmax=result.get("vmax"))
                except Exception as _e:
                    print(f"[auto-save] Failed to archive result: {_e}")
            return viz

        # Handle process graph visualization
        if tool_name == "openeo_generate_graph" and "process_graph" in result:
            return {
                "type": "process_graph",
                "data": {
                    "nodes": [
                        {"id": k, "process_id": v.get("process_id", ""), "arguments": v.get("arguments", {})}
                        for k, v in result.get("process_graph", {}).items()
                    ],
                    "edges": []
                },
                "title": "Process Graph"
            }

    return None
