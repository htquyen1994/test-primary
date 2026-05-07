/**
 * PortfolioHeader
 * Persistent header showing Portfolio_Heat and per-asset correlated group risk.
 *
 * Satisfies: Requirements 18.9, 14.8
 */
import { usePortfolioStore } from '../store/portfolioStore'

export function PortfolioHeader() {
  const { portfolio_heat, open_positions } = usePortfolioStore()

  const heatColor =
    portfolio_heat >= 5 ? 'text-red-400' :
    portfolio_heat >= 3 ? 'text-yellow-400' :
    'text-green-400'

  return (
    <header className="sticky top-0 z-50 bg-gray-900/95 backdrop-blur border-b border-gray-800 px-4 py-2">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-white font-bold text-sm">🔥 Portfolio Heat</span>
          <span className={`font-mono font-bold ${heatColor}`}>
            {portfolio_heat.toFixed(2)}%
          </span>
          <div className="w-24 bg-gray-800 rounded-full h-1.5 ml-1">
            <div
              className={`h-1.5 rounded-full transition-all ${
                portfolio_heat >= 5 ? 'bg-red-500' :
                portfolio_heat >= 3 ? 'bg-yellow-500' : 'bg-green-500'
              }`}
              style={{ width: `${Math.min((portfolio_heat / 6) * 100, 100)}%` }}
            />
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs text-gray-400">
          {Object.entries(open_positions).map(([asset, risk]) => (
            <span key={asset} className="bg-gray-800 px-2 py-0.5 rounded">
              {asset}: <span className="text-white">{(risk * 100).toFixed(1)}%</span>
            </span>
          ))}
          {Object.keys(open_positions).length === 0 && (
            <span className="text-gray-600">No open positions</span>
          )}
        </div>

        <nav className="flex gap-4 text-sm">
          <a href="/" className="text-gray-300 hover:text-white transition-colors">Signals</a>
          <a href="/journal" className="text-gray-300 hover:text-white transition-colors">Journal</a>
          <a href="/analytics" className="text-gray-300 hover:text-white transition-colors">Analytics</a>
          <span className="text-gray-700">|</span>
          <a href="/config/exchange" className="text-gray-400 hover:text-white transition-colors text-xs">Exchange</a>
          <a href="/config/trading" className="text-gray-400 hover:text-white transition-colors text-xs">Params</a>
        </nav>
      </div>
    </header>
  )
}
