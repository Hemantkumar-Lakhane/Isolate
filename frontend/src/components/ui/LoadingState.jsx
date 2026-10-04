import React from 'react'
import { Spinner } from './index'

export function LoadingState({ text = 'Loading...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-14 text-[rgb(var(--text-muted))]">
      <Spinner size="lg" className="mb-4" />
      <p className="text-sm">{text}</p>
    </div>
  )
}
