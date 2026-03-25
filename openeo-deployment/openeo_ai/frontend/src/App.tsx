import { useState, useCallback, useRef, useEffect } from 'react'
import { Activity, History, Download, Leaf, MessageSquare, Database, FolderOpen } from 'lucide-react'
import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'
import { SettingsDialog } from '@/components/layout/SettingsDialog'
import { ChatPanel } from '@/components/chat/ChatPanel'
import { VisualizationPanel } from '@/components/visualizations/VisualizationPanel'
import { QualityMetricsPanel } from '@/components/sidebar/QualityMetricsPanel'
import { WorkflowHistoryPanel } from '@/components/sidebar/WorkflowHistoryPanel'
import { ExportPanel } from '@/components/sidebar/ExportPanel'
import { SustainabilityPanel } from '@/components/sidebar/SustainabilityPanel'
import { SavedJobsPanel } from '@/components/sidebar/SavedJobsPanel'
import { ProjectsPanel } from '@/components/sidebar/ProjectsPanel'
import { TooltipProvider } from '@/components/ui/tooltip'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useLocalStorage } from '@/hooks/useLocalStorage'
import { Message, Visualization, QualityMetrics, SustainabilityMetrics, Workflow, ToolCall, ThinkingStep, BBox, SavedJob, Project, ClarificationQuestion } from '@/types'
import { generateId } from '@/lib/utils'

