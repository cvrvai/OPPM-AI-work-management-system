import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useChatContext } from '@/hooks/useChatContext'
import { GoogleSheetsSetup } from './settings/GoogleSheetsSetup'
import { WorkspaceSettings } from './settings/WorkspaceSettings'
import { ProfileSettings } from './settings/ProfileSettings'
import { WorkspaceMembersPanel } from './settings/WorkspaceMembersPanel'
import { GitHubSettings } from './settings/GitHubSettings'
import { AIModelSettings } from './settings/AIModelSettings'
import { OPPMAISettings } from './settings/OPPMAISettings'
import {
  Cpu,
  Globe,
  UserCircle,
  CheckCircle,
  GitFork,
  Bot,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export function Settings() {
  const [searchParams] = useSearchParams()
  const initialTab = searchParams.get('tab')
  const [activeTab, setActiveTab] = useState<'profile' | 'workspace' | 'github' | 'ai' | 'googleSheets' | 'oppmAI'>(
    initialTab === 'googleSheets' ? 'googleSheets' : 'profile'
  )
  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  useChatContext('workspace')

  const navItems = [
    { id: 'profile'  as const, label: 'Profile',              icon: UserCircle, description: 'Name, email and account info' },
    ...(ws ? [{ id: 'workspace' as const, label: 'Workspace', icon: Globe, description: 'Workspace details and owner-only controls' }] : []),
    { id: 'googleSheets' as const, label: 'Google Sheets Setup', icon: CheckCircle, description: 'Enable AI write access for linked sheet editing' },
    { id: 'github'   as const, label: 'GitHub Integration',   icon: GitFork,    description: 'Connect repos and configure webhooks' },
    { id: 'ai'       as const, label: 'AI Models',            icon: Cpu,        description: 'LLM providers and API keys' },
    ...(ws ? [{ id: 'oppmAI' as const, label: 'OPPM AI',  icon: Bot,        description: 'Customize the OPPM sheet AI system prompt' }] : []),
  ]

  const active = navItems.find((n) => n.id === activeTab) ?? navItems[0]

  return (
    <div className="flex min-h-[calc(100vh-120px)] flex-col gap-6 lg:flex-row lg:gap-8">
      {/* â”€â”€ Left sidebar nav â”€â”€ */}
      <aside className="w-full shrink-0 lg:w-56">
        <div className="mb-5">
          <h1 className="text-xl font-bold text-text">Settings</h1>
          <p className="text-xs text-text-secondary mt-0.5 leading-relaxed">
            Configure your workspace
          </p>
        </div>
        <nav className="flex gap-2 overflow-x-auto pb-1 lg:block lg:space-y-0.5 lg:overflow-visible lg:pb-0">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-left whitespace-nowrap transition-colors lg:w-full',
                activeTab === id
                  ? 'bg-surface-alt text-text'
                  : 'text-text-secondary hover:bg-surface-alt hover:text-text'
              )}
            >
              <Icon className={cn('h-4 w-4 shrink-0', activeTab === id ? 'text-text' : 'text-text-secondary')} />
              {label}
            </button>
          ))}
        </nav>
      </aside>

      {/* â”€â”€ Divider â”€â”€ */}
      <div className="hidden w-px shrink-0 bg-border lg:block" />

      {/* â”€â”€ Content panel â”€â”€ */}
      <div className="flex-1 min-w-0">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-text flex items-center gap-2">
            <active.icon className="h-5 w-5 text-text-secondary" />
            {active.label}
          </h2>
          <p className="text-sm text-text-secondary mt-0.5">{active.description}</p>
        </div>

        {activeTab === 'profile'  && <ProfileSettings />}
        {activeTab === 'workspace' && ws && <WorkspaceSettings />}
        {activeTab === 'googleSheets' && <GoogleSheetsSetup />}
        {activeTab === 'github'   && <GitHubSettings />}
        {activeTab === 'ai'       && <AIModelSettings />}
        {activeTab === 'oppmAI'   && ws && <OPPMAISettings workspaceId={ws.id} />}
      </div>
    </div>
  )
}
