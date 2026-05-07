/**
 * SignalsPage — Active Signal Cards
 * Satisfies: Requirements 18.1, 18.10
 */
import { useAlertsStore } from '../store/alertsStore'
import { SignalCard } from '../components/SignalCard'

export function SignalsPage() {
  const signals = useAlertsStore((s) => s.signals)
  const signalList = Object.values(signals)

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold text-white mb-4">
        Active Signals
        {signalList.length > 0 && (
          <span className="ml-2 text-sm bg-green-900/50 text-green-400 px-2 py-0.5 rounded-full">
            {signalList.length}
          </span>
        )}
      </h1>

      {signalList.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <p className="text-4xl mb-3">📡</p>
          <p>Waiting for signals...</p>
          <p className="text-xs mt-1">Alerts will appear here when score ≥ 75</p>
        </div>
      ) : (
        <div className="space-y-4">
          {signalList
            .sort((a, b) => b.final_score - a.final_score)
            .map((signal) => (
              <SignalCard key={signal.signal_id} signal={signal} />
            ))}
        </div>
      )}
    </div>
  )
}
