import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { WSProvider }    from './contexts/WSContext'
import { ThemeProvider } from './contexts/ThemeContext'
import { AppShell }      from './components/shell/AppShell'
import LandingPage        from './pages/LandingPage'
import LoginPage          from './pages/LoginPage'
import SignupPage         from './pages/SignupPage'
import AuthCallbackPage   from './pages/AuthCallbackPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage  from './pages/ResetPasswordPage'
import AccessDenied       from './components/shell/AccessDenied'
import { Spinner }        from './components/ui'

// ── Platform Admin pages ───────────────────────────────────────────────────────
import AdminPlatformOverview    from './pages/admin/AdminPlatformOverview'
import AdminAssistant           from './pages/admin/AdminAssistant'
// CUSTOMERS
import AdminOrganizations       from './pages/admin/AdminOrganizations'
import AdminOrgDetail           from './pages/admin/AdminOrgDetail'
import UsersPage                from './pages/admin/UsersPage'
// WORKFLOWS
import AdminWorkflowCatalog     from './pages/admin/AdminWorkflowCatalog'
import AdminWorkflowAssignments from './pages/admin/AdminWorkflowAssignments'
import AdminRoutingAssignments  from './pages/admin/AdminRoutingAssignments'
import AdminWorkflowRuns        from './pages/admin/AdminWorkflowRuns'
// BILLING
import AdminPlans               from './pages/admin/AdminPlans'
import AdminSubscriptions       from './pages/admin/AdminSubscriptions'
import AdminUsageCost           from './pages/admin/AdminUsageCost'
import AdminInvoices            from './pages/admin/AdminInvoices'
// AI PLATFORM
import AdminProviderConnections from './pages/admin/AdminProviderConnections'
import AdminModelCatalog        from './pages/admin/AdminModelCatalog'
// OPERATIONS
import AdminSystemHealth        from './pages/admin/AdminSystemHealth'
import AdminAuditLog            from './pages/admin/AdminAuditLog'
import AdminExceptions          from './pages/admin/AdminExceptions'
// SYSTEM
import AdminPlatformSettings    from './pages/admin/AdminPlatformSettings'

// ── SMB Owner pages ────────────────────────────────────────────────────────────
import ConnectionsPage     from './pages/setup/ConnectionsPage'
import CasesPage           from './pages/medical/CasesPage'
import EmailSummarizerPage from './pages/client/EmailSummarizerPage'
import ProductLaunchPage   from './pages/client/ProductLaunchPage'
import UniversalWorkflowRunner from './pages/client/UniversalWorkflowRunner'
import Dashboard           from './pages/client/Dashboard'
import CopilotPage         from './pages/client/CopilotPage'
import EscalationsPage     from './pages/client/EscalationsPage'
import WorkflowsPage       from './pages/client/WorkflowsPage'
import WorkflowLibrary     from './pages/client/WorkflowLibrary'
import AIEngine            from './pages/client/AIEngine'
import AIEngineSettings    from './pages/client/AIEngineSettings'
import GeneralSettings     from './pages/client/GeneralSettings'
import BudgetPage          from './pages/client/BudgetPage'
import EvidencePage        from './pages/client/EvidencePage'

// ── Admin-accessible technical tools (kept for operational use) ───────────────
import WorkflowDetail  from './pages/client/WorkflowDetail'
import WorkflowBuilder from './pages/client/WorkflowBuilder'
import ModelSettings   from './pages/client/ModelSettings'
import ToolsPage       from './pages/client/ToolsPage'
import PromptStudio    from './pages/client/PromptStudio'
import EmailQueuePage  from './pages/client/EmailQueuePage'
import PatternsPage    from './pages/client/PatternsPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function FullScreenLoader() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
      <div className="flex items-center justify-center mb-4">
        <img 
          src="/isolatelogo.svg" 
          alt="Isolate" 
          className="h-8 w-auto max-w-[140px] object-contain dark:brightness-110"
        />
      </div>
      <div className="flex items-center gap-2 text-slate-500 text-sm">
        <Spinner className="w-4 h-4 text-blue-600 animate-spin" />
        <span>Verifying authentication...</span>
      </div>
    </div>
  )
}

