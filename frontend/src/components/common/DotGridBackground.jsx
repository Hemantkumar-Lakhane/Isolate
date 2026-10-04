// frontend/src/components/common/DotGridBackground.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Reusable Subtle Dot-Grid Background Component for SMBFlow.
// Works seamlessly in both Light and Dark themes using CSS background patterns.
// Used selectively for:
// - Integration Marketplace header / hero zone
// - Workflow builder / execution surfaces
// - Empty states & AI Assistant backdrop
// ─────────────────────────────────────────────────────────────────────────────

import React from 'react'

export default function DotGridBackground({
  children,
  className = '',
  dotColor = 'rgba(108, 99, 255, 0.08)',
  dotSize = '1.5px',
  gridSpacing = '24px',
}) {
  return (
    <div
      className={`relative overflow-hidden ${className}`}
      style={{
        backgroundImage: `radial-gradient(${dotColor} ${dotSize}, transparent ${dotSize})`,
        backgroundSize: `${gridSpacing} ${gridSpacing}`,
      }}
    >
      {children}
    </div>
  )
}
