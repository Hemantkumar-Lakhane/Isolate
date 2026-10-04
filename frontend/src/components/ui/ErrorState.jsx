import React from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from './index'

export function ErrorState({ title = 'Error', description, action, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-14 text-center">
      <div className="w-14 h-14 rounded-2xl bg-danger/10 flex items-center justify-center mb-4 text-danger">
        <AlertTriangle className="w-7 h-7" />
      </div>
      <p className="text-sm font-semibold text-[rgb(var(--text-primary))] mb-1">{title}</p>
      {description && <p className="text-xs text-[rgb(var(--text-muted))] mb-4 max-w-xs leading-relaxed">{description}</p>}
      {action ? action : onRetry && (
        <Button onClick={onRetry} variant="secondary" size="sm">
          Retry
        </Button>
      )}
    </div>
  )
}
