/**
 * HelpPage — Hướng dẫn sử dụng hệ thống Crypto Trading
 * Giải thích từng màn hình, từng field, và cách dùng.
 */

import { useState } from 'react'

// ---------------------------------------------------------------------------
// Types & helpers
// ---------------------------------------------------------------------------

interface Section {
  id: string
  icon: string
  title: string
}

const SECTIONS: Section[] = [
  { id: 'overview',   icon: '🗺️',  title: 'Tổng quan hệ thống' },
  { id: 'workflow',   icon: '🔄',  title: 'Quy trình sử dụng' },
  { id: 'signals',    icon: '📡',  title: 'Màn hình Signals' },
  { id: 'monitor',    icon: '📊',  title: 'Màn hình Monitor' },
  { id: 'journal',    icon: '📋',  title: 'Màn hình Journal' },
  { id: 'analytics',  icon: '📈',  title: 'Màn hình Analytics' },
  { id: 'logs',       icon: '🔍',  title: 'Màn hình Logs' },
  { id: 'config',     icon: '⚙️',  title: 'Cấu hình hệ thống' },
  { id: 'glossary',   icon: '📖',  title: 'Từ điển thuật ngữ' },
]

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SectionHeader({ icon, title, id }: { icon: string; title: string; id: string }) {
  return (
    <h2 id={id} className="flex items-center gap-2 text-lg font-bold text-white mt-8 mb-4 pt-4
                            border-t border-gray-800 first:border-t-0 first:mt-0 first:pt-0 scroll-mt-20">
      <span className="text-2xl">{icon}</span>
      {title}
    </h2>
  )
}

