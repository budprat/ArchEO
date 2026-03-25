import { useState, useEffect } from 'react'
import { Settings, Monitor, Sun, Moon } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { useLocalStorage } from '@/hooks/useLocalStorage'

export interface AppSettings {
  apiEndpoint: string
  themePreference: 'system' | 'light' | 'dark'
  notifications: {
    showConnectionStatus: boolean
    showProcessingAlerts: boolean
    showCompletionAlerts: boolean
  }
}

const DEFAULT_SETTINGS: AppSettings = {
  apiEndpoint: '/ws',
  themePreference: 'system',
  notifications: {
    showConnectionStatus: true,
    showProcessingAlerts: true,
    showCompletionAlerts: true,
  },
}

interface SettingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onThemeChange?: (theme: 'system' | 'light' | 'dark') => void
}

export function SettingsDialog({ open, onOpenChange, onThemeChange }: SettingsDialogProps) {
  const [savedSettings, setSavedSettings] = useLocalStorage<AppSettings>('openeo-settings', DEFAULT_SETTINGS)
  const [draft, setDraft] = useState<AppSettings>(savedSettings)

  useEffect(() => {
    if (open) {
      setDraft(savedSettings)
    }
  }, [open, savedSettings])

  const handleSave = () => {
    setSavedSettings(draft)
    if (onThemeChange && draft.themePreference !== savedSettings.themePreference) {
      onThemeChange(draft.themePreference)
    }
    onOpenChange(false)
  }

  const handleReset = () => {
    setDraft(DEFAULT_SETTINGS)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Settings
          </DialogTitle>
          <DialogDescription>
            Configure your OpenEO AI Assistant preferences.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* API Endpoint */}
          <div className="space-y-2">
            <label className="text-sm font-medium">API Endpoint URL</label>
            <input
              type="text"
              value={draft.apiEndpoint}
              onChange={(e) => setDraft({ ...draft, apiEndpoint: e.target.value })}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="/ws"
            />
            <p className="text-xs text-muted-foreground">
              WebSocket endpoint for the backend connection.
            </p>
          </div>

          <Separator />

          {/* Theme Preference */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Theme</label>
            <Select
              value={draft.themePreference}
              onValueChange={(value: 'system' | 'light' | 'dark') =>
                setDraft({ ...draft, themePreference: value })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="system">
                  <span className="flex items-center gap-2">
                    <Monitor className="h-4 w-4" />
                    System
                  </span>
                </SelectItem>
                <SelectItem value="light">
                  <span className="flex items-center gap-2">
                    <Sun className="h-4 w-4" />
                    Light
                  </span>
                </SelectItem>
                <SelectItem value="dark">
                  <span className="flex items-center gap-2">
                    <Moon className="h-4 w-4" />
                    Dark
                  </span>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Separator />

          {/* Notification Preferences */}
          <div className="space-y-3">
            <label className="text-sm font-medium">Notifications</label>

            <CheckboxRow
              label="Connection status changes"
              description="Show alerts when WebSocket connects or disconnects"
              checked={draft.notifications.showConnectionStatus}
              onChange={(checked) =>
                setDraft({
                  ...draft,
                  notifications: { ...draft.notifications, showConnectionStatus: checked },
                })
              }
            />

            <CheckboxRow
              label="Processing alerts"
              description="Show notifications when processing starts"
              checked={draft.notifications.showProcessingAlerts}
              onChange={(checked) =>
                setDraft({
                  ...draft,
                  notifications: { ...draft.notifications, showProcessingAlerts: checked },
                })
              }
            />

            <CheckboxRow
              label="Completion alerts"
              description="Show notifications when analysis completes"
              checked={draft.notifications.showCompletionAlerts}
              onChange={(checked) =>
                setDraft({
                  ...draft,
                  notifications: { ...draft.notifications, showCompletionAlerts: checked },
                })
              }
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleReset}>
            Reset to Defaults
          </Button>
          <Button onClick={handleSave}>
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function CheckboxRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string
  description: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-md p-2 transition-colors hover:bg-muted/50">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded border-input accent-primary"
      />
      <div>
        <div className="text-sm">{label}</div>
        <div className="text-xs text-muted-foreground">{description}</div>
      </div>
    </label>
  )
}
