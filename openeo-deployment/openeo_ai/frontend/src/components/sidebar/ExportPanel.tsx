import { useState } from 'react'
import { Download, FileJson, FileText, BookOpen, Quote } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ExportFormat, Message, Visualization, QualityMetrics } from '@/types'
import { cn } from '@/lib/utils'

interface ExportPanelProps {
  messages: Message[]
  visualizations: Visualization[]
  qualityMetrics: QualityMetrics | null
  processGraph?: Record<string, unknown>
  className?: string
}

const EXPORT_FORMATS = [
  {
    id: 'notebook' as ExportFormat,
    name: 'Jupyter Notebook',
    description: 'Export as .ipynb for Python',
    icon: BookOpen,
  },
  {
    id: 'json' as ExportFormat,
    name: 'Process Graph JSON',
    description: 'OpenEO process graph definition',
    icon: FileJson,
  },
  {
    id: 'markdown' as ExportFormat,
    name: 'Markdown Report',
    description: 'Human-readable analysis report',
    icon: FileText,
  },
  {
    id: 'bibtex' as ExportFormat,
    name: 'BibTeX Citation',
    description: 'Academic citation format',
    icon: Quote,
  },
]

export function ExportPanel({
  messages,
  visualizations,
  qualityMetrics,
  processGraph,
  className,
}: ExportPanelProps) {
  const [exporting, setExporting] = useState<ExportFormat | null>(null)

  const handleExport = async (format: ExportFormat) => {
    setExporting(format)

    try {
      let content: string
      let filename: string
      let mimeType: string

      switch (format) {
        case 'notebook':
          content = generateNotebook(messages, visualizations, processGraph)
          filename = 'openeo_analysis.ipynb'
          mimeType = 'application/json'
          break

        case 'json':
          content = JSON.stringify(processGraph || {}, null, 2)
          filename = 'process_graph.json'
          mimeType = 'application/json'
          break

        case 'markdown':
          content = generateMarkdown(messages, visualizations, qualityMetrics)
          filename = 'analysis_report.md'
          mimeType = 'text/markdown'
          break

        case 'bibtex':
          content = generateBibTeX()
          filename = 'citation.bib'
          mimeType = 'text/plain'
          break

        default:
          return
      }

      downloadFile(content, filename, mimeType)
    } catch (error) {
      console.error('Export failed:', error)
    } finally {
      setExporting(null)
    }
  }

  return (
    <Card className={cn("", className)}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Download className="h-4 w-4" />
          Export
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {EXPORT_FORMATS.map((format) => {
          const Icon = format.icon
          const isExporting = exporting === format.id

          return (
            <Button
              key={format.id}
              variant="outline"
              className="w-full justify-start"
              onClick={() => handleExport(format.id)}
              disabled={isExporting}
            >
              <Icon className="mr-2 h-4 w-4" />
              <div className="flex-1 text-left">
                <div className="text-sm">{format.name}</div>
                <div className="text-xs text-muted-foreground">{format.description}</div>
              </div>
              {isExporting && (
                <span className="ml-2 animate-spin">...</span>
              )}
            </Button>
          )
        })}
      </CardContent>
    </Card>
  )
}

function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function generateNotebook(
  messages: Message[],
  _visualizations: Visualization[],
  processGraph?: Record<string, unknown>
): string {
  const cells = [
    {
      cell_type: 'markdown',
      metadata: {},
      source: [
        '# OpenEO Analysis Report\n',
        '\n',
        `Generated: ${new Date().toISOString()}\n`,
        '\n',
        'This notebook was automatically generated from an OpenEO AI Assistant session.\n',
      ],
    },
    {
      cell_type: 'code',
      metadata: {},
      source: [
        '# Install dependencies\n',
        '# !pip install openeo\n',
        '\n',
        'import openeo\n',
        '\n',
        '# Connect to OpenEO backend\n',
        'connection = openeo.connect("https://openeo.cloud")\n',
        'connection.authenticate_oidc()\n',
      ],
      execution_count: null,
      outputs: [],
    },
  ]

  // Add process graph if available
  if (processGraph) {
    cells.push({
      cell_type: 'code',
      metadata: {},
      source: [
        '# Process Graph Definition\n',
        `process_graph = ${JSON.stringify(processGraph, null, 2)}\n`,
        '\n',
        '# Execute the process graph\n',
        '# result = connection.execute(process_graph)\n',
      ],
      execution_count: null,
      outputs: [],
    })
  }

  // Add conversation summary
  const conversationMd = messages
    .filter((m) => m.role !== 'system')
    .map((m) => `**${m.role === 'user' ? 'User' : 'Assistant'}:** ${m.content}`)
    .join('\n\n')

  cells.push({
    cell_type: 'markdown',
    metadata: {},
    source: ['## Conversation Log\n', '\n', conversationMd],
  })

  const notebook = {
    nbformat: 4,
    nbformat_minor: 5,
    metadata: {
      kernelspec: {
        display_name: 'Python 3',
        language: 'python',
        name: 'python3',
      },
      language_info: {
        name: 'python',
        version: '3.9.0',
      },
    },
    cells,
  }

  return JSON.stringify(notebook, null, 2)
}

function generateMarkdown(
  messages: Message[],
  _visualizations: Visualization[],
  qualityMetrics: QualityMetrics | null
): string {
  let md = `# OpenEO Analysis Report

Generated: ${new Date().toISOString()}

## Summary

This report was generated from an OpenEO AI Assistant conversation.

`

  if (qualityMetrics) {
    md += `## Quality Metrics

- **Overall Score:** ${qualityMetrics.overallScore}% (Grade: ${qualityMetrics.grade})
- **Cloud Coverage:** ${qualityMetrics.cloudCoverage.toFixed(1)}%
- **Temporal Coverage:** ${qualityMetrics.temporalCoverage.toFixed(1)}%
- **Spatial Coverage:** ${qualityMetrics.spatialCoverage.toFixed(1)}%
- **Valid Pixels:** ${qualityMetrics.validPixelPercentage.toFixed(1)}%

### Recommendations

${qualityMetrics.recommendations.map((r) => `- ${r}`).join('\n')}

`
  }

  md += `## Conversation

`

  for (const message of messages) {
    if (message.role === 'system') continue
    const role = message.role === 'user' ? 'User' : 'Assistant'
    md += `### ${role}

${message.content}

`
  }

  return md
}

function generateBibTeX(): string {
  const date = new Date()
  const year = date.getFullYear()
  const month = date.toLocaleString('en-US', { month: 'long' })

  return `@misc{openeo_analysis_${year},
  title = {Earth Observation Analysis using OpenEO},
  author = {OpenEO AI Assistant},
  year = {${year}},
  month = {${month}},
  note = {Analysis generated using OpenEO platform and Claude AI},
  url = {https://openeo.org/}
}

@article{openeo_2020,
  title = {openEO: A Common, Open Source Interface between Earth Observation Data Infrastructures and Front-End Applications},
  author = {Schramm, Matthias and Pebesma, Edzer and Milošević, Miloš and Kadunc, Luka and Jacob, Alexander},
  journal = {Remote Sensing},
  volume = {12},
  number = {6},
  pages = {1059},
  year = {2020},
  publisher = {MDPI}
}`
}
