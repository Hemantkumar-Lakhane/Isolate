// frontend/src/pages/onboarding/OnboardingLayout.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Full-screen wrapper for the onboarding wizard.
// Uses a fixed-height viewport approach: the header is sticky at the top and
// the content area scrolls independently. The body itself is never locked so
// tall steps (like WorkflowGoals) remain fully accessible on small screens.
// ─────────────────────────────────────────────────────────────────────────────

export default function OnboardingLayout({ children }) {
  return (
    // h-screen + overflow-hidden on the outermost div creates the viewport
    // boundary without touching document.body — avoids conflicts with the
    // browser's native scroll restoration and mobile Safari bounce.
    <div className="h-screen bg-slate-50 flex flex-col overflow-hidden">
      {/* ── Sticky top bar ──────────────────────────────────────────────── */}
      <header className="flex-shrink-0 w-full border-b border-slate-200 bg-white/80 backdrop-blur-sm z-10">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center shadow-sm">
              <span className="text-white font-bold text-xs">S</span>
            </div>
            <span className="text-base font-semibold text-slate-900 tracking-tight">SMBFlow</span>
          </div>
        </div>
      </header>

      {/* ── Scrollable content area ─────────────────────────────────────── */}
      {/* overflow-y-auto here (not on body) keeps scroll contained.         */}
      {/* justify-start + min-h-full lets short steps center while tall      */}
      {/* steps (Goals, etc.) simply extend the scrollable area downward.    */}
      <main className="flex-1 overflow-y-auto">
        <div className="min-h-full flex flex-col items-center justify-start px-4 py-12">
          {/* Inner centering wrapper: centers vertically when content is     */}
          {/* shorter than the viewport, flows naturally when it's taller.   */}
          <div className="w-full flex flex-col items-center justify-center flex-1">
            {children}
          </div>
        </div>
      </main>
    </div>
  )
}