function HomeRedirect() {
  const { user, token, loading } = useAuth()
  if (loading) return <FullScreenLoader />
  if (!token || !user) return <LandingPage />
  if (user.requires_onboarding) return <Navigate to="/auth/signup" replace />
  const isAdmin = user.role === 'super_admin' || user.role === 'platform_admin'
  return <Navigate to={isAdmin ? '/admin/copilot' : '/copilot'} replace />
}

function ProtectedRoute({ children, adminOnly = false }) {
  const { user, token, loading } = useAuth()
  if (loading) return <FullScreenLoader />
  if (!token || !user) return <Navigate to="/auth" replace />
  if (user.requires_onboarding) return <Navigate to="/auth/signup" replace />
  const isAdmin = user.role === 'super_admin' || user.role === 'platform_admin'
  if (adminOnly && !isAdmin) return <AccessDenied />
  return children
}

function Wrap({ adminOnly = false, children }) {
  return (
    <ProtectedRoute adminOnly={adminOnly}>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  )
}

function AppRoutes() {
  return (
    <Routes>
      {/* ── Public Landing Page & Auth ────────────────────────────────────── */}
      <Route path="/landing"              element={<LandingPage />} />
      <Route path="/auth"                 element={<LoginPage />} />
      <Route path="/auth/signup"          element={<SignupPage />} />
      <Route path="/auth/callback"        element={<AuthCallbackPage />} />
      <Route path="/auth/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/auth/reset-password"  element={<ResetPasswordPage />} />
      <Route path="/" element={<HomeRedirect />} />

      {/* ── Platform Admin — OVERVIEW ─────────────────────────────────────── */}
      <Route path="/admin"         element={<Wrap adminOnly><AdminPlatformOverview /></Wrap>} />
      <Route path="/admin/copilot" element={<Wrap adminOnly><AdminAssistant /></Wrap>} />

      {/* ── Platform Admin — CUSTOMERS ───────────────────────────────────── */}
      <Route path="/admin/organizations"        element={<Wrap adminOnly><AdminOrganizations /></Wrap>} />
      <Route path="/admin/organizations/:orgId" element={<Wrap adminOnly><AdminOrgDetail /></Wrap>} />
      <Route path="/admin/users"                element={<Wrap adminOnly><UsersPage /></Wrap>} />

      {/* ── Platform Admin — WORKFLOWS ───────────────────────────────────── */}
      <Route path="/admin/workflows/catalog"      element={<Wrap adminOnly><AdminWorkflowCatalog /></Wrap>} />
      <Route path="/admin/workflows/assignments"  element={<Wrap adminOnly><AdminWorkflowAssignments /></Wrap>} />
      <Route path="/admin/runs"                   element={<Wrap adminOnly><AdminWorkflowRuns /></Wrap>} />

      {/* ── Platform Admin — BILLING ─────────────────────────────────────── */}
      <Route path="/admin/plans"         element={<Wrap adminOnly><AdminPlans /></Wrap>} />
      <Route path="/admin/subscriptions" element={<Wrap adminOnly><AdminSubscriptions /></Wrap>} />
      <Route path="/admin/usage"         element={<Wrap adminOnly><AdminUsageCost /></Wrap>} />
      <Route path="/admin/invoices"      element={<Wrap adminOnly><AdminInvoices /></Wrap>} />

      {/* ── Platform Admin — AI PLATFORM ─────────────────────────────────── */}
      <Route path="/admin/providers" element={<Wrap adminOnly><AdminProviderConnections /></Wrap>} />
      <Route path="/admin/models"    element={<Wrap adminOnly><AdminModelCatalog /></Wrap>} />
      <Route path="/admin/routing"   element={<Wrap adminOnly><AdminRoutingAssignments /></Wrap>} />

      {/* ── Platform Admin — OPERATIONS ──────────────────────────────────── */}
      <Route path="/admin/health"      element={<Wrap adminOnly><AdminSystemHealth /></Wrap>} />
      <Route path="/admin/audit"       element={<Wrap adminOnly><AdminAuditLog /></Wrap>} />
      <Route path="/admin/exceptions"  element={<Wrap adminOnly><AdminExceptions /></Wrap>} />

      {/* ── Platform Admin — SYSTEM ──────────────────────────────────────── */}
      <Route path="/admin/settings" element={<Wrap adminOnly><AdminPlatformSettings /></Wrap>} />

      {/* ── SMB Owner — Operations ───────────────────────────────────────── */}
      <Route path="/dashboard"    element={<Wrap><Dashboard /></Wrap>} />
      <Route path="/copilot"      element={<Wrap><CopilotPage /></Wrap>} />
      <Route path="/escalations"  element={<Wrap><EscalationsPage /></Wrap>} />
      <Route path="/workflows"    element={<Wrap><WorkflowsPage /></Wrap>} />
      <Route path="/medical/cases" element={<Wrap><CasesPage /></Wrap>} />

      {/* Dynamic & Universal Workflow Active Canvas Runners */}
      <Route path="/workflows/product_launch"            element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/product_launch_sprint"     element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/invoice_processing"        element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/invoice_extractor"         element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/lead_scoring"              element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/lead_enrichment_crm"       element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/finance_operations"        element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/telegram_customer_agent"   element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/devops_alert_triage"       element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/medical_journey_operations" element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/email_summarizer"          element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/meeting_intelligence_followup" element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/meeting_intelligence"          element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/run/:runId"                element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/workflows/run"                       element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/product-launch"                      element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/email-summarizer"                    element={<Wrap><UniversalWorkflowRunner /></Wrap>} />

      {/* ── SMB Owner — Configuration ────────────────────────────────────── */}
      <Route path="/workflow-library"      element={<Wrap><WorkflowLibrary /></Wrap>} />
      <Route path="/integrations"          element={<Wrap><ConnectionsPage /></Wrap>} />
      <Route path="/setup/connections"     element={<Wrap><ConnectionsPage /></Wrap>} />
      <Route path="/settings/integrations" element={<Wrap><ConnectionsPage /></Wrap>} />
      <Route path="/ai-engine"             element={<Wrap adminOnly><AIEngine /></Wrap>} />

      {/* ── SMB Owner — Settings ─────────────────────────────────────────── */}
      <Route path="/settings/general"   element={<Wrap><GeneralSettings /></Wrap>} />
      <Route path="/settings/ai-engine" element={<Wrap adminOnly><AIEngineSettings /></Wrap>} />
      <Route path="/budget"             element={<Wrap><BudgetPage /></Wrap>} />
      <Route path="/evidence"           element={<Wrap><EvidencePage /></Wrap>} />
      <Route path="/config"             element={<Wrap><GeneralSettings /></Wrap>} />

      {/* ── Admin-accessible technical tools ─────────────────────────────── */}
      <Route path="/workflows/builder" element={<Wrap adminOnly><WorkflowBuilder /></Wrap>} />
      <Route path="/workflows/:runId"  element={<Wrap><UniversalWorkflowRunner /></Wrap>} />
      <Route path="/models"            element={<Wrap adminOnly><ModelSettings /></Wrap>} />
      <Route path="/tools"             element={<Wrap adminOnly><ToolsPage /></Wrap>} />
      <Route path="/prompts"           element={<Wrap adminOnly><PromptStudio /></Wrap>} />
      <Route path="/email-queue"       element={<Wrap><EmailQueuePage /></Wrap>} />
      <Route path="/patterns"          element={<Wrap adminOnly><PatternsPage /></Wrap>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AuthProvider>
            <WSProvider>
              <AppRoutes />
            </WSProvider>
          </AuthProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