export default function App() {
  // State
  const [messages, setMessages] = useState<Message[]>([])
  const [visualizations, setVisualizations] = useState<Visualization[]>([])
  const [qualityMetrics, setQualityMetrics] = useState<QualityMetrics | null>(null)
  const [sustainabilityMetrics, setSustainabilityMetrics] = useState<SustainabilityMetrics | null>(null)
  const [workflows, setWorkflows] = useLocalStorage<Workflow[]>('openeo-workflows', [])
  const [currentWorkflow, setCurrentWorkflow] = useState<Workflow | null>(null)
  const [processGraph, setProcessGraph] = useState<Record<string, unknown> | null>(null)
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([])
  const [selectedBbox, setSelectedBbox] = useState<BBox | null>(null)
  const selectedBboxRef = useRef<BBox | null>(null)
  useEffect(() => { selectedBboxRef.current = selectedBbox }, [selectedBbox])
  const [projects, setProjects] = useLocalStorage<Project[]>('openeo-projects', [])
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null)
  const [contextSuggestions, setContextSuggestions] = useState<string[]>([])
  const [pendingClarification, setPendingClarification] = useState<ClarificationQuestion[] | null>(null)
  const [isDark, setIsDark] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const streamingMessageIdRef = useRef<string | null>(null)

  // WebSocket connection
  const handleMessage = useCallback((message: Message) => {
    setMessages((prev) => [...prev, message])

    // Update current workflow
    if (currentWorkflow) {
      setCurrentWorkflow((prev) => {
        if (!prev) return prev
        return {
          ...prev,
          status: message.role === 'assistant' ? 'completed' : prev.status,
          completedAt: message.role === 'assistant' ? new Date() : prev.completedAt,
        }
      })
    }
  }, [currentWorkflow])

  const handleVisualization = useCallback((visualization: Visualization) => {
    setVisualizations((prev) => [...prev, visualization])
  }, [])

  const handleQualityMetrics = useCallback((metrics: QualityMetrics) => {
    setQualityMetrics(metrics)
  }, [])

  const handleToolCall = useCallback((toolCall: ToolCall) => {
    // Update current workflow steps
    if (currentWorkflow) {
      setCurrentWorkflow((prev) => {
        if (!prev) return prev
        const stepIndex = prev.steps.findIndex((s) => s.id === toolCall.id)
        if (stepIndex >= 0) {
          const newSteps = [...prev.steps]
          newSteps[stepIndex] = {
            ...newSteps[stepIndex],
            status: toolCall.status,
            result: toolCall.result,
            completedAt: toolCall.status === 'completed' ? new Date() : undefined,
          }
          return { ...prev, steps: newSteps }
        } else if (toolCall.status === 'running') {
          return {
            ...prev,
            steps: [
              ...prev.steps,
              {
                id: toolCall.id,
                name: toolCall.name,
                status: 'running',
                tool: toolCall.name,
                arguments: toolCall.arguments,
                startedAt: new Date(),
              },
            ],
          }
        }
        return prev
      })
    }

    // Inject tool result as a chat message (MCP-UI card)
    if (toolCall.status === 'completed' && toolCall.result != null) {
      setMessages((prev) => [...prev, {
        id: generateId(),
        role: 'tool' as const,
        content: '',
        timestamp: new Date(),
        toolName: toolCall.name,
        toolResult: toolCall.result,
      }])
    }
  }, [currentWorkflow])

  const finalizeStreaming = useCallback(() => {
    const msgId = streamingMessageIdRef.current
    if (!msgId) return
    setMessages(prev => {
      const msg = prev.find(m => m.id === msgId)
      if (msg && !msg.content.trim()) {
        // Remove empty streaming messages (Bug 5)
        return prev.filter(m => m.id !== msgId)
      }
      return prev.map(m => m.id === msgId ? { ...m, isStreaming: false } : m)
    })
    streamingMessageIdRef.current = null
  }, [])

  const handleError = useCallback((error: Error) => {
    console.error('WebSocket error:', error)
    finalizeStreaming()
    setThinkingSteps([])
    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: 'system',
        content: `Error: ${error.message}`,
        timestamp: new Date(),
      },
    ])
    setCurrentWorkflow((prev) => {
      if (!prev || prev.status !== 'running') return prev
      return { ...prev, status: 'error' }
    })
  }, [finalizeStreaming])

  const handleProcessGraph = useCallback((graph: Record<string, unknown>) => {
    setProcessGraph(graph)
  }, [])

  const handleThinking = useCallback((thinkingStep: ThinkingStep) => {
    setThinkingSteps((prev) => {
      // If step is completed, remove it from the list
      if (thinkingStep.completed) {
        return prev.filter((s) => s.id !== thinkingStep.id)
      }
      // Keep only the last 3 active steps to avoid accumulation
      const newSteps = [...prev.filter(s => !s.completed), thinkingStep]
      return newSteps.slice(-3)
    })
  }, [])

  // Streaming text callbacks
  const handleTextStreamStart = useCallback(() => {
    const id = generateId()
    streamingMessageIdRef.current = id
    setMessages(prev => [...prev, {
      id, role: 'assistant' as const, content: '', timestamp: new Date(), isStreaming: true
    }])
  }, [])

  const handleTextDelta = useCallback((content: string) => {
    const msgId = streamingMessageIdRef.current
    if (!msgId) return
    setMessages(prev =>
      prev.map(m => m.id === msgId ? { ...m, content: m.content + content } : m)
    )
  }, [])

  const handleTextStreamEnd = useCallback(() => {
    finalizeStreaming()
  }, [finalizeStreaming])

  const handleSuggestions = useCallback((suggestions: string[]) => {
    setContextSuggestions(suggestions)
  }, [])

  const handleSessionRestored = useCallback((sessionId: string) => {
    console.log('[App] Session restored:', sessionId)
  }, [])

  const handleClarification = useCallback((questions: ClarificationQuestion[]) => {
    setPendingClarification(questions)
  }, [])

  // handleClarificationSubmit defined after useWebSocket returns sendRaw

  const handleDone = useCallback(() => {
    finalizeStreaming()
    setThinkingSteps([])
    setCurrentWorkflow((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        status: 'completed',
        completedAt: new Date(),
      }
    })
  }, [finalizeStreaming])

  const { isConnected, isProcessing, sendMessage, sendRaw, reconnect, newSession } = useWebSocket({
    url: '/ws',
    onMessage: handleMessage,
    onVisualization: handleVisualization,
    onQualityMetrics: handleQualityMetrics,
    onToolCall: handleToolCall,
    onThinking: handleThinking,
    onError: handleError,
    onProcessGraph: handleProcessGraph,
    onTextStreamStart: handleTextStreamStart,
    onTextDelta: handleTextDelta,
    onTextStreamEnd: handleTextStreamEnd,
    onSuggestions: handleSuggestions,
    onSessionRestored: handleSessionRestored,
    onClarification: handleClarification,
    onDone: handleDone,
  })

  const handleClarificationSubmit = useCallback((answers: Record<string, string | string[]>) => {
    setPendingClarification(null)
    sendRaw({ type: 'clarification_response', answers })
  }, [sendRaw])

  // Finalize streaming on disconnect
  const prevConnectedRef = useRef(true)
  useEffect(() => {
    if (prevConnectedRef.current && !isConnected) {
      finalizeStreaming()
    }
    prevConnectedRef.current = isConnected
  }, [isConnected, finalizeStreaming])

  // Handlers
  const handleSendMessage = useCallback((content: string) => {
    // Clear thinking steps and suggestions for new message
    setThinkingSteps([])
    setContextSuggestions([])

    // Add user message to chat
    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMessage])

    // Create new workflow
    const workflow: Workflow = {
      id: generateId(),
      name: content.slice(0, 50) + (content.length > 50 ? '...' : ''),
      description: content,
      status: 'running',
      steps: [],
      createdAt: new Date(),
    }
    setCurrentWorkflow(workflow)

    // Save to history
    setWorkflows((prev) => [workflow, ...prev.slice(0, 19)])

    // Prepend bbox context if selected (use ref to always get latest value)
    const bbox = selectedBboxRef.current
    const messageContent = bbox
      ? `[Bounding box: west=${bbox.west}, south=${bbox.south}, east=${bbox.east}, north=${bbox.north}] ${content}`
      : content

    console.log('[App] Sending message:', messageContent, 'bbox:', bbox)

    // Send to backend
    sendMessage(messageContent)

    // Update sustainability estimate
    setSustainabilityMetrics({
      carbonFootprint: Math.random() * 0.1,
      dataTransferred: Math.random() * 100000000,
      computeTime: Math.random() * 60,
      energyUsed: Math.random() * 0.01,
    })
  }, [sendMessage, setWorkflows])

  const handleReplayWorkflow = useCallback((workflow: Workflow) => {
    if (workflow.description) {
      handleSendMessage(workflow.description)
    }
  }, [handleSendMessage])

  const handleStop = useCallback(() => {
    sendRaw({ type: 'stop' })
  }, [sendRaw])

  const handleLoadSavedJob = useCallback((job: SavedJob) => {
    sendRaw({ type: 'load_saved_job', save_id: job.save_id })
  }, [sendRaw])

  const handleSelectProject = useCallback((project: Project) => {
    setActiveProjectId(project.id)
  }, [])

  const handleCreateProject = useCallback((name: string, description: string) => {
    const now = new Date().toISOString()
    const project: Project = {
      id: generateId(),
      name,
      description,
      analysisCount: 0,
      createdAt: now,
      updatedAt: now,
    }
    setProjects((prev) => [project, ...prev])
    setActiveProjectId(project.id)
  }, [setProjects])

  const handleDeleteProject = useCallback((id: string) => {
    setProjects((prev) => prev.filter((p) => p.id !== id))
    if (activeProjectId === id) setActiveProjectId(null)
  }, [setProjects, activeProjectId])

  const handleRenameProject = useCallback((id: string, name: string) => {
    setProjects((prev) =>
      prev.map((p) => p.id === id ? { ...p, name, updatedAt: new Date().toISOString() } : p)
    )
  }, [setProjects])

  const handleToggleTheme = useCallback(() => {
    setIsDark((prev) => !prev)
    document.documentElement.classList.toggle('dark')
  }, [])

  const handleSettings = useCallback(() => {
    setSettingsOpen(true)
  }, [])

  const handleThemeChange = useCallback((theme: 'system' | 'light' | 'dark') => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark')
      setIsDark(true)
    } else if (theme === 'light') {
      document.documentElement.classList.remove('dark')
      setIsDark(false)
    } else {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      if (prefersDark) {
        document.documentElement.classList.add('dark')
        setIsDark(true)
      } else {
        document.documentElement.classList.remove('dark')
        setIsDark(false)
      }
    }
  }, [])

  const handleNewChat = useCallback(() => {
    // Clear all chat state
    setMessages([])
    setVisualizations([])
    setQualityMetrics(null)
    setProcessGraph(null)
    setThinkingSteps([])
    setContextSuggestions([])
    setPendingClarification(null)
    setCurrentWorkflow(null)
    // Start fresh WebSocket session
    newSession()
  }, [newSession])

  const handleHelp = useCallback(() => {
    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: 'system',
        content: `Welcome to OpenEO AI Assistant!

You can ask questions like:
• "Show NDVI for Kerala, India during monsoon 2024"
• "Compare land cover changes in Amazon 2020 vs 2024"
• "Find cloud-free Sentinel-2 imagery for Paris"
• "Calculate vegetation health for California"

I can help you with:
- Earth observation data discovery
- Vegetation indices (NDVI, EVI, etc.)
- Change detection analysis
- Terrain analysis
- Time series visualization

Just type your question below!`,
        timestamp: new Date(),
      },
    ])
  }, [])

  // Left sidebar tab (Chat)
  const leftSidebarTabs = [
    {
      id: 'chat',
      label: 'Chat',
      icon: <MessageSquare className="h-4 w-4" />,
      content: (
        <ChatPanel
          messages={messages}
          onSendMessage={handleSendMessage}
          isProcessing={isProcessing}
          isConnected={isConnected}
          thinkingSteps={thinkingSteps}
          onReconnect={reconnect}
          activeBbox={selectedBbox}
          onStop={handleStop}
          contextSuggestions={contextSuggestions}
          pendingClarification={pendingClarification}
          onClarificationSubmit={handleClarificationSubmit}
        />
      ),
    },
  ]

  // Right sidebar tabs
  const rightSidebarTabs = [
    {
      id: 'quality',
      label: 'Quality',
      icon: <Activity className="h-4 w-4" />,
      content: <QualityMetricsPanel metrics={qualityMetrics} />,
    },
    {
      id: 'projects',
      label: 'Projects',
      icon: <FolderOpen className="h-4 w-4" />,
      content: (
        <ProjectsPanel
          projects={projects}
          activeProjectId={activeProjectId}
          onSelectProject={handleSelectProject}
          onCreateProject={handleCreateProject}
          onDeleteProject={handleDeleteProject}
          onRenameProject={handleRenameProject}
        />
      ),
    },
    {
      id: 'history',
      label: 'History',
      icon: <History className="h-4 w-4" />,
      content: (
        <WorkflowHistoryPanel
          workflows={workflows}
          onReplay={handleReplayWorkflow}
        />
      ),
    },
    {
      id: 'export',
      label: 'Export',
      icon: <Download className="h-4 w-4" />,
      content: (
        <ExportPanel
          messages={messages}
          visualizations={visualizations}
          qualityMetrics={qualityMetrics}
          processGraph={processGraph || undefined}
        />
      ),
    },
    {
      id: 'saved',
      label: 'Saved',
      icon: <Database className="h-4 w-4" />,
      content: <SavedJobsPanel onLoadJob={handleLoadSavedJob} />,
    },
    {
      id: 'eco',
      label: 'Eco',
      icon: <Leaf className="h-4 w-4" />,
      content: <SustainabilityPanel metrics={sustainabilityMetrics} />,
    },
  ]

  return (
    <TooltipProvider>
      <div className="flex h-screen flex-col bg-background">
        <Header
          isConnected={isConnected}
          isDark={isDark}
          onToggleTheme={handleToggleTheme}
          onHelp={handleHelp}
          onSettings={handleSettings}
          onNewChat={handleNewChat}
        />

        <SettingsDialog
          open={settingsOpen}
          onOpenChange={setSettingsOpen}
          onThemeChange={handleThemeChange}
        />

        <div className="flex flex-1 overflow-hidden">
          {/* Left Sidebar - Chat */}
          <Sidebar
            position="left"
            tabs={leftSidebarTabs}
            defaultCollapsed={false}
          />

          {/* Main Content - Visualization */}
          <div className="flex flex-1 flex-col overflow-hidden p-3">
            <VisualizationPanel
              visualizations={visualizations}
              className="h-full"
              onBboxChange={setSelectedBbox}
              bbox={selectedBbox}
            />
          </div>

          {/* Right Sidebar */}
          <Sidebar
            position="right"
            tabs={rightSidebarTabs}
            defaultCollapsed={false}
          />
        </div>
      </div>
    </TooltipProvider>
  )
}
