OpenEO AI Product - Implementation Design                                                                                                                                                     
                                                                                                                                                                                                      
                                                                                                                                                                                                          
    Architecture with Claude SDK Direct Integration                                                                                                                                                   
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    ┌────────────────────────────────────────────────────────────────────────────┐                                                                                                                    
    │                         OPENEO AI ASSISTANT                                 │                                                                                                                   
    │                    (Claude SDK Direct Integration)                          │                                                                                                                   
    ├────────────────────────────────────────────────────────────────────────────┤                                                                                                                    
    │                                                                             │                                                                                                                   
    │  ┌─────────────────────────────────────────────────────────────────────┐   │                                                                                                                    
    │  │                      CLAUDE SDK LAYER                                │   │                                                                                                                   
    │  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────┐   │   │                                                                                                                    
    │  │  │ Query API   │ │ Custom      │ │ Permission  │ │ Session      │   │   │                                                                                                                    
    │  │  │ (streaming) │ │ Tools       │ │ Callbacks   │ │ Management   │   │   │                                                                                                                    
    │  │  └─────────────┘ └─────────────┘ └─────────────┘ └──────────────┘   │   │                                                                                                                    
    │  └─────────────────────────────────────────────────────────────────────┘   │                                                                                                                    
    │                                    │                                        │                                                                                                                   
    │  ┌─────────────────────────────────┼───────────────────────────────────┐   │                                                                                                                    
    │  │                     CUSTOM TOOLS (SDK Registered)                    │   │                                                                                                                   
    │  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐  │   │                                                                                                                    
    │  │  │ openeo_      │ │ openeo_      │ │ geoai_       │ │ viz_       │  │   │                                                                                                                    
    │  │  │ process_*    │ │ job_*        │ │ predict_*    │ │ render_*   │  │   │                                                                                                                    
    │  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘  │   │                                                                                                                    
    │  └─────────────────────────────────────────────────────────────────────┘   │                                                                                                                    
    │                                    │                                        │                                                                                                                   
    │  ┌─────────────────────────────────┼───────────────────────────────────┐   │                                                                                                                    
    │  │                          SERVICE LAYER                               │   │                                                                                                                   
    │  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐  │   │                                                                                                                    
    │  │  │ OpenEO       │ │ Process      │ │ GeoAI        │ │ MCP-UI     │  │   │                                                                                                                    
    │  │  │ Backend      │ │ Graph Store  │ │ Local Models │ │ Renderer   │  │   │                                                                                                                    
    │  │  │ (FastAPI)    │ │ (SQLite)     │ │ (PyTorch)    │ │            │  │   │                                                                                                                    
    │  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘  │   │                                                                                                                    
    │  └─────────────────────────────────────────────────────────────────────┘   │                                                                                                                    
    │                                                                             │                                                                                                                   
    │  ┌─────────────────────────────────────────────────────────────────────┐   │                                                                                                                    
    │  │                       AUTHENTICATION (OIDC)                          │   │                                                                                                                   
    │  │  ┌─────────────────────────────────────────────────────────────┐    │   │                                                                                                                    
    │  │  │ EGI Check-in / Custom OIDC Provider                          │    │   │                                                                                                                   
    │  │  └─────────────────────────────────────────────────────────────┘    │   │                                                                                                                    
    │  └─────────────────────────────────────────────────────────────────────┘   │                                                                                                                    
    └────────────────────────────────────────────────────────────────────────────┘                                                                                                                    
                                                                                                                                                                                                      
    ---                                                                                                                                                                                               
    Project Structure                                                                                                                                                                                 
                                                                                                                                                                                                      
    openeo-ai/                                                                                                                                                                                        
    ├── openeo_ai/                                                                                                                                                                                    
    │   ├── __init__.py                                                                                                                                                                               
    │   ├── main.py                    # Entry point                                                                                                                                                  
    │   │                                                                                                                                                                                             
    │   ├── sdk/                       # Claude SDK Integration                                                                                                                                       
    │   │   ├── __init__.py                                                                                                                                                                           
    │   │   ├── client.py              # Claude SDK client wrapper                                                                                                                                    
    │   │   ├── tools.py               # Custom tool definitions                                                                                                                                      
    │   │   ├── permissions.py         # Permission callbacks                                                                                                                                         
    │   │   └── sessions.py            # Session management                                                                                                                                           
    │   │                                                                                                                                                                                             
    │   ├── tools/                     # Tool Implementations                                                                                                                                         
    │   │   ├── __init__.py                                                                                                                                                                           
    │   │   ├── openeo_tools.py        # OpenEO process tools                                                                                                                                         
    │   │   ├── job_tools.py           # Batch job tools                                                                                                                                              
    │   │   ├── geoai_tools.py         # GeoAI model tools                                                                                                                                            
    │   │   ├── viz_tools.py           # Visualization tools                                                                                                                                          
    │   │   └── validation_tools.py    # Graph validation tools                                                                                                                                       
    │   │                                                                                                                                                                                             
    │   ├── storage/                   # SQLite Storage                                                                                                                                               
    │   │   ├── __init__.py                                                                                                                                                                           
    │   │   ├── database.py            # SQLite connection                                                                                                                                            
    │   │   ├── models.py              # SQLAlchemy models                                                                                                                                            
    │   │   └── repositories.py        # Data access layer                                                                                                                                            
    │   │                                                                                                                                                                                             
    │   ├── geoai/                     # Local GeoAI Models                                                                                                                                           
    │   │   ├── __init__.py                                                                                                                                                                           
    │   │   ├── model_registry.py      # Model management                                                                                                                                             
    │   │   ├── inference.py           # Inference engine                                                                                                                                             
    │   │   └── models/                # Pre-trained models                                                                                                                                           
    │   │       ├── segmentation.py                                                                                                                                                                   
    │   │       ├── change_detection.py                                                                                                                                                               
    │   │       └── canopy_height.py                                                                                                                                                                  
    │   │                                                                                                                                                                                             
    │   ├── visualization/             # MCP-UI Integration                                                                                                                                           
    │   │   ├── __init__.py                                                                                                                                                                           
    │   │   ├── maps.py                # Interactive maps                                                                                                                                             
    │   │   ├── charts.py              # Time series charts                                                                                                                                           
    │   │   └── components.py          # UI components                                                                                                                                                
    │   │                                                                                                                                                                                             
    │   ├── auth/                      # OIDC Authentication                                                                                                                                          
    │   │   ├── __init__.py                                                                                                                                                                           
    │   │   ├── oidc.py                # OIDC client                                                                                                                                                  
    │   │   └── middleware.py          # Auth middleware                                                                                                                                              
    │   │                                                                                                                                                                                             
    │   └── education/                 # Educational Guidance                                                                                                                                         
    │       ├── __init__.py                                                                                                                                                                           
    │       ├── knowledge_base.py      # EO knowledge                                                                                                                                                 
    │       └── tutorials.py           # Guided workflows                                                                                                                                             
    │                                                                                                                                                                                                 
    ├── tests/                                                                                                                                                                                        
    ├── configs/                                                                                                                                                                                      
    │   ├── models.yaml                # GeoAI model configs                                                                                                                                          
    │   └── oidc.yaml                  # OIDC settings                                                                                                                                                
    │                                                                                                                                                                                                 
    ├── data/                                                                                                                                                                                         
    │   └── openeo_ai.db               # SQLite database                                                                                                                                              
    │                                                                                                                                                                                                 
    └── pyproject.toml                                                                                                                                                                                
                                                                                                                                                                                                      
    ---                                                                                                                                                                                               
    1. Claude SDK Client with Custom Tools                                                                                                                                                            
                                                                                                                                                                                                      
    # openeo_ai/sdk/client.py                                                                                                                                                                         
    """                                                                                                                                                                                               
    Claude SDK client for OpenEO AI Assistant.                                                                                                                                                        
    Uses direct SDK integration with custom tools.                                                                                                                                                    
    """                                                                                                                                                                                               
                                                                                                                                                                                                      
    import asyncio                                                                                                                                                                                    
    from typing import AsyncIterator, Any, Optional                                                                                                                                                   
    from claude_agent_sdk import query, ClaudeAgentOptions, HookMatcher                                                                                                                               
    from dataclasses import dataclass                                                                                                                                                                 
                                                                                                                                                                                                      
    from .tools import create_openeo_tools                                                                                                                                                            
    from .permissions import openeo_permission_callback                                                                                                                                               
    from .sessions import SessionManager                                                                                                                                                              
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    @dataclass                                                                                                                                                                                        
    class OpenEOAIConfig:                                                                                                                                                                             
        """Configuration for OpenEO AI Assistant."""                                                                                                                                                  
        model: str = "claude-sonnet-4-5"                                                                                                                                                              
        max_turns: int = 50                                                                                                                                                                           
        openeo_url: str = "http://localhost:8000/openeo/1.1.0"                                                                                                                                        
        sqlite_path: str = "data/openeo_ai.db"                                                                                                                                                        
        geoai_models_path: str = "models/"                                                                                                                                                            
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    class OpenEOAIClient:                                                                                                                                                                             
        """                                                                                                                                                                                           
        OpenEO AI Assistant using Claude SDK.                                                                                                                                                         
                                                                                                                                                                                                      
        Provides conversational interface for:                                                                                                                                                        
        - Natural language → Process graph generation                                                                                                                                                 
        - Process graph validation                                                                                                                                                                    
        - Batch job management                                                                                                                                                                        
        - Result visualization                                                                                                                                                                        
        - GeoAI model inference                                                                                                                                                                       
        """                                                                                                                                                                                           
                                                                                                                                                                                                      
        SYSTEM_PROMPT = """You are an expert Earth Observation assistant powered by OpenEO.                                                                                                           
                                                                                                                                                                                                      
    Your capabilities:                                                                                                                                                                                
    1. **Data Discovery**: Help users find satellite data (Sentinel-2, Landsat, DEMs)                                                                                                                 
    2. **Process Graph Creation**: Convert natural language to OpenEO process graphs                                                                                                                  
    3. **Validation**: Validate process graphs before execution                                                                                                                                       
    4. **Job Management**: Create, monitor, and manage batch processing jobs                                                                                                                          
    5. **Visualization**: Display results on interactive maps and charts                                                                                                                              
    6. **AI Analysis**: Apply GeoAI models (segmentation, change detection, etc.)                                                                                                                     
    7. **Education**: Explain EO concepts, indices, and best practices                                                                                                                                
                                                                                                                                                                                                      
    When helping users:                                                                                                                                                                               
    - Always validate process graphs before execution                                                                                                                                                 
    - Explain what you're doing in accessible terms                                                                                                                                                   
    - Suggest optimizations when appropriate                                                                                                                                                          
    - Warn about large queries that may be slow/expensive                                                                                                                                             
    - Provide educational context for EO newcomers                                                                                                                                                    
                                                                                                                                                                                                      
    Available tools:                                                                                                                                                                                  
    - openeo_list_collections: Discover available data collections                                                                                                                                    
    - openeo_get_collection_info: Get band info for a collection                                                                                                                                      
    - openeo_validate_graph: Validate a process graph                                                                                                                                                 
    - openeo_create_job: Create a batch processing job                                                                                                                                                
    - openeo_start_job: Start a queued job                                                                                                                                                            
    - openeo_get_job_status: Check job status                                                                                                                                                         
    - openeo_get_results: Download job results                                                                                                                                                        
    - geoai_segment: Run segmentation model                                                                                                                                                           
    - geoai_detect_change: Run change detection                                                                                                                                                       
    - viz_show_map: Display results on map                                                                                                                                                            
    - viz_show_chart: Display time series chart                                                                                                                                                       
    """                                                                                                                                                                                               
                                                                                                                                                                                                      
        def __init__(self, config: Optional[OpenEOAIConfig] = None):                                                                                                                                  
            self.config = config or OpenEOAIConfig()                                                                                                                                                  
            self.session_manager = SessionManager(self.config.sqlite_path)                                                                                                                            
            self.tools = create_openeo_tools(self.config)                                                                                                                                             
                                                                                                                                                                                                      
        def _build_options(self, user_id: str) -> ClaudeAgentOptions:                                                                                                                                 
            """Build Claude SDK options with custom tools."""                                                                                                                                         
            return ClaudeAgentOptions(                                                                                                                                                                
                model=self.config.model,                                                                                                                                                              
                system_prompt=self.SYSTEM_PROMPT,                                                                                                                                                     
                allowed_tools=list(self.tools.keys()),                                                                                                                                                
                can_use_tool=openeo_permission_callback,                                                                                                                                              
                custom_tools=self.tools,                                                                                                                                                              
                max_turns=self.config.max_turns,                                                                                                                                                      
            )                                                                                                                                                                                         
                                                                                                                                                                                                      
        async def chat(                                                                                                                                                                               
            self,                                                                                                                                                                                     
            prompt: str,                                                                                                                                                                              
            user_id: str,                                                                                                                                                                             
            session_id: Optional[str] = None                                                                                                                                                          
        ) -> AsyncIterator[dict]:                                                                                                                                                                     
            """                                                                                                                                                                                       
            Chat with the OpenEO AI Assistant.                                                                                                                                                        
                                                                                                                                                                                                      
            Args:                                                                                                                                                                                     
                prompt: User's message                                                                                                                                                                
                user_id: Authenticated user ID (from OIDC)                                                                                                                                            
                session_id: Optional session to resume                                                                                                                                                
                                                                                                                                                                                                      
            Yields:                                                                                                                                                                                   
                Response messages with text, tool results, or visualizations                                                                                                                          
            """                                                                                                                                                                                       
            options = self._build_options(user_id)                                                                                                                                                    
                                                                                                                                                                                                      
            # Resume session if provided                                                                                                                                                              
            if session_id:                                                                                                                                                                            
                options.resume = session_id                                                                                                                                                           
                                                                                                                                                                                                      
            async for message in query(prompt=prompt, options=options):                                                                                                                               
                # Track session                                                                                                                                                                       
                if hasattr(message, 'session_id'):                                                                                                                                                    
                    self.session_manager.update_session(                                                                                                                                              
                        session_id=message.session_id,                                                                                                                                                
                        user_id=user_id                                                                                                                                                               
                    )                                                                                                                                                                                 
                                                                                                                                                                                                      
                # Process and yield message                                                                                                                                                           
                yield self._process_message(message)                                                                                                                                                  
                                                                                                                                                                                                      
        def _process_message(self, message) -> dict:                                                                                                                                                  
            """Process SDK message into structured response."""                                                                                                                                       
            if hasattr(message, 'text'):                                                                                                                                                              
                return {"type": "text", "content": message.text}                                                                                                                                      
            elif hasattr(message, 'tool_result'):                                                                                                                                                     
                return {                                                                                                                                                                              
                    "type": "tool_result",                                                                                                                                                            
                    "tool": message.tool_name,                                                                                                                                                        
                    "result": message.tool_result                                                                                                                                                     
                }                                                                                                                                                                                     
            elif hasattr(message, 'visualization'):                                                                                                                                                   
                return {                                                                                                                                                                              
                    "type": "visualization",                                                                                                                                                          
                    "component": message.visualization                                                                                                                                                
                }                                                                                                                                                                                     
            return {"type": "raw", "content": str(message)}                                                                                                                                           
                                                                                                                                                                                                      
    ---                                                                                                                                                                                               
    2. Custom Tool Definitions                                                                                                                                                                        
                                                                                                                                                                                                      
    # openeo_ai/sdk/tools.py                                                                                                                                                                          
    """                                                                                                                                                                                               
    Custom tools for OpenEO AI Assistant.                                                                                                                                                             
    Registered directly with Claude SDK.                                                                                                                                                              
    """                                                                                                                                                                                               
                                                                                                                                                                                                      
    from typing import Any, Dict                                                                                                                                                                      
    from claude_agent_sdk import tool                                                                                                                                                                 
    import json                                                                                                                                                                                       
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    def create_openeo_tools(config) -> Dict[str, callable]:                                                                                                                                           
        """Create all OpenEO tools for Claude SDK."""                                                                                                                                                 
                                                                                                                                                                                                      
        from ..tools.openeo_tools import OpenEOTools                                                                                                                                                  
        from ..tools.job_tools import JobTools                                                                                                                                                        
        from ..tools.geoai_tools import GeoAITools                                                                                                                                                    
        from ..tools.viz_tools import VizTools                                                                                                                                                        
        from ..tools.validation_tools import ValidationTools                                                                                                                                          
                                                                                                                                                                                                      
        openeo = OpenEOTools(config.openeo_url)                                                                                                                                                       
        jobs = JobTools(config.openeo_url)                                                                                                                                                            
        geoai = GeoAITools(config.geoai_models_path)                                                                                                                                                  
        viz = VizTools()                                                                                                                                                                              
        validation = ValidationTools()                                                                                                                                                                
                                                                                                                                                                                                      
        tools = {}                                                                                                                                                                                    
                                                                                                                                                                                                      
        # === OpenEO Data Tools ===                                                                                                                                                                   
                                                                                                                                                                                                      
        @tool("openeo_list_collections",                                                                                                                                                              
              "List available Earth Observation data collections",                                                                                                                                    
              {})                                                                                                                                                                                     
        async def list_collections(args):                                                                                                                                                             
            """List all available collections."""                                                                                                                                                     
            collections = await openeo.list_collections()                                                                                                                                             
            return {"content": [{"type": "text", "text": json.dumps(collections)}]}                                                                                                                   
        tools["openeo_list_collections"] = list_collections                                                                                                                                           
                                                                                                                                                                                                      
        @tool("openeo_get_collection_info",                                                                                                                                                           
              "Get detailed information about a collection including bands",                                                                                                                          
              {"collection_id": str})                                                                                                                                                                 
        async def get_collection_info(args):                                                                                                                                                          
            """Get collection details."""                                                                                                                                                             
            info = await openeo.get_collection_info(args["collection_id"])                                                                                                                            
            return {"content": [{"type": "text", "text": json.dumps(info)}]}                                                                                                                          
        tools["openeo_get_collection_info"] = get_collection_info                                                                                                                                     
                                                                                                                                                                                                      
        # === Process Graph Tools ===                                                                                                                                                                 
                                                                                                                                                                                                      
        @tool("openeo_validate_graph",                                                                                                                                                                
              "Validate a process graph before execution. Returns errors, warnings, and suggestions.",                                                                                                
              {"process_graph": dict})                                                                                                                                                                
        async def validate_graph(args):                                                                                                                                                               
            """Validate process graph."""                                                                                                                                                             
            result = await validation.validate(args["process_graph"])                                                                                                                                 
            return {"content": [{"type": "text", "text": json.dumps(result)}]}                                                                                                                        
        tools["openeo_validate_graph"] = validate_graph                                                                                                                                               
                                                                                                                                                                                                      
        @tool("openeo_generate_graph",                                                                                                                                                                
              "Generate a process graph from a description. Use for complex graphs.",                                                                                                                 
              {                                                                                                                                                                                       
                  "description": str,                                                                                                                                                                 
                  "collection": str,                                                                                                                                                                  
                  "spatial_extent": dict,                                                                                                                                                             
                  "temporal_extent": list,                                                                                                                                                            
                  "output_format": str                                                                                                                                                                
              })                                                                                                                                                                                      
        async def generate_graph(args):                                                                                                                                                               
            """Generate process graph from description."""                                                                                                                                            
            graph = await openeo.generate_process_graph(                                                                                                                                              
                description=args["description"],                                                                                                                                                      
                collection=args["collection"],                                                                                                                                                        
                spatial_extent=args["spatial_extent"],                                                                                                                                                
                temporal_extent=args["temporal_extent"],                                                                                                                                              
                output_format=args.get("output_format", "GTiff")                                                                                                                                      
            )                                                                                                                                                                                         
            return {"content": [{"type": "text", "text": json.dumps(graph)}]}                                                                                                                         
        tools["openeo_generate_graph"] = generate_graph                                                                                                                                               
                                                                                                                                                                                                      
        @tool("openeo_save_graph",                                                                                                                                                                    
              "Save a process graph to the library for reuse",                                                                                                                                        
              {"name": str, "description": str, "process_graph": dict, "tags": list})                                                                                                                 
        async def save_graph(args):                                                                                                                                                                   
            """Save process graph to SQLite."""                                                                                                                                                       
            from ..storage.repositories import ProcessGraphRepository                                                                                                                                 
            repo = ProcessGraphRepository()                                                                                                                                                           
            graph_id = await repo.save(                                                                                                                                                               
                name=args["name"],                                                                                                                                                                    
                description=args["description"],                                                                                                                                                      
                process_graph=args["process_graph"],                                                                                                                                                  
                tags=args.get("tags", [])                                                                                                                                                             
            )                                                                                                                                                                                         
            return {"content": [{"type": "text", "text": f"Saved as: {graph_id}"}]}                                                                                                                   
        tools["openeo_save_graph"] = save_graph                                                                                                                                                       
                                                                                                                                                                                                      
        @tool("openeo_list_saved_graphs",                                                                                                                                                             
              "List saved process graphs from the library",                                                                                                                                           
              {"tags": list, "search": str})                                                                                                                                                          
        async def list_saved_graphs(args):                                                                                                                                                            
            """List saved process graphs."""                                                                                                                                                          
            from ..storage.repositories import ProcessGraphRepository                                                                                                                                 
            repo = ProcessGraphRepository()                                                                                                                                                           
            graphs = await repo.list(                                                                                                                                                                 
                tags=args.get("tags"),                                                                                                                                                                
                search=args.get("search")                                                                                                                                                             
            )                                                                                                                                                                                         
            return {"content": [{"type": "text", "text": json.dumps(graphs)}]}                                                                                                                        
        tools["openeo_list_saved_graphs"] = list_saved_graphs                                                                                                                                         
                                                                                                                                                                                                      
        # === Job Management Tools ===                                                                                                                                                                
                                                                                                                                                                                                      
        @tool("openeo_create_job",                                                                                                                                                                    
              "Create a batch processing job",                                                                                                                                                        
              {"title": str, "description": str, "process_graph": dict})                                                                                                                              
        async def create_job(args):                                                                                                                                                                   
            """Create batch job."""                                                                                                                                                                   
            job = await jobs.create(                                                                                                                                                                  
                title=args["title"],                                                                                                                                                                  
                description=args.get("description", ""),                                                                                                                                              
                process_graph=args["process_graph"]                                                                                                                                                   
            )                                                                                                                                                                                         
            return {"content": [{"type": "text", "text": json.dumps(job)}]}                                                                                                                           
        tools["openeo_create_job"] = create_job                                                                                                                                                       
                                                                                                                                                                                                      
        @tool("openeo_start_job",                                                                                                                                                                     
              "Start a queued batch job",                                                                                                                                                             
              {"job_id": str})                                                                                                                                                                        
        async def start_job(args):                                                                                                                                                                    
            """Start batch job."""                                                                                                                                                                    
            result = await jobs.start(args["job_id"])                                                                                                                                                 
            return {"content": [{"type": "text", "text": json.dumps(result)}]}                                                                                                                        
        tools["openeo_start_job"] = start_job                                                                                                                                                         
                                                                                                                                                                                                      
        @tool("openeo_get_job_status",                                                                                                                                                                
              "Get the status of a batch job",                                                                                                                                                        
              {"job_id": str})                                                                                                                                                                        
        async def get_job_status(args):                                                                                                                                                               
            """Get job status."""                                                                                                                                                                     
            status = await jobs.get_status(args["job_id"])                                                                                                                                            
            return {"content": [{"type": "text", "text": json.dumps(status)}]}                                                                                                                        
        tools["openeo_get_job_status"] = get_job_status                                                                                                                                               
                                                                                                                                                                                                      
        @tool("openeo_get_results",                                                                                                                                                                   
              "Download results from a completed job",                                                                                                                                                
              {"job_id": str, "output_path": str})                                                                                                                                                    
        async def get_results(args):                                                                                                                                                                  
            """Get job results."""                                                                                                                                                                    
            result = await jobs.get_results(                                                                                                                                                          
                args["job_id"],                                                                                                                                                                       
                args.get("output_path", "/tmp")                                                                                                                                                       
            )                                                                                                                                                                                         
            return {"content": [{"type": "text", "text": json.dumps(result)}]}                                                                                                                        
        tools["openeo_get_results"] = get_results                                                                                                                                                     
                                                                                                                                                                                                      
        # === GeoAI Tools ===                                                                                                                                                                         
                                                                                                                                                                                                      
        @tool("geoai_segment",                                                                                                                                                                        
              "Run semantic segmentation on satellite imagery",                                                                                                                                       
              {"input_path": str, "model": str, "output_path": str})                                                                                                                                  
        async def geoai_segment(args):                                                                                                                                                                
            """Run segmentation model."""                                                                                                                                                             
            result = await geoai.segment(                                                                                                                                                             
                input_path=args["input_path"],                                                                                                                                                        
                model=args.get("model", "default"),                                                                                                                                                   
                output_path=args.get("output_path")                                                                                                                                                   
            )                                                                                                                                                                                         
            return {"content": [{"type": "text", "text": json.dumps(result)}]}                                                                                                                        
        tools["geoai_segment"] = geoai_segment                                                                                                                                                        
                                                                                                                                                                                                      
        @tool("geoai_detect_change",                                                                                                                                                                  
              "Detect changes between two images",                                                                                                                                                    
              {"before_path": str, "after_path": str, "model": str})                                                                                                                                  
        async def geoai_detect_change(args):                                                                                                                                                          
            """Run change detection."""                                                                                                                                                               
            result = await geoai.detect_change(                                                                                                                                                       
                before_path=args["before_path"],                                                                                                                                                      
                after_path=args["after_path"],                                                                                                                                                        
                model=args.get("model", "default")                                                                                                                                                    
            )                                                                                                                                                                                         
            return {"content": [{"type": "text", "text": json.dumps(result)}]}                                                                                                                        
        tools["geoai_detect_change"] = geoai_detect_change                                                                                                                                            
                                                                                                                                                                                                      
        @tool("geoai_estimate_canopy_height",                                                                                                                                                         
              "Estimate canopy height from RGB imagery using HighResCanopyHeight model",                                                                                                              
              {"input_path": str})                                                                                                                                                                    
        async def geoai_canopy_height(args):                                                                                                                                                          
            """Estimate canopy height."""                                                                                                                                                             
            result = await geoai.estimate_canopy_height(args["input_path"])                                                                                                                           
            return {"content": [{"type": "text", "text": json.dumps(result)}]}                                                                                                                        
        tools["geoai_estimate_canopy_height"] = geoai_canopy_height                                                                                                                                   
                                                                                                                                                                                                      
        # === Visualization Tools (MCP-UI) ===                                                                                                                                                        
                                                                                                                                                                                                      
        @tool("viz_show_map",                                                                                                                                                                         
              "Display a GeoTIFF on an interactive map",                                                                                                                                              
              {"geotiff_path": str, "title": str, "colormap": str, "vmin": float, "vmax": float})                                                                                                     
        async def viz_show_map(args):                                                                                                                                                                 
            """Show interactive map."""                                                                                                                                                               
            component = await viz.create_map(                                                                                                                                                         
                geotiff_path=args["geotiff_path"],                                                                                                                                                    
                title=args.get("title", "Result"),                                                                                                                                                    
                colormap=args.get("colormap", "viridis"),                                                                                                                                             
                vmin=args.get("vmin"),                                                                                                                                                                
                vmax=args.get("vmax")                                                                                                                                                                 
            )                                                                                                                                                                                         
            return {"content": [{"type": "visualization", "component": component}]}                                                                                                                   
        tools["viz_show_map"] = viz_show_map                                                                                                                                                          
                                                                                                                                                                                                      
        @tool("viz_show_ndvi_map",                                                                                                                                                                    
              "Display NDVI results with vegetation color scale",                                                                                                                                     
              {"geotiff_path": str, "title": str})                                                                                                                                                    
        async def viz_show_ndvi_map(args):                                                                                                                                                            
            """Show NDVI map with RdYlGn colormap."""                                                                                                                                                 
            component = await viz.create_map(                                                                                                                                                         
                geotiff_path=args["geotiff_path"],                                                                                                                                                    
                title=args.get("title", "NDVI"),                                                                                                                                                      
                colormap="RdYlGn",                                                                                                                                                                    
                vmin=-1, vmax=1                                                                                                                                                                       
            )                                                                                                                                                                                         
            return {"content": [{"type": "visualization", "component": component}]}                                                                                                                   
        tools["viz_show_ndvi_map"] = viz_show_ndvi_map                                                                                                                                                
                                                                                                                                                                                                      
        @tool("viz_show_time_series",                                                                                                                                                                 
              "Display a time series chart",                                                                                                                                                          
              {"values": list, "dates": list, "title": str, "ylabel": str})                                                                                                                           
        async def viz_show_time_series(args):                                                                                                                                                         
            """Show time series chart."""                                                                                                                                                             
            component = await viz.create_time_series(                                                                                                                                                 
                values=args["values"],                                                                                                                                                                
                dates=args["dates"],                                                                                                                                                                  
                title=args.get("title", "Time Series"),                                                                                                                                               
                ylabel=args.get("ylabel", "Value")                                                                                                                                                    
            )                                                                                                                                                                                         
            return {"content": [{"type": "visualization", "component": component}]}                                                                                                                   
        tools["viz_show_time_series"] = viz_show_time_series                                                                                                                                          
                                                                                                                                                                                                      
        @tool("viz_compare_images",                                                                                                                                                                   
              "Create a before/after comparison slider",                                                                                                                                              
              {"before_path": str, "after_path": str, "title": str})                                                                                                                                  
        async def viz_compare_images(args):                                                                                                                                                           
            """Create comparison slider."""                                                                                                                                                           
            component = await viz.create_comparison(                                                                                                                                                  
                before_path=args["before_path"],                                                                                                                                                      
                after_path=args["after_path"],                                                                                                                                                        
                title=args.get("title", "Comparison")                                                                                                                                                 
            )                                                                                                                                                                                         
            return {"content": [{"type": "visualization", "component": component}]}                                                                                                                   
        tools["viz_compare_images"] = viz_compare_images                                                                                                                                              
                                                                                                                                                                                                      
        return tools                                                                                                                                                                                  
                                                                                                                                                                                                      
    ---                                                                                                                                                                                               
    3. SQLite Process Graph Storage                                                                                                                                                                   
                                                                                                                                                                                                      
    # openeo_ai/storage/models.py                                                                                                                                                                     
    """SQLAlchemy models for process graph storage."""                                                                                                                                                
                                                                                                                                                                                                      
    from sqlalchemy import Column, String, JSON, DateTime, ForeignKey, Table                                                                                                                          
    from sqlalchemy.orm import relationship                                                                                                                                                           
    from sqlalchemy.ext.declarative import declarative_base                                                                                                                                           
    from datetime import datetime                                                                                                                                                                     
    import uuid                                                                                                                                                                                       
                                                                                                                                                                                                      
    Base = declarative_base()                                                                                                                                                                         
                                                                                                                                                                                                      
    # Many-to-many for tags                                                                                                                                                                           
    graph_tags = Table(                                                                                                                                                                               
        'graph_tags', Base.metadata,                                                                                                                                                                  
        Column('graph_id', String, ForeignKey('process_graphs.id')),                                                                                                                                  
        Column('tag_id', String, ForeignKey('tags.id'))                                                                                                                                               
    )                                                                                                                                                                                                 
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    class ProcessGraph(Base):                                                                                                                                                                         
        """Stored process graph."""                                                                                                                                                                   
        __tablename__ = 'process_graphs'                                                                                                                                                              
                                                                                                                                                                                                      
        id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))                                                                                                                      
        name = Column(String, nullable=False)                                                                                                                                                         
        description = Column(String)                                                                                                                                                                  
        process_graph = Column(JSON, nullable=False)                                                                                                                                                  
        user_id = Column(String, nullable=False)                                                                                                                                                      
        created_at = Column(DateTime, default=datetime.utcnow)                                                                                                                                        
        updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)                                                                                                              
                                                                                                                                                                                                      
        # Relationships                                                                                                                                                                               
        tags = relationship("Tag", secondary=graph_tags, back_populates="graphs")                                                                                                                     
        executions = relationship("Execution", back_populates="graph")                                                                                                                                
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    class Tag(Base):                                                                                                                                                                                  
        """Tags for process graphs."""                                                                                                                                                                
        __tablename__ = 'tags'                                                                                                                                                                        
                                                                                                                                                                                                      
        id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))                                                                                                                      
        name = Column(String, unique=True, nullable=False)                                                                                                                                            
                                                                                                                                                                                                      
        graphs = relationship("ProcessGraph", secondary=graph_tags, back_populates="tags")                                                                                                            
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    class Execution(Base):                                                                                                                                                                            
        """Execution history."""                                                                                                                                                                      
        __tablename__ = 'executions'                                                                                                                                                                  
                                                                                                                                                                                                      
        id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))                                                                                                                      
        graph_id = Column(String, ForeignKey('process_graphs.id'))                                                                                                                                    
        job_id = Column(String)  # OpenEO job ID                                                                                                                                                      
        status = Column(String)                                                                                                                                                                       
        started_at = Column(DateTime)                                                                                                                                                                 
        finished_at = Column(DateTime)                                                                                                                                                                
        result_path = Column(String)                                                                                                                                                                  
        error_message = Column(String)                                                                                                                                                                
                                                                                                                                                                                                      
        graph = relationship("ProcessGraph", back_populates="executions")                                                                                                                             
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    class Session(Base):                                                                                                                                                                              
        """Chat sessions."""                                                                                                                                                                          
        __tablename__ = 'sessions'                                                                                                                                                                    
                                                                                                                                                                                                      
        id = Column(String, primary_key=True)                                                                                                                                                         
        user_id = Column(String, nullable=False)                                                                                                                                                      
        created_at = Column(DateTime, default=datetime.utcnow)                                                                                                                                        
        last_active = Column(DateTime, default=datetime.utcnow)                                                                                                                                       
        context = Column(JSON)  # Stored context for resumption                                                                                                                                       
                                                                                                                                                                                                      
    # openeo_ai/storage/repositories.py                                                                                                                                                               
    """Data access layer for SQLite storage."""                                                                                                                                                       
                                                                                                                                                                                                      
    from typing import List, Optional                                                                                                                                                                 
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine                                                                                                                              
    from sqlalchemy.orm import sessionmaker                                                                                                                                                           
    from sqlalchemy import select, or_                                                                                                                                                                
    import json                                                                                                                                                                                       
                                                                                                                                                                                                      
    from .models import Base, ProcessGraph, Tag, Execution, Session                                                                                                                                   
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    class Database:                                                                                                                                                                                   
        """Async SQLite database connection."""                                                                                                                                                       
                                                                                                                                                                                                      
        def __init__(self, db_path: str = "data/openeo_ai.db"):                                                                                                                                       
            self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")                                                                                                                       
            self.async_session = sessionmaker(                                                                                                                                                        
                self.engine, class_=AsyncSession, expire_on_commit=False                                                                                                                              
            )                                                                                                                                                                                         
                                                                                                                                                                                                      
        async def init(self):                                                                                                                                                                         
            """Create tables."""                                                                                                                                                                      
            async with self.engine.begin() as conn:                                                                                                                                                   
                await conn.run_sync(Base.metadata.create_all)                                                                                                                                         
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    class ProcessGraphRepository:                                                                                                                                                                     
        """Repository for process graph storage."""                                                                                                                                                   
                                                                                                                                                                                                      
        def __init__(self, db: Database):                                                                                                                                                             
            self.db = db                                                                                                                                                                              
                                                                                                                                                                                                      
        async def save(                                                                                                                                                                               
            self,                                                                                                                                                                                     
            name: str,                                                                                                                                                                                
            description: str,                                                                                                                                                                         
            process_graph: dict,                                                                                                                                                                      
            user_id: str,                                                                                                                                                                             
            tags: List[str] = None                                                                                                                                                                    
        ) -> str:                                                                                                                                                                                     
            """Save a process graph."""                                                                                                                                                               
            async with self.db.async_session() as session:                                                                                                                                            
                # Create or get tags                                                                                                                                                                  
                tag_objects = []                                                                                                                                                                      
                for tag_name in (tags or []):                                                                                                                                                         
                    result = await session.execute(                                                                                                                                                   
                        select(Tag).where(Tag.name == tag_name)                                                                                                                                       
                    )                                                                                                                                                                                 
                    tag = result.scalar_one_or_none()                                                                                                                                                 
                    if not tag:                                                                                                                                                                       
                        tag = Tag(name=tag_name)                                                                                                                                                      
                        session.add(tag)                                                                                                                                                              
                    tag_objects.append(tag)                                                                                                                                                           
                                                                                                                                                                                                      
                # Create process graph                                                                                                                                                                
                graph = ProcessGraph(                                                                                                                                                                 
                    name=name,                                                                                                                                                                        
                    description=description,                                                                                                                                                          
                    process_graph=process_graph,                                                                                                                                                      
                    user_id=user_id,                                                                                                                                                                  
                    tags=tag_objects                                                                                                                                                                  
                )                                                                                                                                                                                     
                session.add(graph)                                                                                                                                                                    
                await session.commit()                                                                                                                                                                
                return graph.id                                                                                                                                                                       
                                                                                                                                                                                                      
        async def get(self, graph_id: str) -> Optional[dict]:                                                                                                                                         
            """Get a process graph by ID."""                                                                                                                                                          
            async with self.db.async_session() as session:                                                                                                                                            
                result = await session.execute(                                                                                                                                                       
                    select(ProcessGraph).where(ProcessGraph.id == graph_id)                                                                                                                           
                )                                                                                                                                                                                     
                graph = result.scalar_one_or_none()                                                                                                                                                   
                if graph:                                                                                                                                                                             
                    return {                                                                                                                                                                          
                        "id": graph.id,                                                                                                                                                               
                        "name": graph.name,                                                                                                                                                           
                        "description": graph.description,                                                                                                                                             
                        "process_graph": graph.process_graph,                                                                                                                                         
                        "tags": [t.name for t in graph.tags],                                                                                                                                         
                        "created_at": graph.created_at.isoformat()                                                                                                                                    
                    }                                                                                                                                                                                 
                return None                                                                                                                                                                           
                                                                                                                                                                                                      
        async def list(                                                                                                                                                                               
            self,                                                                                                                                                                                     
            user_id: str,                                                                                                                                                                             
            tags: List[str] = None,                                                                                                                                                                   
            search: str = None,                                                                                                                                                                       
            limit: int = 50                                                                                                                                                                           
        ) -> List[dict]:                                                                                                                                                                              
            """List process graphs with optional filtering."""                                                                                                                                        
            async with self.db.async_session() as session:                                                                                                                                            
                query = select(ProcessGraph).where(                                                                                                                                                   
                    ProcessGraph.user_id == user_id                                                                                                                                                   
                )                                                                                                                                                                                     
                                                                                                                                                                                                      
                if tags:                                                                                                                                                                              
                    query = query.join(ProcessGraph.tags).where(                                                                                                                                      
                        Tag.name.in_(tags)                                                                                                                                                            
                    )                                                                                                                                                                                 
                                                                                                                                                                                                      
                if search:                                                                                                                                                                            
                    query = query.where(                                                                                                                                                              
                        or_(                                                                                                                                                                          
                            ProcessGraph.name.contains(search),                                                                                                                                       
                            ProcessGraph.description.contains(search)                                                                                                                                 
                        )                                                                                                                                                                             
                    )                                                                                                                                                                                 
                                                                                                                                                                                                      
                query = query.limit(limit).order_by(ProcessGraph.updated_at.desc())                                                                                                                   
                                                                                                                                                                                                      
                result = await session.execute(query)                                                                                                                                                 
                graphs = result.scalars().all()                                                                                                                                                       
                                                                                                                                                                                                      
                return [                                                                                                                                                                              
                    {                                                                                                                                                                                 
                        "id": g.id,                                                                                                                                                                   
                        "name": g.name,                                                                                                                                                               
                        "description": g.description,                                                                                                                                                 
                        "tags": [t.name for t in g.tags],                                                                                                                                             
                        "updated_at": g.updated_at.isoformat()                                                                                                                                        
                    }                                                                                                                                                                                 
                    for g in graphs                                                                                                                                                                   
                ]                                                                                                                                                                                     
                                                                                                                                                                                                      
    ---                                                                                                                                                                                               
    4. Process Graph Validation                                                                                                                                                                       
                                                                                                                                                                                                      
    # openeo_ai/tools/validation_tools.py                                                                                                                                                             
    """Process graph validation with educational feedback."""                                                                                                                                         
                                                                                                                                                                                                      
    from typing import List, Dict, Any                                                                                                                                                                
    from dataclasses import dataclass                                                                                                                                                                 
    import json                                                                                                                                                                                       
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    @dataclass                                                                                                                                                                                        
    class ValidationResult:                                                                                                                                                                           
        """Result of process graph validation."""                                                                                                                                                     
        valid: bool                                                                                                                                                                                   
        errors: List[str]                                                                                                                                                                             
        warnings: List[str]                                                                                                                                                                           
        suggestions: List[str]                                                                                                                                                                        
        resource_estimate: Dict[str, Any]                                                                                                                                                             
                                                                                                                                                                                                      
        def to_dict(self) -> dict:                                                                                                                                                                    
            return {                                                                                                                                                                                  
                "valid": self.valid,                                                                                                                                                                  
                "errors": self.errors,                                                                                                                                                                
                "warnings": self.warnings,                                                                                                                                                            
                "suggestions": self.suggestions,                                                                                                                                                      
                "resource_estimate": self.resource_estimate                                                                                                                                           
            }                                                                                                                                                                                         
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    class ValidationTools:                                                                                                                                                                            
        """Validate process graphs before execution."""                                                                                                                                               
                                                                                                                                                                                                      
        # Known processes with their required arguments                                                                                                                                               
        PROCESS_SPECS = {                                                                                                                                                                             
            "load_collection": {                                                                                                                                                                      
                "required": ["id"],                                                                                                                                                                   
                "optional": ["spatial_extent", "temporal_extent", "bands", "properties"]                                                                                                              
            },                                                                                                                                                                                        
            "ndvi": {                                                                                                                                                                                 
                "required": ["data"],                                                                                                                                                                 
                "optional": ["nir", "red", "target_band"]                                                                                                                                             
            },                                                                                                                                                                                        
            "reduce_dimension": {                                                                                                                                                                     
                "required": ["data", "dimension", "reducer"],                                                                                                                                         
                "optional": ["context"]                                                                                                                                                               
            },                                                                                                                                                                                        
            "save_result": {                                                                                                                                                                          
                "required": ["data", "format"],                                                                                                                                                       
                "optional": ["options"]                                                                                                                                                               
            },                                                                                                                                                                                        
            # ... more processes                                                                                                                                                                      
        }                                                                                                                                                                                             
                                                                                                                                                                                                      
        # Band mappings for validation                                                                                                                                                                
        COLLECTION_BANDS = {                                                                                                                                                                          
            "sentinel-2-l2a": ["blue", "green", "red", "nir", "nir08", "swir16", "swir22", "scl"],                                                                                                    
            "landsat-c2-l2": ["blue", "green", "red", "nir", "swir16", "swir22"],                                                                                                                     
            "cop-dem-glo-30": ["data"],                                                                                                                                                               
        }                                                                                                                                                                                             
                                                                                                                                                                                                      
        async def validate(self, process_graph: dict) -> ValidationResult:                                                                                                                            
            """Run all validation checks on a process graph."""                                                                                                                                       
            errors = []                                                                                                                                                                               
            warnings = []                                                                                                                                                                             
            suggestions = []                                                                                                                                                                          
                                                                                                                                                                                                      
            # 1. Structural validation                                                                                                                                                                
            errors.extend(self._validate_structure(process_graph))                                                                                                                                    
                                                                                                                                                                                                      
            # 2. Process validation                                                                                                                                                                   
            errors.extend(self._validate_processes(process_graph))                                                                                                                                    
                                                                                                                                                                                                      
            # 3. Data flow validation                                                                                                                                                                 
            errors.extend(self._validate_data_flow(process_graph))                                                                                                                                    
                                                                                                                                                                                                      
            # 4. Band validation                                                                                                                                                                      
            errors.extend(self._validate_bands(process_graph))                                                                                                                                        
                                                                                                                                                                                                      
            # 5. Extent validation                                                                                                                                                                    
            warnings.extend(self._validate_extents(process_graph))                                                                                                                                    
                                                                                                                                                                                                      
            # 6. Generate suggestions                                                                                                                                                                 
            suggestions.extend(self._generate_suggestions(process_graph))                                                                                                                             
                                                                                                                                                                                                      
            # 7. Estimate resources                                                                                                                                                                   
            estimate = self._estimate_resources(process_graph)                                                                                                                                        
                                                                                                                                                                                                      
            return ValidationResult(                                                                                                                                                                  
                valid=len(errors) == 0,                                                                                                                                                               
                errors=errors,                                                                                                                                                                        
                warnings=warnings,                                                                                                                                                                    
                suggestions=suggestions,                                                                                                                                                              
                resource_estimate=estimate                                                                                                                                                            
            )                                                                                                                                                                                         
                                                                                                                                                                                                      
        def _validate_structure(self, pg: dict) -> List[str]:                                                                                                                                         
            """Validate basic structure."""                                                                                                                                                           
            errors = []                                                                                                                                                                               
                                                                                                                                                                                                      
            if not isinstance(pg, dict):                                                                                                                                                              
                errors.append("Process graph must be a dictionary")                                                                                                                                   
                return errors                                                                                                                                                                         
                                                                                                                                                                                                      
            if len(pg) == 0:                                                                                                                                                                          
                errors.append("Process graph is empty")                                                                                                                                               
                return errors                                                                                                                                                                         
                                                                                                                                                                                                      
            # Check for result node                                                                                                                                                                   
            has_result = any(                                                                                                                                                                         
                node.get("result", False)                                                                                                                                                             
                for node in pg.values()                                                                                                                                                               
                if isinstance(node, dict)                                                                                                                                                             
            )                                                                                                                                                                                         
            if not has_result:                                                                                                                                                                        
                errors.append("No result node found. Mark one node with 'result': true")                                                                                                              
                                                                                                                                                                                                      
            return errors                                                                                                                                                                             
                                                                                                                                                                                                      
        def _validate_processes(self, pg: dict) -> List[str]:                                                                                                                                         
            """Validate process IDs and arguments."""                                                                                                                                                 
            errors = []                                                                                                                                                                               
                                                                                                                                                                                                      
            for node_id, node in pg.items():                                                                                                                                                          
                if not isinstance(node, dict):                                                                                                                                                        
                    continue                                                                                                                                                                          
                                                                                                                                                                                                      
                process_id = node.get("process_id")                                                                                                                                                   
                if not process_id:                                                                                                                                                                    
                    errors.append(f"Node '{node_id}' missing process_id")                                                                                                                             
                    continue                                                                                                                                                                          
                                                                                                                                                                                                      
                # Check if process exists                                                                                                                                                             
                if process_id not in self.PROCESS_SPECS:                                                                                                                                              
                    # Not necessarily an error - could be a valid but unknown process                                                                                                                 
                    pass                                                                                                                                                                              
                else:                                                                                                                                                                                 
                    # Validate required arguments                                                                                                                                                     
                    spec = self.PROCESS_SPECS[process_id]                                                                                                                                             
                    args = node.get("arguments", {})                                                                                                                                                  
                                                                                                                                                                                                      
                    for req_arg in spec["required"]:                                                                                                                                                  
                        if req_arg not in args:                                                                                                                                                       
                            errors.append(                                                                                                                                                            
                                f"Node '{node_id}' ({process_id}): "                                                                                                                                  
                                f"missing required argument '{req_arg}'"                                                                                                                              
                            )                                                                                                                                                                         
                                                                                                                                                                                                      
            return errors                                                                                                                                                                             
                                                                                                                                                                                                      
        def _validate_data_flow(self, pg: dict) -> List[str]:                                                                                                                                         
            """Validate node references."""                                                                                                                                                           
            errors = []                                                                                                                                                                               
            node_ids = set(pg.keys())                                                                                                                                                                 
                                                                                                                                                                                                      
            for node_id, node in pg.items():                                                                                                                                                          
                if not isinstance(node, dict):                                                                                                                                                        
                    continue                                                                                                                                                                          
                                                                                                                                                                                                      
                args = node.get("arguments", {})                                                                                                                                                      
                self._check_references(args, node_ids, node_id, errors)                                                                                                                               
                                                                                                                                                                                                      
            return errors                                                                                                                                                                             
                                                                                                                                                                                                      
        def _check_references(                                                                                                                                                                        
            self,                                                                                                                                                                                     
            obj: Any,                                                                                                                                                                                 
            valid_nodes: set,                                                                                                                                                                         
            current_node: str,                                                                                                                                                                        
            errors: List[str]                                                                                                                                                                         
        ):                                                                                                                                                                                            
            """Recursively check from_node references."""                                                                                                                                             
            if isinstance(obj, dict):                                                                                                                                                                 
                if "from_node" in obj:                                                                                                                                                                
                    ref = obj["from_node"]                                                                                                                                                            
                    if ref not in valid_nodes:                                                                                                                                                        
                        errors.append(                                                                                                                                                                
                            f"Node '{current_node}' references unknown node '{ref}'"                                                                                                                  
                        )                                                                                                                                                                             
                for value in obj.values():                                                                                                                                                            
                    self._check_references(value, valid_nodes, current_node, errors)                                                                                                                  
            elif isinstance(obj, list):                                                                                                                                                               
                for item in obj:                                                                                                                                                                      
                    self._check_references(item, valid_nodes, current_node, errors)                                                                                                                   
                                                                                                                                                                                                      
        def _validate_bands(self, pg: dict) -> List[str]:                                                                                                                                             
            """Validate band names against collection capabilities."""                                                                                                                                
            errors = []                                                                                                                                                                               
                                                                                                                                                                                                      
            for node_id, node in pg.items():                                                                                                                                                          
                if not isinstance(node, dict):                                                                                                                                                        
                    continue                                                                                                                                                                          
                                                                                                                                                                                                      
                if node.get("process_id") == "load_collection":                                                                                                                                       
                    args = node.get("arguments", {})                                                                                                                                                  
                    collection_id = args.get("id", "")                                                                                                                                                
                    bands = args.get("bands", [])                                                                                                                                                     
                                                                                                                                                                                                      
                    if collection_id in self.COLLECTION_BANDS and bands:                                                                                                                              
                        available = set(self.COLLECTION_BANDS[collection_id])                                                                                                                         
                        requested = set(bands)                                                                                                                                                        
                        invalid = requested - available                                                                                                                                               
                                                                                                                                                                                                      
                        if invalid:                                                                                                                                                                   
                            errors.append(                                                                                                                                                            
                                f"Node '{node_id}': bands {invalid} not available "                                                                                                                   
                                f"in {collection_id}. Available: {available}"                                                                                                                         
                            )                                                                                                                                                                         
                                                                                                                                                                                                      
            return errors                                                                                                                                                                             
                                                                                                                                                                                                      
        def _validate_extents(self, pg: dict) -> List[str]:                                                                                                                                           
            """Check spatial/temporal extents for warnings."""                                                                                                                                        
            warnings = []                                                                                                                                                                             
                                                                                                                                                                                                      
            for node_id, node in pg.items():                                                                                                                                                          
                if not isinstance(node, dict):                                                                                                                                                        
                    continue                                                                                                                                                                          
                                                                                                                                                                                                      
                if node.get("process_id") == "load_collection":                                                                                                                                       
                    args = node.get("arguments", {})                                                                                                                                                  
                                                                                                                                                                                                      
                    # Check spatial extent                                                                                                                                                            
                    spatial = args.get("spatial_extent", {})                                                                                                                                          
                    if spatial:                                                                                                                                                                       
                        width = abs(spatial.get("east", 0) - spatial.get("west", 0))                                                                                                                  
                        height = abs(spatial.get("north", 0) - spatial.get("south", 0))                                                                                                               
                                                                                                                                                                                                      
                        if width > 1 or height > 1:                                                                                                                                                   
                            warnings.append(                                                                                                                                                          
                                f"Large spatial extent ({width:.2f}° x {height:.2f}°). "                                                                                                              
                                "Consider reducing for faster processing."                                                                                                                            
                            )                                                                                                                                                                         
                                                                                                                                                                                                      
                        if width > 5 or height > 5:                                                                                                                                                   
                            warnings.append(                                                                                                                                                          
                                f"Very large extent may timeout or fail. "                                                                                                                            
                                "Recommend < 1° x 1° for testing."                                                                                                                                    
                            )                                                                                                                                                                         
                                                                                                                                                                                                      
                    # Check temporal extent                                                                                                                                                           
                    temporal = args.get("temporal_extent", [])                                                                                                                                        
                    if len(temporal) >= 2 and temporal[0] and temporal[1]:                                                                                                                            
                        # Would parse and check duration here                                                                                                                                         
                        pass                                                                                                                                                                          
                                                                                                                                                                                                      
            return warnings                                                                                                                                                                           
                                                                                                                                                                                                      
        def _generate_suggestions(self, pg: dict) -> List[str]:                                                                                                                                       
            """Generate optimization suggestions."""                                                                                                                                                  
            suggestions = []                                                                                                                                                                          
                                                                                                                                                                                                      
            has_cloud_mask = any(                                                                                                                                                                     
                node.get("process_id") in ["mask", "mask_polygon"]                                                                                                                                    
                for node in pg.values() if isinstance(node, dict)                                                                                                                                     
            )                                                                                                                                                                                         
                                                                                                                                                                                                      
            has_sentinel = any(                                                                                                                                                                       
                "sentinel" in str(node.get("arguments", {}).get("id", "")).lower()                                                                                                                    
                for node in pg.values() if isinstance(node, dict)                                                                                                                                     
            )                                                                                                                                                                                         
                                                                                                                                                                                                      
            if has_sentinel and not has_cloud_mask:                                                                                                                                                   
                suggestions.append(                                                                                                                                                                   
                    "Consider adding cloud masking for Sentinel data. "                                                                                                                               
                    "Use the SCL band to filter cloudy pixels."                                                                                                                                       
                )                                                                                                                                                                                     
                                                                                                                                                                                                      
            # Check for reduce_dimension on time                                                                                                                                                      
            has_reduce_time = any(                                                                                                                                                                    
                node.get("process_id") == "reduce_dimension" and                                                                                                                                      
                node.get("arguments", {}).get("dimension") == "time"                                                                                                                                  
                for node in pg.values() if isinstance(node, dict)                                                                                                                                     
            )                                                                                                                                                                                         
                                                                                                                                                                                                      
            if not has_reduce_time:                                                                                                                                                                   
                suggestions.append(                                                                                                                                                                   
                    "Consider adding reduce_dimension over time if you need "                                                                                                                         
                    "a single composite image (e.g., mean, median)."                                                                                                                                  
                )                                                                                                                                                                                     
                                                                                                                                                                                                      
            return suggestions                                                                                                                                                                        
                                                                                                                                                                                                      
        def _estimate_resources(self, pg: dict) -> Dict[str, Any]:                                                                                                                                    
            """Estimate processing resources needed."""                                                                                                                                               
            # This would calculate based on extent, temporal range, bands, etc.                                                                                                                       
            return {                                                                                                                                                                                  
                "estimated_size_mb": "unknown",                                                                                                                                                       
                "estimated_time_seconds": "unknown",                                                                                                                                                  
                "complexity": "medium"                                                                                                                                                                
            }                                                                                                                                                                                         
                                                                                                                                                                                                      
    ---                                                                                                                                                                                               
    5. Local GeoAI Model Integration                                                                                                                                                                  
                                                                                                                                                                                                      
    # openeo_ai/geoai/inference.py                                                                                                                                                                    
    """Local GeoAI model inference engine."""                                                                                                                                                         
                                                                                                                                                                                                      
    import torch                                                                                                                                                                                      
    import numpy as np                                                                                                                                                                                
    from pathlib import Path                                                                                                                                                                          
    from typing import Optional, Dict, Any                                                                                                                                                            
    import rioxarray                                                                                                                                                                                  
    import xarray as xr                                                                                                                                                                               
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    class GeoAIInference:                                                                                                                                                                             
        """Run GeoAI models locally on geospatial data."""                                                                                                                                            
                                                                                                                                                                                                      
        def __init__(self, models_path: str = "models/"):                                                                                                                                             
            self.models_path = Path(models_path)                                                                                                                                                      
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")                                                                                                                
            self._loaded_models: Dict[str, Any] = {}                                                                                                                                                  
                                                                                                                                                                                                      
        def _load_model(self, model_name: str):                                                                                                                                                       
            """Load a model if not already loaded."""                                                                                                                                                 
            if model_name in self._loaded_models:                                                                                                                                                     
                return self._loaded_models[model_name]                                                                                                                                                
                                                                                                                                                                                                      
            model_path = self.models_path / model_name                                                                                                                                                
            if not model_path.exists():                                                                                                                                                               
                raise ValueError(f"Model not found: {model_name}")                                                                                                                                    
                                                                                                                                                                                                      
            # Load based on model type                                                                                                                                                                
            if "segmentation" in model_name:                                                                                                                                                          
                from .models.segmentation import load_segmentation_model                                                                                                                              
                model = load_segmentation_model(model_path)                                                                                                                                           
            elif "change" in model_name:                                                                                                                                                              
                from .models.change_detection import load_change_model                                                                                                                                
                model = load_change_model(model_path)                                                                                                                                                 
            elif "canopy" in model_name:                                                                                                                                                              
                from .models.canopy_height import load_canopy_model                                                                                                                                   
                model = load_canopy_model(model_path)                                                                                                                                                 
            else:                                                                                                                                                                                     
                raise ValueError(f"Unknown model type: {model_name}")                                                                                                                                 
                                                                                                                                                                                                      
            model = model.to(self.device)                                                                                                                                                             
            model.eval()                                                                                                                                                                              
            self._loaded_models[model_name] = model                                                                                                                                                   
            return model                                                                                                                                                                              
                                                                                                                                                                                                      
        async def segment(                                                                                                                                                                            
            self,                                                                                                                                                                                     
            input_path: str,                                                                                                                                                                          
            model: str = "segmentation_default",                                                                                                                                                      
            output_path: Optional[str] = None,                                                                                                                                                        
            tile_size: int = 512,                                                                                                                                                                     
            overlap: int = 64                                                                                                                                                                         
        ) -> Dict[str, Any]:                                                                                                                                                                          
            """                                                                                                                                                                                       
            Run semantic segmentation on a GeoTIFF.                                                                                                                                                   
                                                                                                                                                                                                      
            Uses tiling for large images with overlap handling.                                                                                                                                       
            """                                                                                                                                                                                       
            # Load image                                                                                                                                                                              
            data = rioxarray.open_rasterio(input_path)                                                                                                                                                
                                                                                                                                                                                                      
            # Load model                                                                                                                                                                              
            seg_model = self._load_model(model)                                                                                                                                                       
                                                                                                                                                                                                      
            # Process with tiling                                                                                                                                                                     
            result = self._process_tiled(                                                                                                                                                             
                data.values,                                                                                                                                                                          
                seg_model,                                                                                                                                                                            
                tile_size,                                                                                                                                                                            
                overlap                                                                                                                                                                               
            )                                                                                                                                                                                         
                                                                                                                                                                                                      
            # Save result                                                                                                                                                                             
            if output_path is None:                                                                                                                                                                   
                output_path = input_path.replace(".tif", "_segmented.tif")                                                                                                                            
                                                                                                                                                                                                      
            result_da = xr.DataArray(                                                                                                                                                                 
                result,                                                                                                                                                                               
                dims=data.dims,                                                                                                                                                                       
                coords=data.coords,                                                                                                                                                                   
                attrs=data.attrs                                                                                                                                                                      
            )                                                                                                                                                                                         
            result_da.rio.to_raster(output_path)                                                                                                                                                      
                                                                                                                                                                                                      
            # Calculate statistics                                                                                                                                                                    
            unique, counts = np.unique(result, return_counts=True)                                                                                                                                    
            class_stats = {str(u): int(c) for u, c in zip(unique, counts)}                                                                                                                            
                                                                                                                                                                                                      
            return {                                                                                                                                                                                  
                "output_path": output_path,                                                                                                                                                           
                "classes_found": len(unique),                                                                                                                                                         
                "class_statistics": class_stats,                                                                                                                                                      
                "shape": list(result.shape)                                                                                                                                                           
            }                                                                                                                                                                                         
                                                                                                                                                                                                      
        async def detect_change(                                                                                                                                                                      
            self,                                                                                                                                                                                     
            before_path: str,                                                                                                                                                                         
            after_path: str,                                                                                                                                                                          
            model: str = "change_default",                                                                                                                                                            
            output_path: Optional[str] = None                                                                                                                                                         
        ) -> Dict[str, Any]:                                                                                                                                                                          
            """                                                                                                                                                                                       
            Detect changes between two images.                                                                                                                                                        
            """                                                                                                                                                                                       
            # Load images                                                                                                                                                                             
            before = rioxarray.open_rasterio(before_path)                                                                                                                                             
            after = rioxarray.open_rasterio(after_path)                                                                                                                                               
                                                                                                                                                                                                      
            # Ensure same shape                                                                                                                                                                       
            if before.shape != after.shape:                                                                                                                                                           
                raise ValueError("Images must have same dimensions")                                                                                                                                  
                                                                                                                                                                                                      
            # Stack for model input                                                                                                                                                                   
            stacked = np.concatenate([before.values, after.values], axis=0)                                                                                                                           
                                                                                                                                                                                                      
            # Load and run model                                                                                                                                                                      
            change_model = self._load_model(model)                                                                                                                                                    
                                                                                                                                                                                                      
            with torch.no_grad():                                                                                                                                                                     
                tensor = torch.from_numpy(stacked).unsqueeze(0).float().to(self.device)                                                                                                               
                prediction = change_model(tensor)                                                                                                                                                     
                result = prediction.squeeze().cpu().numpy()                                                                                                                                           
                                                                                                                                                                                                      
            # Threshold to binary                                                                                                                                                                     
            binary_change = (result > 0.5).astype(np.uint8)                                                                                                                                           
                                                                                                                                                                                                      
            # Save result                                                                                                                                                                             
            if output_path is None:                                                                                                                                                                   
                output_path = before_path.replace(".tif", "_change.tif")                                                                                                                              
                                                                                                                                                                                                      
            result_da = xr.DataArray(                                                                                                                                                                 
                binary_change[np.newaxis, ...],                                                                                                                                                       
                dims=before.dims,                                                                                                                                                                     
                coords=before.coords                                                                                                                                                                  
            )                                                                                                                                                                                         
            result_da.rio.to_raster(output_path)                                                                                                                                                      
                                                                                                                                                                                                      
            # Calculate change statistics                                                                                                                                                             
            changed_pixels = int(np.sum(binary_change))                                                                                                                                               
            total_pixels = int(binary_change.size)                                                                                                                                                    
            change_percent = (changed_pixels / total_pixels) * 100                                                                                                                                    
                                                                                                                                                                                                      
            return {                                                                                                                                                                                  
                "output_path": output_path,                                                                                                                                                           
                "changed_pixels": changed_pixels,                                                                                                                                                     
                "total_pixels": total_pixels,                                                                                                                                                         
                "change_percent": round(change_percent, 2)                                                                                                                                            
            }                                                                                                                                                                                         
                                                                                                                                                                                                      
        async def estimate_canopy_height(                                                                                                                                                             
            self,                                                                                                                                                                                     
            input_path: str,                                                                                                                                                                          
            output_path: Optional[str] = None                                                                                                                                                         
        ) -> Dict[str, Any]:                                                                                                                                                                          
            """                                                                                                                                                                                       
            Estimate canopy height from RGB imagery.                                                                                                                                                  
            Uses Meta's HighResCanopyHeight model (DINOv2 + DPT).                                                                                                                                     
            """                                                                                                                                                                                       
            # Load image                                                                                                                                                                              
            data = rioxarray.open_rasterio(input_path)                                                                                                                                                
                                                                                                                                                                                                      
            # Load model                                                                                                                                                                              
            canopy_model = self._load_model("canopy_height")                                                                                                                                          
                                                                                                                                                                                                      
            # Process                                                                                                                                                                                 
            with torch.no_grad():                                                                                                                                                                     
                tensor = torch.from_numpy(data.values).unsqueeze(0).float().to(self.device)                                                                                                           
                height_map = canopy_model(tensor)                                                                                                                                                     
                result = height_map.squeeze().cpu().numpy()                                                                                                                                           
                                                                                                                                                                                                      
            # Save result                                                                                                                                                                             
            if output_path is None:                                                                                                                                                                   
                output_path = input_path.replace(".tif", "_canopy_height.tif")                                                                                                                        
                                                                                                                                                                                                      
            result_da = xr.DataArray(                                                                                                                                                                 
                result[np.newaxis, ...],                                                                                                                                                              
                dims=data.dims[:1] + data.dims[1:],                                                                                                                                                   
                coords={k: v for k, v in data.coords.items() if k != 'band'}                                                                                                                          
            )                                                                                                                                                                                         
            result_da.rio.to_raster(output_path)                                                                                                                                                      
                                                                                                                                                                                                      
            # Statistics                                                                                                                                                                              
            valid = result[~np.isnan(result)]                                                                                                                                                         
                                                                                                                                                                                                      
            return {                                                                                                                                                                                  
                "output_path": output_path,                                                                                                                                                           
                "height_min_m": float(np.min(valid)),                                                                                                                                                 
                "height_max_m": float(np.max(valid)),                                                                                                                                                 
                "height_mean_m": float(np.mean(valid)),                                                                                                                                               
                "height_std_m": float(np.std(valid))                                                                                                                                                  
            }                                                                                                                                                                                         
                                                                                                                                                                                                      
        def _process_tiled(                                                                                                                                                                           
            self,                                                                                                                                                                                     
            data: np.ndarray,                                                                                                                                                                         
            model: torch.nn.Module,                                                                                                                                                                   
            tile_size: int,                                                                                                                                                                           
            overlap: int                                                                                                                                                                              
        ) -> np.ndarray:                                                                                                                                                                              
            """Process large images with tiling and overlap."""                                                                                                                                       
            _, height, width = data.shape                                                                                                                                                             
                                                                                                                                                                                                      
            # Calculate tiles                                                                                                                                                                         
            step = tile_size - overlap                                                                                                                                                                
            result = np.zeros((height, width), dtype=np.float32)                                                                                                                                      
            counts = np.zeros((height, width), dtype=np.float32)                                                                                                                                      
                                                                                                                                                                                                      
            for y in range(0, height, step):                                                                                                                                                          
                for x in range(0, width, step):                                                                                                                                                       
                    # Extract tile                                                                                                                                                                    
                    y_end = min(y + tile_size, height)                                                                                                                                                
                    x_end = min(x + tile_size, width)                                                                                                                                                 
                    tile = data[:, y:y_end, x:x_end]                                                                                                                                                  
                                                                                                                                                                                                      
                    # Pad if needed                                                                                                                                                                   
                    if tile.shape[1] < tile_size or tile.shape[2] < tile_size:                                                                                                                        
                        padded = np.zeros((data.shape[0], tile_size, tile_size))                                                                                                                      
                        padded[:, :tile.shape[1], :tile.shape[2]] = tile                                                                                                                              
                        tile = padded                                                                                                                                                                 
                                                                                                                                                                                                      
                    # Predict                                                                                                                                                                         
                    with torch.no_grad():                                                                                                                                                             
                        tensor = torch.from_numpy(tile).unsqueeze(0).float().to(self.device)                                                                                                          
                        pred = model(tensor)                                                                                                                                                          
                        pred_np = pred.squeeze().cpu().numpy()                                                                                                                                        
                                                                                                                                                                                                      
                    # Accumulate with overlap averaging                                                                                                                                               
                    result[y:y_end, x:x_end] += pred_np[:y_end-y, :x_end-x]                                                                                                                           
                    counts[y:y_end, x:x_end] += 1                                                                                                                                                     
                                                                                                                                                                                                      
            # Average overlapping regions                                                                                                                                                             
            result = result / np.maximum(counts, 1)                                                                                                                                                   
                                                                                                                                                                                                      
            return result                                                                                                                                                                             
                                                                                                                                                                                                      
    ---                                                                                                                                                                                               
    6. MCP-UI Visualization Components                                                                                                                                                                
                                                                                                                                                                                                      
    # openeo_ai/visualization/maps.py                                                                                                                                                                 
    """Interactive map components for MCP-UI."""                                                                                                                                                      
                                                                                                                                                                                                      
    from typing import Optional, List, Dict, Any                                                                                                                                                      
    import numpy as np                                                                                                                                                                                
    import rioxarray                                                                                                                                                                                  
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    class MapComponent:                                                                                                                                                                               
        """Interactive map visualization for MCP-UI."""                                                                                                                                               
                                                                                                                                                                                                      
        def __init__(self):                                                                                                                                                                           
            pass                                                                                                                                                                                      
                                                                                                                                                                                                      
        async def create_raster_map(                                                                                                                                                                  
            self,                                                                                                                                                                                     
            geotiff_path: str,                                                                                                                                                                        
            title: str = "Result",                                                                                                                                                                    
            colormap: str = "viridis",                                                                                                                                                                
            vmin: Optional[float] = None,                                                                                                                                                             
            vmax: Optional[float] = None,                                                                                                                                                             
            opacity: float = 0.8                                                                                                                                                                      
        ) -> Dict[str, Any]:                                                                                                                                                                          
            """                                                                                                                                                                                       
            Create an interactive map with a raster layer.                                                                                                                                            
                                                                                                                                                                                                      
            Returns MCP-UI component specification.                                                                                                                                                   
            """                                                                                                                                                                                       
            # Load raster to get bounds and stats                                                                                                                                                     
            data = rioxarray.open_rasterio(geotiff_path)                                                                                                                                              
            bounds = data.rio.bounds()                                                                                                                                                                
                                                                                                                                                                                                      
            # Calculate value range if not provided                                                                                                                                                   
            values = data.values.flatten()                                                                                                                                                            
            valid = values[~np.isnan(values)]                                                                                                                                                         
                                                                                                                                                                                                      
            if vmin is None:                                                                                                                                                                          
                vmin = float(np.percentile(valid, 2))                                                                                                                                                 
            if vmax is None:                                                                                                                                                                          
                vmax = float(np.percentile(valid, 98))                                                                                                                                                
                                                                                                                                                                                                      
            center = [                                                                                                                                                                                
                (bounds[1] + bounds[3]) / 2,  # lat                                                                                                                                                   
                (bounds[0] + bounds[2]) / 2   # lon                                                                                                                                                   
            ]                                                                                                                                                                                         
                                                                                                                                                                                                      
            return {                                                                                                                                                                                  
                "type": "map",                                                                                                                                                                        
                "spec": {                                                                                                                                                                             
                    "title": title,                                                                                                                                                                   
                    "center": center,                                                                                                                                                                 
                    "zoom": 12,                                                                                                                                                                       
                    "layers": [                                                                                                                                                                       
                        {                                                                                                                                                                             
                            "type": "raster",                                                                                                                                                         
                            "source": geotiff_path,                                                                                                                                                   
                            "colormap": colormap,                                                                                                                                                     
                            "vmin": vmin,                                                                                                                                                             
                            "vmax": vmax,                                                                                                                                                             
                            "opacity": opacity                                                                                                                                                        
                        }                                                                                                                                                                             
                    ],                                                                                                                                                                                
                    "controls": ["zoom", "layer_toggle", "colorbar", "fullscreen"],                                                                                                                   
                    "colorbar": {                                                                                                                                                                     
                        "title": title,                                                                                                                                                               
                        "colormap": colormap,                                                                                                                                                         
                        "min": vmin,                                                                                                                                                                  
                        "max": vmax                                                                                                                                                                   
                    }                                                                                                                                                                                 
                }                                                                                                                                                                                     
            }                                                                                                                                                                                         
                                                                                                                                                                                                      
        async def create_ndvi_map(                                                                                                                                                                    
            self,                                                                                                                                                                                     
            geotiff_path: str,                                                                                                                                                                        
            title: str = "NDVI"                                                                                                                                                                       
        ) -> Dict[str, Any]:                                                                                                                                                                          
            """Create NDVI-specific map with vegetation colormap."""                                                                                                                                  
            return await self.create_raster_map(                                                                                                                                                      
                geotiff_path=geotiff_path,                                                                                                                                                            
                title=title,                                                                                                                                                                          
                colormap="RdYlGn",                                                                                                                                                                    
                vmin=-1.0,                                                                                                                                                                            
                vmax=1.0                                                                                                                                                                              
            )                                                                                                                                                                                         
                                                                                                                                                                                                      
        async def create_comparison_slider(                                                                                                                                                           
            self,                                                                                                                                                                                     
            before_path: str,                                                                                                                                                                         
            after_path: str,                                                                                                                                                                          
            title: str = "Before / After"                                                                                                                                                             
        ) -> Dict[str, Any]:                                                                                                                                                                          
            """Create before/after comparison slider."""                                                                                                                                              
            return {                                                                                                                                                                                  
                "type": "comparison_slider",                                                                                                                                                          
                "spec": {                                                                                                                                                                             
                    "title": title,                                                                                                                                                                   
                    "before": {                                                                                                                                                                       
                        "source": before_path,                                                                                                                                                        
                        "label": "Before"                                                                                                                                                             
                    },                                                                                                                                                                                
                    "after": {                                                                                                                                                                        
                        "source": after_path,                                                                                                                                                         
                        "label": "After"                                                                                                                                                              
                    },                                                                                                                                                                                
                    "initial_position": 50                                                                                                                                                            
                }                                                                                                                                                                                     
            }                                                                                                                                                                                         
                                                                                                                                                                                                      
        async def create_multi_layer_map(                                                                                                                                                             
            self,                                                                                                                                                                                     
            layers: List[Dict[str, Any]],                                                                                                                                                             
            title: str = "Multi-Layer Map",                                                                                                                                                           
            center: Optional[List[float]] = None                                                                                                                                                      
        ) -> Dict[str, Any]:                                                                                                                                                                          
            """Create map with multiple layers."""                                                                                                                                                    
            return {                                                                                                                                                                                  
                "type": "map",                                                                                                                                                                        
                "spec": {                                                                                                                                                                             
                    "title": title,                                                                                                                                                                   
                    "center": center or [0, 0],                                                                                                                                                       
                    "zoom": 10,                                                                                                                                                                       
                    "layers": layers,                                                                                                                                                                 
                    "controls": ["zoom", "layer_toggle", "legend", "fullscreen"]                                                                                                                      
                }                                                                                                                                                                                     
            }                                                                                                                                                                                         
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    class ChartComponent:                                                                                                                                                                             
        """Chart components for MCP-UI."""                                                                                                                                                            
                                                                                                                                                                                                      
        async def create_time_series(                                                                                                                                                                 
            self,                                                                                                                                                                                     
            values: List[float],                                                                                                                                                                      
            dates: List[str],                                                                                                                                                                         
            title: str = "Time Series",                                                                                                                                                               
            ylabel: str = "Value",                                                                                                                                                                    
            series_name: str = "Data"                                                                                                                                                                 
        ) -> Dict[str, Any]:                                                                                                                                                                          
            """Create time series line chart."""                                                                                                                                                      
            return {                                                                                                                                                                                  
                "type": "chart",                                                                                                                                                                      
                "spec": {                                                                                                                                                                             
                    "chart_type": "line",                                                                                                                                                             
                    "title": title,                                                                                                                                                                   
                    "data": {                                                                                                                                                                         
                        "x": dates,                                                                                                                                                                   
                        "y": values,                                                                                                                                                                  
                        "name": series_name                                                                                                                                                           
                    },                                                                                                                                                                                
                    "xaxis": {"title": "Date", "type": "date"},                                                                                                                                       
                    "yaxis": {"title": ylabel}                                                                                                                                                        
                }                                                                                                                                                                                     
            }                                                                                                                                                                                         
                                                                                                                                                                                                      
        async def create_histogram(                                                                                                                                                                   
            self,                                                                                                                                                                                     
            values: List[float],                                                                                                                                                                      
            title: str = "Distribution",                                                                                                                                                              
            xlabel: str = "Value",                                                                                                                                                                    
            bins: int = 50                                                                                                                                                                            
        ) -> Dict[str, Any]:                                                                                                                                                                          
            """Create histogram."""                                                                                                                                                                   
            return {                                                                                                                                                                                  
                "type": "chart",                                                                                                                                                                      
                "spec": {                                                                                                                                                                             
                    "chart_type": "histogram",                                                                                                                                                        
                    "title": title,                                                                                                                                                                   
                    "data": {"values": values},                                                                                                                                                       
                    "bins": bins,                                                                                                                                                                     
                    "xaxis": {"title": xlabel},                                                                                                                                                       
                    "yaxis": {"title": "Count"}                                                                                                                                                       
                }                                                                                                                                                                                     
            }                                                                                                                                                                                         
                                                                                                                                                                                                      
        async def create_bar_chart(                                                                                                                                                                   
            self,                                                                                                                                                                                     
            categories: List[str],                                                                                                                                                                    
            values: List[float],                                                                                                                                                                      
            title: str = "Bar Chart",                                                                                                                                                                 
            ylabel: str = "Value"                                                                                                                                                                     
        ) -> Dict[str, Any]:                                                                                                                                                                          
            """Create bar chart."""                                                                                                                                                                   
            return {                                                                                                                                                                                  
                "type": "chart",                                                                                                                                                                      
                "spec": {                                                                                                                                                                             
                    "chart_type": "bar",                                                                                                                                                              
                    "title": title,                                                                                                                                                                   
                    "data": {                                                                                                                                                                         
                        "x": categories,                                                                                                                                                              
                        "y": values                                                                                                                                                                   
                    },                                                                                                                                                                                
                    "xaxis": {"title": "Category"},                                                                                                                                                   
                    "yaxis": {"title": ylabel}                                                                                                                                                        
                }                                                                                                                                                                                     
            }                                                                                                                                                                                         
                                                                                                                                                                                                      
    ---                                                                                                                                                                                               
    7. Main Entry Point                                                                                                                                                                               
                                                                                                                                                                                                      
    # openeo_ai/main.py                                                                                                                                                                               
    """OpenEO AI Assistant - Main entry point."""                                                                                                                                                     
                                                                                                                                                                                                      
    import asyncio                                                                                                                                                                                    
    from fastapi import FastAPI, Depends, WebSocket                                                                                                                                                   
    from fastapi.middleware.cors import CORSMiddleware                                                                                                                                                
                                                                                                                                                                                                      
    from .sdk.client import OpenEOAIClient, OpenEOAIConfig                                                                                                                                            
    from .auth.oidc import get_current_user, OIDCUser                                                                                                                                                 
    from .storage.repositories import Database                                                                                                                                                        
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    app = FastAPI(                                                                                                                                                                                    
        title="OpenEO AI Assistant",                                                                                                                                                                  
        description="AI-powered Earth Observation analysis with OpenEO",                                                                                                                              
        version="1.0.0"                                                                                                                                                                               
    )                                                                                                                                                                                                 
                                                                                                                                                                                                      
    app.add_middleware(                                                                                                                                                                               
        CORSMiddleware,                                                                                                                                                                               
        allow_origins=["*"],                                                                                                                                                                          
        allow_methods=["*"],                                                                                                                                                                          
        allow_headers=["*"],                                                                                                                                                                          
    )                                                                                                                                                                                                 
                                                                                                                                                                                                      
    # Initialize components                                                                                                                                                                           
    config = OpenEOAIConfig()                                                                                                                                                                         
    client = OpenEOAIClient(config)                                                                                                                                                                   
    db = Database(config.sqlite_path)                                                                                                                                                                 
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    @app.on_event("startup")                                                                                                                                                                          
    async def startup():                                                                                                                                                                              
        await db.init()                                                                                                                                                                               
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    @app.websocket("/ws/chat")                                                                                                                                                                        
    async def chat_websocket(                                                                                                                                                                         
        websocket: WebSocket,                                                                                                                                                                         
        user: OIDCUser = Depends(get_current_user)                                                                                                                                                    
    ):                                                                                                                                                                                                
        """                                                                                                                                                                                           
        WebSocket endpoint for real-time chat.                                                                                                                                                        
                                                                                                                                                                                                      
        Streams responses including text, tool results, and visualizations.                                                                                                                           
        """                                                                                                                                                                                           
        await websocket.accept()                                                                                                                                                                      
                                                                                                                                                                                                      
        session_id = None                                                                                                                                                                             
                                                                                                                                                                                                      
        try:                                                                                                                                                                                          
            while True:                                                                                                                                                                               
                # Receive message                                                                                                                                                                     
                data = await websocket.receive_json()                                                                                                                                                 
                prompt = data.get("message", "")                                                                                                                                                      
                session_id = data.get("session_id", session_id)                                                                                                                                       
                                                                                                                                                                                                      
                # Stream response                                                                                                                                                                     
                async for response in client.chat(                                                                                                                                                    
                    prompt=prompt,                                                                                                                                                                    
                    user_id=user.sub,                                                                                                                                                                 
                    session_id=session_id                                                                                                                                                             
                ):                                                                                                                                                                                    
                    await websocket.send_json(response)                                                                                                                                               
                                                                                                                                                                                                      
                    # Track session ID                                                                                                                                                                
                    if "session_id" in response:                                                                                                                                                      
                        session_id = response["session_id"]                                                                                                                                           
                                                                                                                                                                                                      
                # Send completion marker                                                                                                                                                              
                await websocket.send_json({"type": "complete", "session_id": session_id})                                                                                                             
                                                                                                                                                                                                      
        except Exception as e:                                                                                                                                                                        
            await websocket.send_json({"type": "error", "message": str(e)})                                                                                                                           
        finally:                                                                                                                                                                                      
            await websocket.close()                                                                                                                                                                   
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    @app.post("/api/chat")                                                                                                                                                                            
    async def chat_http(                                                                                                                                                                              
        request: dict,                                                                                                                                                                                
        user: OIDCUser = Depends(get_current_user)                                                                                                                                                    
    ):                                                                                                                                                                                                
        """                                                                                                                                                                                           
        HTTP endpoint for single-turn chat.                                                                                                                                                           
                                                                                                                                                                                                      
        Returns complete response (non-streaming).                                                                                                                                                    
        """                                                                                                                                                                                           
        prompt = request.get("message", "")                                                                                                                                                           
        session_id = request.get("session_id")                                                                                                                                                        
                                                                                                                                                                                                      
        responses = []                                                                                                                                                                                
        async for response in client.chat(                                                                                                                                                            
            prompt=prompt,                                                                                                                                                                            
            user_id=user.sub,                                                                                                                                                                         
            session_id=session_id                                                                                                                                                                     
        ):                                                                                                                                                                                            
            responses.append(response)                                                                                                                                                                
                                                                                                                                                                                                      
        return {"responses": responses}                                                                                                                                                               
                                                                                                                                                                                                      
                                                                                                                                                                                                      
    if __name__ == "__main__":                                                                                                                                                                        
        import uvicorn                                                                                                                                                                                
        uvicorn.run(app, host="0.0.0.0", port=8080)                                                                                                                                                   
                                                                                                                                                                                                      
    ---                                                                                                                                                                                               
    Example Conversation Flow                                                                                                                                                                         
                                                                                                                                                                                                      
    User: "Show me vegetation health for farmland near Des Moines, Iowa                                                                                                                               
           from June to August 2024"                                                                                                                                                                  
                                                                                                                                                                                                      
    Claude (via SDK): I'll help you analyze vegetation health using NDVI.                                                                                                                             
    Let me break this down:                                                                                                                                                                           
                                                                                                                                                                                                      
    1. **Data**: Sentinel-2 L2A (10m resolution, good for field-level analysis)                                                                                                                       
    2. **Location**: Des Moines, Iowa farmland                                                                                                                                                        
    3. **Time**: June-August 2024 (peak growing season)                                                                                                                                               
    4. **Analysis**: NDVI (Normalized Difference Vegetation Index)                                                                                                                                    
                                                                                                                                                                                                      
    First, let me validate the process graph...                                                                                                                                                       
                                                                                                                                                                                                      
    [Tool: openeo_validate_graph]                                                                                                                                                                     
    ✅ Validation passed:                                                                                                                                                                             
    - Spatial extent: 0.15° x 0.15° (~16km x 16km) ✓                                                                                                                                                  
    - Temporal: 3 months ✓                                                                                                                                                                            
    - Bands: red, nir ✓                                                                                                                                                                               
                                                                                                                                                                                                      
    ⚠️ Suggestion: Consider adding cloud masking for cleaner results.                                                                                                                                 
                                                                                                                                                                                                      
    Would you like me to:                                                                                                                                                                             
    1. Proceed with the current graph                                                                                                                                                                 
    2. Add cloud masking (recommended)                                                                                                                                                                
    3. Adjust the area or time range                                                                                                                                                                  
                                                                                                                                                                                                      
    User: "Add cloud masking and proceed"                                                                                                                                                             
                                                                                                                                                                                                      
    Claude: Adding cloud masking using the SCL (Scene Classification Layer) band.                                                                                                                     
                                                                                                                                                                                                      
    [Tool: openeo_create_job]                                                                                                                                                                         
    Created job: ndvi-iowa-2024-summer (ID: abc123)                                                                                                                                                   
                                                                                                                                                                                                      
    [Tool: openeo_start_job]                                                                                                                                                                          
    Job started. Processing...                                                                                                                                                                        
                                                                                                                                                                                                      
    [Waiting for completion - checking status every 10s]                                                                                                                                              
                                                                                                                                                                                                      
    Job completed in 45 seconds!                                                                                                                                                                      
                                                                                                                                                                                                      
    [Tool: openeo_get_results]                                                                                                                                                                        
    Downloaded: /tmp/ndvi_iowa_2024.tif                                                                                                                                                               
                                                                                                                                                                                                      
    [Tool: viz_show_ndvi_map]                                                                                                                                                                         
    [Interactive map displayed with NDVI results]                                                                                                                                                     
                                                                                                                                                                                                      
    **Results Summary:**                                                                                                                                                                              
    - NDVI Range: 0.15 to 0.82                                                                                                                                                                        
    - Mean NDVI: 0.58 (healthy vegetation)                                                                                                                                                            
    - Coverage: ~95% valid pixels (cloud masking worked well)                                                                                                                                         
                                                                                                                                                                                                      
    The map shows:                                                                                                                                                                                    
    - 🌿 Dark green areas (NDVI > 0.6): Healthy, dense crops                                                                                                                                          
    - 🟢 Light green (0.4-0.6): Moderate vegetation                                                                                                                                                   
    - 🟡 Yellow (0.2-0.4): Sparse vegetation or stressed crops                                                                                                                                        
    - 🟤 Brown (<0.2): Bare soil, roads, or buildings                                                                                                                                                 
                                                                                                                                                                                                      
    Would you like me to:                                                                                                                                                                             
    1. Generate a time series showing NDVI changes over the summer?                                                                                                                                   
    2. Run AI crop classification on this area?                                                                                                                                                       
    3. Save this workflow for reuse?                                                                                                                                                                  
    4. Export the results in different formats?                                                                                                                                                       
                                                                                                                                                                                                      
    ---                                                                                                                                                                                               
    Next Steps to Implement                                                                                                                                                                           
                                                                                                                                                                                                      
    1. Phase 1 - Core SDK Integration (1-2 weeks)                                                                                                                                                     
      - Set up project structure                                                                                                                                                                      
      - Implement Claude SDK client                                                                                                                                                                   
      - Create core OpenEO tools                                                                                                                                                                      
      - SQLite storage layer                                                                                                                                                                          
    2. Phase 2 - Validation & Education (1 week)                                                                                                                                                      
      - Process graph validator                                                                                                                                                                       
      - Educational knowledge base                                                                                                                                                                    
      - Error message improvements                                                                                                                                                                    
    3. Phase 3 - Visualization (1 week)                                                                                                                                                               
      - MCP-UI map components                                                                                                                                                                         
      - Chart components                                                                                                                                                                              
      - Comparison tools                                                                                                                                                                              
    4. Phase 4 - GeoAI Integration (2 weeks)                                                                                                                                                          
      - Model registry                                                                                                                                                                                
      - Segmentation inference                                                                                                                                                                        
      - Change detection                                                                                                                                                                              
      - Canopy height                                                                                                                                                                                 
    5. Phase 5 - Authentication & Production (1 week)                                                                                                                                                 
      - OIDC integration                                                                                                                                                                              
      - Session management                                                                                                                                                                            
      - Production deployment                                                                                                                                                                         
                                                                                                           