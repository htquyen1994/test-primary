/**
 * JournalPage — Trade Journal
 * Satisfies: Requirement 18.7
 */
import { useEffect, useState } from 'react'
import { JournalTable } from '../components/JournalTable'
import type { TradeJournalEntry } from '../types'

export function JournalPage() {
  const [entries, setEntries] = useState<TradeJournalEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/journal?page=${page}&page_size=20`)
      .then((r) => r.json())
      .then((data) => {
        setEntries(Array.isArray(data) ? data : [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [page])

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold text-white mb-4">Trade Journal</h1>

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : (
        <>
          <JournalTable entries={entries} />
          <div className="flex justify-center gap-3 mt-4">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 text-sm rounded-lg text-gray-300 transition-colors"
            >
              ← Prev
            </button>
            <span className="text-gray-500 text-sm py-1.5">Page {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={entries.length < 20}
              className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-40 text-sm rounded-lg text-gray-300 transition-colors"
            >
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  )
}
