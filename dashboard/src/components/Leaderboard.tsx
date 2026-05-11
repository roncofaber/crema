import { useEffect, useState } from "react"
import { api } from "../api"
import type { User } from "../types"

function fmt(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return h ? `${h}h ${m}m` : `${m}m`
}

function fmtDate(ts: number | null): string {
  if (!ts) return "-"
  return new Date(ts * 1000).toLocaleDateString()
}

export function Leaderboard() {
  const [users, setUsers] = useState<User[]>([])
  useEffect(() => { api.users().then(setUsers).catch(() => {}) }, [])

  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-gray-400 border-b border-gray-700">
            <th className="text-left px-4 py-3">#</th>
            <th className="text-left px-4 py-3">Name</th>
            <th className="text-right px-4 py-3">Brews</th>
            <th className="text-right px-4 py-3">Time</th>
            <th className="text-right px-4 py-3">Last brew</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u, i) => (
            <tr key={u.id} className="border-b border-gray-700 last:border-0 hover:bg-gray-750">
              <td className="px-4 py-3 text-gray-500">{i + 1}</td>
              <td className="px-4 py-3 font-medium">{u.name}</td>
              <td className="px-4 py-3 text-right">{u.total_brews}</td>
              <td className="px-4 py-3 text-right text-gray-300">{fmt(u.total_time)}</td>
              <td className="px-4 py-3 text-right text-gray-400">{fmtDate(u.last_brew)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
