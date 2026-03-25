import { useState, useCallback, memo } from 'react'
import { User, Bot, Copy, Check, ChevronDown, ChevronRight, Wrench, AlertCircle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python'
import javascript from 'react-syntax-highlighter/dist/esm/languages/prism/javascript'
import typescript from 'react-syntax-highlighter/dist/esm/languages/prism/typescript'
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json'
import bash from 'react-syntax-highlighter/dist/esm/languages/prism/bash'
import sql from 'react-syntax-highlighter/dist/esm/languages/prism/sql'

SyntaxHighlighter.registerLanguage('python', python)
SyntaxHighlighter.registerLanguage('py', python)
SyntaxHighlighter.registerLanguage('javascript', javascript)
SyntaxHighlighter.registerLanguage('js', javascript)
SyntaxHighlighter.registerLanguage('typescript', typescript)
SyntaxHighlighter.registerLanguage('ts', typescript)
SyntaxHighlighter.registerLanguage('json', json)
SyntaxHighlighter.registerLanguage('bash', bash)
SyntaxHighlighter.registerLanguage('sh', bash)
SyntaxHighlighter.registerLanguage('shell', bash)
SyntaxHighlighter.registerLanguage('sql', sql)
import { Message, ToolCall as ToolCallType } from '@/types'
import { ToolResultCard } from './ToolResultCard'
import { cn } from '@/lib/utils'

interface ChatMessageProps {
  message: Message
}

export const ChatMessage = memo(function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'
  const [copied, setCopied] = useState(false)
  const [hovering, setHovering] = useState(false)

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [message.content])

  if (isSystem) {
    return (
      <div className="message-enter px-4 py-2">
        <div className="flex items-start gap-2 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-3 py-2 text-sm text-yellow-800 dark:text-yellow-200">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-500" />
          <span>{message.content}</span>
        </div>
      </div>
    )
  }

  if (message.role === 'tool' && message.toolName) {
    return (
      <div className="message-enter px-4 py-1.5">
        <div className="ml-10">
          <ToolResultCard toolName={message.toolName} result={message.toolResult} />
        </div>
      </div>
    )
  }

  if (isUser) {
    return (
      <div className="message-enter px-4 py-3">
        <div className="flex items-start gap-3">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <User className="h-3.5 w-3.5" />
          </div>
          <div className="min-w-0 flex-1 pt-0.5">
            <p className="text-sm font-medium text-foreground/80 mb-1">You</p>
            <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap">{message.content}</p>
          </div>
        </div>
      </div>
    )
  }

  // Assistant message
  return (
    <div
      className="message-enter group relative px-4 py-3"
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary/20 to-primary/5 text-primary">
          <Bot className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1 pt-0.5">
          <p className="text-sm font-medium text-primary/80 mb-1.5">Jona</p>

          <div className="prose-chat text-sm leading-relaxed">
            {message.isStreaming ? (
              <span className="whitespace-pre-wrap">{message.content}<span className="inline-block w-1.5 h-4 bg-primary/70 animate-pulse ml-0.5 align-text-bottom rounded-sm" /></span>
            ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '')
                  const codeString = String(children).replace(/\n$/, '')

                  if (match) {
                    return <CodeBlock language={match[1]} code={codeString} />
                  }

                  return (
                    <code
                      className="rounded bg-muted px-1.5 py-0.5 text-[13px] font-mono text-foreground"
                      {...props}
                    >
                      {children}
                    </code>
                  )
                },
                p({ children }) {
                  return <p className="mb-2 last:mb-0">{children}</p>
                },
                ul({ children }) {
                  return <ul className="mb-2 ml-4 list-disc space-y-1 last:mb-0">{children}</ul>
                },
                ol({ children }) {
                  return <ol className="mb-2 ml-4 list-decimal space-y-1 last:mb-0">{children}</ol>
                },
                li({ children }) {
                  return <li className="text-sm">{children}</li>
                },
                h1({ children }) {
                  return <h1 className="mb-2 mt-4 text-lg font-semibold first:mt-0">{children}</h1>
                },
                h2({ children }) {
                  return <h2 className="mb-2 mt-3 text-base font-semibold first:mt-0">{children}</h2>
                },
                h3({ children }) {
                  return <h3 className="mb-1.5 mt-2 text-sm font-semibold first:mt-0">{children}</h3>
                },
                a({ href, children }) {
                  return (
                    <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline hover:text-primary/80">
                      {children}
                    </a>
                  )
                },
                blockquote({ children }) {
                  return (
                    <blockquote className="mb-2 border-l-2 border-primary/30 pl-3 text-muted-foreground italic">
                      {children}
                    </blockquote>
                  )
                },
                table({ children }) {
                  return (
                    <div className="mb-2 overflow-x-auto rounded-lg border border-border">
                      <table className="w-full text-sm">{children}</table>
                    </div>
                  )
                },
                thead({ children }) {
                  return <thead className="bg-muted/50">{children}</thead>
                },
                th({ children }) {
                  return <th className="px-3 py-1.5 text-left font-medium">{children}</th>
                },
                td({ children }) {
                  return <td className="border-t border-border px-3 py-1.5">{children}</td>
                },
                hr() {
                  return <hr className="my-3 border-border" />
                },
                strong({ children }) {
                  return <strong className="font-semibold text-foreground">{children}</strong>
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
            )}
          </div>

          {message.toolCalls && message.toolCalls.length > 0 && (
            <div className="mt-2 flex flex-col gap-1.5">
              {message.toolCalls.map((toolCall) => (
                <ToolCallCard key={toolCall.id} toolCall={toolCall} />
              ))}
            </div>
          )}
        </div>

        {/* Copy button - appears on hover */}
        <div className={cn(
          "shrink-0 pt-6 transition-opacity duration-150",
          hovering ? "opacity-100" : "opacity-0"
        )}>
          <button
            onClick={handleCopy}
            className="rounded-md p-1.5 text-muted-foreground/60 hover:bg-muted hover:text-muted-foreground transition-colors"
            title="Copy message"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>
    </div>
  )
})

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="group/code relative my-2 overflow-hidden rounded-lg border border-border bg-[#282c34]">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-1.5">
        <span className="text-[11px] font-medium text-white/50">{language}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 rounded px-2 py-0.5 text-[11px] text-white/50 hover:bg-white/10 hover:text-white/80 transition-colors"
        >
          {copied ? (
            <>
              <Check className="h-3 w-3" />
              <span>Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3 w-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <SyntaxHighlighter
        style={oneDark}
        language={language}
        PreTag="div"
        customStyle={{
          margin: 0,
          padding: '12px 16px',
          background: 'transparent',
          fontSize: '13px',
          lineHeight: '1.5',
        }}
        codeTagProps={{
          style: { fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace" },
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
}

function ToolCallCard({ toolCall }: { toolCall: ToolCallType }) {
  const [expanded, setExpanded] = useState(false)

  const friendlyName = toolCall.name
    .replace(/^openeo_/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())

  const statusConfig = {
    pending: { color: 'text-muted-foreground', bg: 'bg-muted/50', label: 'Pending' },
    running: { color: 'text-primary', bg: 'bg-primary/5 border border-primary/20', label: 'Running' },
    completed: { color: 'text-success', bg: 'bg-success/5 border border-success/20', label: 'Done' },
    error: { color: 'text-destructive', bg: 'bg-destructive/5 border border-destructive/20', label: 'Error' },
  }

  const status = statusConfig[toolCall.status]

  return (
    <div className={cn("rounded-lg px-3 py-2 text-xs transition-all", status.bg)}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3 w-3 text-muted-foreground" />
        )}
        <Wrench className={cn("h-3 w-3", status.color)} />
        <span className="font-medium text-foreground">{friendlyName}</span>
        {toolCall.status === 'running' && (
          <span className="ml-1 inline-flex gap-0.5">
            <span className="h-1 w-1 rounded-full bg-primary animate-pulse" />
            <span className="h-1 w-1 rounded-full bg-primary animate-pulse [animation-delay:150ms]" />
            <span className="h-1 w-1 rounded-full bg-primary animate-pulse [animation-delay:300ms]" />
          </span>
        )}
        <span className={cn("ml-auto text-[10px]", status.color)}>{status.label}</span>
      </button>

      {expanded && toolCall.arguments && Object.keys(toolCall.arguments).length > 0 && (
        <div className="mt-2 rounded bg-muted/50 p-2 font-mono text-[11px] text-muted-foreground">
          {Object.entries(toolCall.arguments).map(([key, value]) => (
            <div key={key} className="truncate">
              <span className="text-primary/70">{key}</span>: {JSON.stringify(value)}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
