// frontend/src/components/common/BrandLogo.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Unified Brand Logo Component for Isolate Platform
// ─────────────────────────────────────────────────────────────────────────────

import React from 'react'

export default function BrandLogo({
  className = 'h-7 w-auto',
  showText = true,
  textClassName = 'text-base font-bold tracking-tight text-slate-900 dark:text-white',
  hideIcon = false
}) {
  return (
    <div className="flex items-center gap-2.5">
      {!hideIcon && (
        <img
          src="/isolatelogo.svg"
          alt="Isolate"
          className={`${className} object-contain rounded shrink-0`}
        />
      )}
      {showText && (
        <span className={textClassName}>
          Isolate
        </span>
      )}
    </div>
  )
}