function FieldTable({ rows }: { rows: { field: string; type?: string; desc: string; example?: string }[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-800 mb-4">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-800/60">
            <th className="text-left py-2 px-3 text-xs text-gray-400 font-medium w-36">Field</th>
            <th className="text-left py-2 px-3 text-xs text-gray-400 font-medium w-24">Loại</th>
            <th className="text-left py-2 px-3 text-xs text-gray-400 font-medium">Ý nghĩa</th>
            <th className="text-left py-2 px-3 text-xs text-gray-400 font-medium w-32">Ví dụ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={`border-t border-gray-800/50 ${i % 2 === 0 ? '' : 'bg-gray-900/30'}`}>
              <td className="py-2 px-3 font-mono text-xs text-blue-300">{r.field}</td>
              <td className="py-2 px-3 text-xs text-gray-500">{r.type ?? '—'}</td>
              <td className="py-2 px-3 text-xs text-gray-300">{r.desc}</td>
              <td className="py-2 px-3 text-xs text-gray-500 font-mono">{r.example ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Callout({ type, children }: { type: 'info' | 'warning' | 'tip'; children: React.ReactNode }) {
  const styles = {
    info:    'bg-blue-900/20 border-blue-800 text-blue-300',
    warning: 'bg-yellow-900/20 border-yellow-800 text-yellow-300',
    tip:     'bg-green-900/20 border-green-800 text-green-300',
  }
  const icons = { info: 'ℹ️', warning: '⚠️', tip: '💡' }
  return (
    <div className={`flex gap-2 border rounded-xl px-4 py-3 mb-4 text-sm ${styles[type]}`}>
      <span className="flex-shrink-0">{icons[type]}</span>
      <div>{children}</div>
    </div>
  )
}

function StepList({ steps }: { steps: string[] }) {
  return (
    <ol className="space-y-2 mb-4">
      {steps.map((s, i) => (
        <li key={i} className="flex gap-3 text-sm text-gray-300">
          <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-700 text-white text-xs
                           flex items-center justify-center font-bold">{i + 1}</span>
          <span className="pt-0.5">{s}</span>
        </li>
      ))}
    </ol>
  )
}

function ScoreBadge({ label, pts, color }: { label: string; pts: string; color: string }) {
  return (
    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${color}`}>
      <span>{label}</span>
      <span className="opacity-70">{pts}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function HelpPage() {
  const [activeSection, setActiveSection] = useState('overview')

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 flex gap-6">

      {/* Sidebar navigation */}
      <aside className="hidden lg:block w-52 flex-shrink-0">
        <div className="sticky top-20 space-y-1">
          <p className="text-xs text-gray-500 uppercase tracking-wider px-3 mb-2">Nội dung</p>
          {SECTIONS.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              onClick={() => setActiveSection(s.id)}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors
                ${activeSection === s.id
                  ? 'bg-blue-600/20 text-blue-400 font-medium'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}`}
            >
              <span>{s.icon}</span>
              <span>{s.title}</span>
            </a>
          ))}
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 min-w-0">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white">📚 Hướng dẫn sử dụng</h1>
          <p className="text-gray-400 mt-1">Crypto Trading System — Semi-Automatic Trading Platform</p>
        </div>

        {/* ── OVERVIEW ── */}
        <SectionHeader id="overview" icon="🗺️" title="Tổng quan hệ thống" />
        <p className="text-sm text-gray-300 mb-4">
          Đây là nền tảng giao dịch crypto <strong className="text-white">bán tự động</strong> — AI tự động
          phân tích thị trường và tạo tín hiệu giao dịch, nhưng <strong className="text-white">trader
          phải xác nhận</strong> trước khi lệnh được đặt. Hệ thống không bao giờ tự đặt lệnh mà không có
          sự đồng ý của bạn.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
          {[
            { icon: '📡', title: 'AI Engine', desc: 'Quét thị trường 24/7, chấm điểm mỗi nến đóng trên 5 module phân tích' },
            { icon: '🖥️', title: 'Dashboard', desc: 'Hiển thị Signal Card khi điểm ≥ 75. Trader xem và quyết định CONFIRM hoặc SKIP' },
            { icon: '⚡', title: 'Execution', desc: 'Sau khi CONFIRM, hệ thống tự đặt lệnh Entry + Stop Loss + Take Profit trên exchange' },
          ].map(({ icon, title, desc }) => (
            <div key={title} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-2xl mb-2">{icon}</div>
              <p className="font-semibold text-white text-sm mb-1">{title}</p>
              <p className="text-xs text-gray-400">{desc}</p>
            </div>
          ))}
        </div>

        <Callout type="info">
          <strong>Chế độ Testnet:</strong> Mặc định hệ thống chạy ở Testnet (giả lập) — lệnh không được đặt
          trên exchange thật. Để giao dịch thực, vào <strong>Config → Exchange</strong> và tắt Testnet.
        </Callout>

        {/* ── WORKFLOW ── */}
        <SectionHeader id="workflow" icon="🔄" title="Quy trình sử dụng hàng ngày" />
        <StepList steps={[
          'Mở Dashboard (/) — chờ Signal Card xuất hiện khi AI phát hiện cơ hội.',
          'Đọc Signal Card: kiểm tra hướng (Long/Short), điểm số, Entry, SL, TP, R:R.',
          'Quyết định CONFIRM (đặt lệnh) hoặc SKIP (bỏ qua). Signal hết hạn sau ~15 nến nếu không action.',
          'Vào Monitor → Live Positions để theo dõi lệnh đang mở, xem unrealized PnL real-time.',
          'Sau khi lệnh đóng (SL hoặc TP hit), kết quả ghi vào Journal và Analytics.',
          'Xem Analytics để đánh giá hiệu suất theo tuần/tháng.',
        ]} />

        <Callout type="warning">
          <strong>Portfolio Heat:</strong> Thanh màu trên header cho biết tổng rủi ro đang mở.
          Khi Heat ≥ 6%, hệ thống tự từ chối Signal mới để bảo vệ vốn.
        </Callout>

        {/* ── SIGNALS ── */}
        <SectionHeader id="signals" icon="📡" title="Màn hình Signals — Trang chủ" />
        <p className="text-sm text-gray-300 mb-4">
          Màn hình chính hiển thị các <strong className="text-white">Signal Card</strong> — mỗi card là một
          cơ hội giao dịch mà AI đã phân tích và cho điểm ≥ 75/100.
        </p>

        <h3 className="text-sm font-semibold text-gray-200 mb-2">📌 Header của Signal Card</h3>
        <FieldTable rows={[
          { field: 'Symbol', type: 'BTC/USDT', desc: 'Cặp tiền tệ được phân tích', example: 'BTC/USDT' },
          { field: 'LONG / SHORT', type: 'Hướng', desc: 'LONG = mua (giá tăng). SHORT = bán (giá giảm)', example: 'LONG' },
          { field: 'Regime', type: 'Trạng thái', desc: 'TRENDING = xu hướng mạnh ✅ | RANGING = dao động | PARABOLIC = cực kỳ biến động ⚠️ | CHOPPY = lộn xộn', example: 'TRENDING' },
          { field: 'Countdown', type: 'Timer', desc: 'Số nến còn lại trước khi signal hết hạn. Mỗi nến 15 phút. Signal hết hạn khi = 0', example: '12 nến (3h)' },
        ]} />

        <h3 className="text-sm font-semibold text-gray-200 mb-2">💰 Mức giá giao dịch</h3>
        <FieldTable rows={[
          { field: 'Entry', type: 'Giá', desc: 'Giá vào lệnh đề xuất = giá đóng nến hiện tại', example: '$45,230' },
          { field: 'Stop Loss', type: 'Giá đỏ', desc: 'Giá cắt lỗ tự động. Khoảng cách SL = ATR(14) × 1.5. Đây là điểm thoát khi trade sai chiều', example: '$44,800' },
          { field: 'TP1', type: 'Giá xanh lá', desc: 'Take Profit 1 = Entry + SL_distance × 2.0. Mục tiêu lợi nhuận đầu tiên', example: '$46,090' },
          { field: 'TP2', type: 'Giá xanh nhạt', desc: 'Take Profit 2 = Entry + SL_distance × 3.0. Mục tiêu lợi nhuận xa hơn', example: '$47,320' },
        ]} />

        <h3 className="text-sm font-semibold text-gray-200 mb-2">⚖️ Risk:Reward</h3>
        <FieldTable rows={[
          { field: 'Gross R:R', type: 'Số', desc: 'Tỷ lệ lợi nhuận/rủi ro TRƯỚC phí. Gross R:R = (TP1 - Entry) / (Entry - SL). Ví dụ 2.0 = nếu thắng lời gấp đôi số thua', example: '2.00' },
          { field: 'Net R:R', type: 'Số', desc: 'Tỷ lệ lợi nhuận/rủi ro SAU phí giao dịch (0.1% taker × 2 lượt). Net R:R < 1.5 → signal bị chặn', example: '1.68' },
        ]} />

        <Callout type="tip">
          Net R:R ≥ 1.5 là ngưỡng tối thiểu để signal được publish. Nếu thị trường quá biến động
          (ATR lớn) và R:R không đạt, hệ thống tự lọc signal đó.
        </Callout>

        <h3 className="text-sm font-semibold text-gray-200 mb-2">🎯 Score Breakdown — 5 module chấm điểm</h3>
        <p className="text-xs text-gray-400 mb-3">Tổng tối đa = 125 điểm raw → normalize về 0–100</p>
        <div className="flex flex-wrap gap-2 mb-4">
          <ScoreBadge label="Order Flow" pts="0–35" color="border-blue-700 text-blue-300" />
          <ScoreBadge label="SMC" pts="0–30" color="border-purple-700 text-purple-300" />
          <ScoreBadge label="VSA" pts="0–30" color="border-orange-700 text-orange-300" />
          <ScoreBadge label="Context" pts="0–15" color="border-cyan-700 text-cyan-300" />
          <ScoreBadge label="Confluence" pts="0–15" color="border-pink-700 text-pink-300" />
        </div>
        <FieldTable rows={[
          { field: 'Order Flow', type: '0–35 pts', desc: 'Đo áp lực mua/bán tổ chức. Delta (dòng tiền) + Bid/Ask stack + Absorption. ⚠️ Cần Order Book feed đang chạy. Hiện tại = 0 nếu OB chưa start', example: '0/35 (OB off)' },
          { field: 'SMC', type: '0–30 pts', desc: 'Smart Money Concepts. CHoCH (đảo chiều xác nhận) +10, Order Block retest +10, FVG midpoint +10. Phân tích dấu vết tổ chức', example: '20/30' },
          { field: 'VSA', type: '0–30 pts', desc: 'Volume Spread Analysis. No Supply (volume pullback thấp) +10, Effort vs Result +10, Entry tại POC (Point of Control) +10', example: '20/30' },
          { field: 'Context', type: '0–15 pts', desc: '1H bias đồng thuận với hướng signal +8, Funding rate neutral (±0.05%) +4, Giá cách xa S/R ≥ 0.5% +3', example: '11/15' },
          { field: 'Confluence', type: '0–15 pts', desc: 'Bonus khi nhiều confluences: OB + Fib 61.8% + FVG = 45 raw → normalize 15 pts. Càng nhiều confluences = điểm bonus càng cao', example: '10/15' },
        ]} />

        <h3 className="text-sm font-semibold text-gray-200 mb-2">🚦 Điểm cuối (Final Score)</h3>
        <div className="grid grid-cols-3 gap-3 mb-4">
          {[
            { range: '≥ 75', label: 'ALERT 🟢', desc: 'Signal Card hiển thị trên Dashboard. Cần action ngay', color: 'border-green-700 bg-green-900/20' },
            { range: '55–74', label: 'WATCH 🟡', desc: 'Chỉ ghi log. Không hiển thị trên Dashboard', color: 'border-yellow-700 bg-yellow-900/20' },
            { range: '< 55', label: 'IGNORE ⚫', desc: 'Tín hiệu yếu, bỏ qua hoàn toàn', color: 'border-gray-700 bg-gray-900/20' },
          ].map((item) => (
            <div key={item.range} className={`border rounded-xl p-3 ${item.color}`}>
              <p className="font-mono text-sm font-bold text-white">{item.range}</p>
              <p className="text-xs font-semibold mt-0.5">{item.label}</p>
              <p className="text-xs text-gray-400 mt-1">{item.desc}</p>
            </div>
          ))}
        </div>

        <Callout type="warning">
          <strong>Tại sao điểm thấp?</strong> Hiện tại Order Book feed chưa chạy → Order Flow = 0/35 →
          điểm bị cap tối đa 60/100. Cần start OrderBookService và DeltaService để đạt ALERT.
        </Callout>

        <h3 className="text-sm font-semibold text-gray-200 mb-2">🔘 Nút hành động</h3>
        <FieldTable rows={[
          { field: 'CONFIRM', type: 'Button xanh', desc: 'Đặt lệnh thật trên exchange. Hệ thống tự tạo Entry + SL + TP1 + TP2. Không thể hoàn tác sau khi xác nhận', example: '' },
          { field: 'SKIP', type: 'Button xám', desc: 'Bỏ qua signal. Có thể nhập lý do (optional). Signal bị remove khỏi Dashboard', example: 'Too risky' },
        ]} />

        {/* ── MONITOR ── */}
        <SectionHeader id="monitor" icon="📊" title="Màn hình Monitor — Theo dõi lệnh" />
        <p className="text-sm text-gray-300 mb-4">
          4 tabs để theo dõi toàn bộ vòng đời của một trade: từ lúc đang chờ khớp lệnh đến khi đóng.
        </p>

        <h3 className="text-sm font-semibold text-gray-200 mb-2">📌 Account Summary Bar</h3>
        <FieldTable rows={[
          { field: 'Balance', type: 'USD', desc: 'Số dư tài khoản (cash)', example: '$10,245' },
          { field: 'Equity', type: 'USD', desc: 'Balance + Unrealized PnL của tất cả lệnh đang mở', example: '$10,180' },
          { field: 'Used Margin', type: 'USD', desc: 'Tổng margin đang bị lock bởi các lệnh mở', example: '$350' },
          { field: 'Realized PnL', type: 'USD', desc: 'Tổng lợi nhuận/thua lỗ đã chốt từ trước đến nay', example: '+$180' },
          { field: 'Fees Paid', type: 'USD', desc: 'Tổng phí giao dịch đã trả', example: '$12.50' },
        ]} />

        <h3 className="text-sm font-semibold text-gray-200 mb-2">Tab 1: Live Positions — Lệnh đang mở</h3>
        <FieldTable rows={[
          { field: 'Symbol', type: '', desc: 'Cặp tiền tệ', example: 'BTC/USDT' },
          { field: 'Direction', type: '', desc: 'LONG (mua) hoặc SHORT (bán)', example: 'LONG' },
          { field: 'Leverage', type: '×N', desc: 'Đòn bẩy đang dùng. Cao hơn = rủi ro cao hơn', example: '5×' },
          { field: 'Entry', type: 'Giá', desc: 'Giá mở lệnh thực tế', example: '$45,232' },
          { field: 'Current', type: 'Giá', desc: 'Giá hiện tại, cập nhật real-time qua WebSocket', example: '$45,580' },
          { field: 'SL', type: 'Giá đỏ', desc: 'Stop Loss — lệnh sẽ tự đóng nếu giá chạm', example: '$44,800' },
          { field: 'TP1', type: 'Giá xanh', desc: 'Take Profit 1 — mục tiêu lợi nhuận đầu', example: '$46,090' },
          { field: 'Unrealized PnL', type: 'USD %', desc: 'Lợi nhuận/thua lỗ chưa chốt. Màu xanh = lời, đỏ = lỗ', example: '+$12.4 (+0.27%)' },
          { field: 'Progress bar', type: 'Bar', desc: '% đường đi từ Entry đến TP1. Đầy = gần TP1', example: '68%' },
        ]} />

        <h3 className="text-sm font-semibold text-gray-200 mb-2">Tab 2: Pending Orders — Lệnh đang chờ</h3>
        <FieldTable rows={[
          { field: 'EXECUTING ⏳', type: 'Status', desc: 'Celery task vừa được dispatch, đang gửi lên exchange. Thường chỉ vài giây', example: '' },
          { field: 'OPEN 🔵', type: 'Status', desc: 'Lệnh SL hoặc TP đã đặt trên exchange, đang chờ giá chạm để fill', example: '' },
          { field: 'FILLED ✅', type: 'Status', desc: 'Lệnh đã được khớp', example: '' },
          { field: 'CANCELLED', type: 'Status', desc: 'Lệnh đã hủy', example: '' },
          { field: 'Cancel button', type: 'Button', desc: 'Chỉ khả dụng khi status = PENDING hoặc OPEN. Hủy lệnh resting (SL/TP)', example: '' },
        ]} />

        <h3 className="text-sm font-semibold text-gray-200 mb-2">Tab 3: Trade History — Lịch sử giao dịch</h3>
        <FieldTable rows={[
          { field: 'Net PnL', type: 'USD', desc: 'Lợi nhuận/thua lỗ ròng sau phí và slippage', example: '+$76.76' },
          { field: 'Result', type: '', desc: 'WIN (TP hit) | LOSS (SL hit) | BE (breakeven)', example: 'WIN TP1_HIT' },
          { field: 'Score', type: '0–100', desc: 'Điểm AI tại thời điểm tạo signal. Để phân tích correlation giữa score và kết quả', example: '80' },
          { field: 'Verdict', type: '', desc: 'Đánh giá chất lượng signal từ Audit Engine: GOOD_SIGNAL | ACCEPTABLE | BAD_SIGNAL', example: 'GOOD_SIGNAL' },
          { field: 'Duration', type: 'Phút', desc: 'Thời gian giữ lệnh (entry → exit)', example: '134m' },
          { field: 'Slippage', type: 'USD', desc: 'Chênh lệch giữa giá dự kiến và giá thực khớp', example: '$1.60' },
        ]} />

        <h3 className="text-sm font-semibold text-gray-200 mb-2">Tab 4: Signal Audit — Phân tích sau sự kiện</h3>
        <FieldTable rows={[
          { field: 'Signal Result', type: '', desc: 'SIGNAL = score ≥ 75, signal card được tạo | NO_SIGNAL = không đạt ngưỡng hoặc bị block', example: 'SIGNAL' },
          { field: 'Block Reason', type: '', desc: 'MTF_BLOCK (xu hướng 4H ngược chiều) | BTC_GUARD (BTC spike) | CB_LOCKED (Circuit Breaker) | REGIME (daily bias)', example: 'MTF_BLOCK' },
          { field: 'MTF Scenario', type: 'A/B/C', desc: 'A = 4H aligned (+10 điểm) | B = 4H ranging (-10 điểm, size×0.5) | C = 4H opposing (BLOCK)', example: 'A' },
          { field: 'Price at T+1/T+4/T+16', type: 'Giá', desc: 'Giá thực tế sau 1, 4, 16 nến kể từ signal. Để đánh giá: nếu confirm thì có lời không?', example: '$45,800' },
          { field: 'Would hit SL/TP1/TP2', type: 'bool', desc: '✓ = giá đã chạm trong audit window | ✗ = không chạm | ? = chưa đủ data', example: 'TP1: ✓' },
          { field: 'MFE %', type: '%', desc: 'Max Favorable Excursion — mức lời tối đa từ entry trong audit window', example: '+2.3%' },
          { field: 'MAE %', type: '%', desc: 'Max Adverse Excursion — mức lỗ tối đa từ entry. Nhỏ hơn = SL placement tốt', example: '-0.8%' },
        ]} />

        {/* ── JOURNAL ── */}
        <SectionHeader id="journal" icon="📋" title="Màn hình Journal — Lịch sử giao dịch" />
        <FieldTable rows={[
          { field: 'Asset', type: '', desc: 'Symbol giao dịch', example: 'BTC/USDT' },
          { field: 'Direction', type: '', desc: 'LONG hoặc SHORT', example: 'LONG' },
          { field: 'Entry Price', type: 'Giá', desc: 'Giá fill thực tế khi vào lệnh (sau slippage)', example: '$45,232' },
          { field: 'Exit Price', type: 'Giá', desc: 'Giá fill khi thoát (SL hoặc TP hit). Null nếu lệnh vẫn đang mở', example: '$46,001' },
          { field: 'Position Size', type: 'USD', desc: 'Số tiền đặt vào lệnh', example: '$100' },
          { field: 'Gross PnL', type: 'USD', desc: 'Lợi nhuận trước khi trừ phí và slippage', example: '+$76.90' },
          { field: 'Net PnL', type: 'USD', desc: 'Lợi nhuận ròng (sau phí + slippage + funding). Đây là con số thực tế', example: '+$76.76' },
          { field: 'Fee', type: 'USD', desc: 'Phí giao dịch (entry + exit). Taker fee 0.1% × 2', example: '$0.093' },
          { field: 'Signal Score', type: '0–100', desc: 'Điểm AI khi signal được tạo', example: '80' },
          { field: 'Testnet', type: 'bool', desc: 'TRUE = lệnh giả lập trên testnet | FALSE = lệnh thật', example: 'false' },
        ]} />

        {/* ── ANALYTICS ── */}
        <SectionHeader id="analytics" icon="📈" title="Màn hình Analytics — Hiệu suất" />
        <FieldTable rows={[
          { field: 'Win Rate', type: '%', desc: 'Tỷ lệ lệnh thắng. ≥ 55% = tốt 🟢 | 45–55% = trung bình 🟡 | < 45% = cần review 🔴', example: '62.5%' },
          { field: 'Profit Factor', type: 'x', desc: 'Tổng lời / Tổng lỗ. ≥ 1.5 = tốt | ≥ 1.0 = hòa | < 1.0 = thua lỗ ổng thể. Vô cực = chưa có lệnh thua', example: '2.15' },
          { field: 'Net Profit', type: 'USD', desc: 'Tổng lợi nhuận tích lũy từ tất cả lệnh đã đóng', example: '+$245.50' },
          { field: 'Max Drawdown', type: '%', desc: 'Mức sụt giảm lớn nhất từ đỉnh equity curve. < 10% = tốt | 10–15% = cảnh báo | > 15% = nguy hiểm', example: '8.5%' },
          { field: 'Sharpe Ratio', type: '', desc: 'Lợi nhuận điều chỉnh theo rủi ro (annualized). ≥ 1.0 = tốt | ≥ 2.0 = xuất sắc | < 0 = chiến lược tệ', example: '1.82' },
          { field: 'Total Trades', type: 'N', desc: 'Số lệnh đã đóng. < 30 = chưa đủ dữ liệu thống kê (kết quả chưa đáng tin)', example: '48' },
        ]} />

        <Callout type="info">
          <strong>Khi nào analytics đáng tin cậy?</strong> Cần ít nhất <strong>30 lệnh</strong> để có ý
          nghĩa thống kê. Với ít lệnh hơn, một vài lệnh thắng/thua lớn có thể làm lệch toàn bộ số liệu.
        </Callout>

        {/* ── LOGS ── */}
        <SectionHeader id="logs" icon="🔍" title="Màn hình Logs — Debug real-time" />
        <p className="text-sm text-gray-300 mb-4">
          Hiển thị toàn bộ quá trình chấm điểm của <strong className="text-white">mỗi nến đóng</strong>,
          bao gồm cả WATCH và IGNORE. Dùng để debug: tại sao signal không đạt ALERT?
        </p>
        <FieldTable rows={[
          { field: 'Symbol / Timeframe', type: '', desc: 'Nến nào vừa đóng và được scoring', example: 'BTC/USDT 15m' },
          { field: 'Regime', type: '', desc: 'Trạng thái thị trường tại thời điểm scoring', example: 'TRENDING ×1.0' },
          { field: 'Classification', type: '', desc: 'ALERT / WATCH / IGNORE — kết quả cuối cùng của scoring cycle này', example: 'WATCH' },
          { field: 'Delta', type: 'Float', desc: 'Cumulative delta của nến vừa đóng. 0 = DeltaService chưa chạy', example: '1,245.3' },
          { field: 'Delta threshold', type: 'Float', desc: 'Ngưỡng dynamic để tính +15 pts Order Flow. = P75(|delta 24h|) × 1.5', example: '2,800' },
          { field: 'OB available', type: 'bool', desc: 'Order Book có data không. false → score bị cap 60', example: 'false ⚠️' },
          { field: 'Conditions met', type: 'List', desc: 'Điều kiện nào đã thỏa mãn để cộng điểm', example: 'CHoCH_ALIGNED, OB_RETEST' },
          { field: 'Conditions missed', type: 'List', desc: 'Điều kiện nào chưa thỏa. Dùng để hiểu tại sao điểm thấp', example: 'NO_DELTA_DATA' },
          { field: 'Why not alert', type: 'Text', desc: 'Giải thích ngắn tại sao không đạt ALERT threshold', example: 'OB unavailable, score capped at 60' },
          { field: 'Filter block', type: 'Text', desc: 'Filter nào đã block signal trước khi scoring. MTF/BTC_GUARD/CB_LOCKED', example: 'MTF_BLOCK: 4H_OPPOSING_TREND' },
        ]} />

        {/* ── CONFIG ── */}
        <SectionHeader id="config" icon="⚙️" title="Cấu hình hệ thống" />

        <h3 className="text-sm font-semibold text-gray-200 mb-2">Exchange Config (/config/exchange)</h3>
        <FieldTable rows={[
          { field: 'Exchange', type: '', desc: 'Sàn giao dịch: Binance, Bybit, Gate.io...', example: 'binance' },
          { field: 'Market Type', type: '', desc: 'futures = hợp đồng tương lai | spot = giao ngay', example: 'futures' },
          { field: 'Testnet', type: 'Toggle', desc: 'BẬT = giả lập, không dùng tiền thật | TẮT = giao dịch thật ⚠️', example: 'ON' },
          { field: 'API Key / Secret', type: 'Encrypted', desc: 'Khóa API từ exchange. Lưu mã hóa AES-256, không hiển thị plaintext', example: '****5678' },
          { field: 'Sizing Mode', type: '', desc: 'fixed_usd = đặt $X cố định mỗi lệnh | risk_pct = risk N% equity mỗi lệnh', example: 'risk_pct' },
          { field: 'Risk % per trade', type: '%', desc: 'Khi mode = risk_pct, đây là % tài khoản risk mỗi lệnh. 2% trên $10k = $200 max loss', example: '2.0%' },
          { field: 'Default Leverage', type: '×N', desc: 'Đòn bẩy mặc định áp dụng cho tất cả symbols', example: '5×' },
        ]} />

        <h3 className="text-sm font-semibold text-gray-200 mb-2">Trading Params (/config/trading)</h3>
        <FieldTable rows={[
          { field: 'Alert threshold', type: '0–100', desc: 'Điểm tối thiểu để tạo Signal Card. Mặc định 75. Tăng = ít signal hơn nhưng chất lượng cao hơn', example: '75' },
          { field: 'ATR SL multiplier', type: 'Float', desc: 'SL distance = ATR(14) × N. 1.5 = SL cách entry 1.5 lần biến động trung bình', example: '1.5' },
          { field: 'TP1 R:R ratio', type: 'Float', desc: 'TP1 = Entry ± SL_dist × N. Mặc định 2.0 = target lời gấp đôi rủi ro', example: '2.0' },
          { field: 'TP2 R:R ratio', type: 'Float', desc: 'TP2 xa hơn TP1. Mặc định 3.0', example: '3.0' },
          { field: 'Min Net R:R', type: 'Float', desc: 'Signal bị loại nếu Net R:R (sau phí) < giá trị này. Mặc định 1.5', example: '1.5' },
          { field: 'Portfolio heat limit', type: '%', desc: 'Tổng rủi ro tối đa đang mở. Vượt ngưỡng = không nhận signal mới. Mặc định 6%', example: '6.0%' },
          { field: 'Max daily loss', type: '%', desc: 'Circuit Breaker Trigger 3: thua lỗ > N% trong ngày → khóa trading đến 00:00 UTC', example: '5.0%' },
        ]} />

        <Callout type="warning">
          <strong>Thay đổi Trading Params</strong> tạo một version mới trong database — version cũ được
          giữ lại để rollback. Hot-reload tự động, không cần restart backend.
        </Callout>

        {/* ── GLOSSARY ── */}
        <SectionHeader id="glossary" icon="📖" title="Từ điển thuật ngữ" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            { term: 'ATR (Average True Range)', desc: 'Chỉ báo đo biến động trung bình trong 14 nến. ATR cao = thị trường biến động nhiều → SL rộng hơn' },
            { term: 'ADX (Average Directional Index)', desc: 'Đo sức mạnh xu hướng (0–100). ADX > 25 = xu hướng mạnh (TRENDING). ADX < 20 = không có xu hướng (CHOPPY)' },
            { term: 'CHoCH (Change of Character)', desc: 'Giá phá vỡ swing high/low gần nhất → tín hiệu đảo chiều xu hướng. CHoCH bullish + 1H bias tăng = điểm SMC tốt' },
            { term: 'Order Block (OB)', desc: 'Vùng giá tổ chức đặt lệnh lớn. Khi giá retest về OB = cơ hội entry tốt. Hệ thống tìm tối đa 3 OB, ưu tiên OB tại Fibonacci 61.8%' },
            { term: 'FVG (Fair Value Gap)', desc: 'Khoảng trống giá trên 3 nến liên tiếp. Thị trường hay quay lại lấp vùng này. Entry tại midpoint FVG = +10 pts SMC' },
            { term: 'POC (Point of Control)', desc: 'Mức giá có volume giao dịch cao nhất trong ngày. Vào lệnh tại POC ±0.3% = +10 pts VSA' },
            { term: 'Delta (Cumulative)', desc: 'Tổng (Buy volume - Sell volume). Delta dương = áp lực mua. Cần DeltaService chạy để có dữ liệu' },
            { term: 'Funding Rate', desc: 'Phí định kỳ giữa Long và Short trong futures perpetual. Neutral (±0.05%) = thị trường cân bằng = +4 pts Context' },
            { term: 'MTF (Multi-Timeframe)', desc: '4H và Daily bias. Scenario A = 4H aligned (+10 pts). Scenario B = 4H ranging (-10 pts, size×0.5). Scenario C = 4H opposing → BLOCK' },
            { term: 'Circuit Breaker', desc: 'Tự động khóa trading khi: 3 thua liên tiếp (12h) | Thua > 4% equity (6h) | Thua > 5%/ngày | Drawdown > 10% từ đỉnh 7 ngày' },
            { term: 'Portfolio Heat', desc: 'Tổng % risk của tất cả lệnh đang mở. Heat 4% = đang risk $400 trên tài khoản $10k. Giới hạn 6%' },
            { term: 'Slippage', desc: 'Chênh lệch giữa giá dự kiến và giá thực khớp. Xảy ra do thanh khoản không đủ hoặc thị trường di chuyển nhanh' },
            { term: 'Regime', desc: 'Trạng thái thị trường: TRENDING (×1.0) = tốt nhất | RANGING (×0.85) | CHOPPY (×0.85) | PARABOLIC (×0.6, block Short)' },
            { term: 'Confluence', desc: 'Nhiều phương pháp phân tích cùng chỉ ra 1 điểm vào lệnh. OB + Fib 61.8% + FVG = confluence mạnh nhất = +15 pts bonus' },
            { term: 'Testnet', desc: 'Môi trường giả lập của exchange. Mọi lệnh đều fake, không mất tiền thật. Bật khi đang test hệ thống' },
            { term: 'R:R (Risk:Reward)', desc: 'Tỷ lệ lợi nhuận/rủi ro. R:R 2.0 = nếu thắng lời $200, nếu thua lỗ $100. Gross = trước phí, Net = sau phí' },
          ].map(({ term, desc }) => (
            <div key={term} className="bg-gray-900 border border-gray-800 rounded-xl p-3">
              <p className="text-sm font-semibold text-blue-300 mb-1">{term}</p>
              <p className="text-xs text-gray-400">{desc}</p>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="mt-10 pt-6 border-t border-gray-800 text-center text-xs text-gray-600">
          Crypto Trading System — Semi-Automatic Trading Platform v2.0 (Phase 9)
        </div>
      </main>
    </div>
  )
}
