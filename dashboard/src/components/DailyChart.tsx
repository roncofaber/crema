import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from "recharts"
import { api } from "../api"
import { usePolling } from "../hooks/usePolling"
import type { DailyStats } from "../types"

export function DailyChart() {
  const { data } = usePolling(api.dailyStats, 300_000)

  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <h2 className="text-sm text-gray-400 mb-4">Brews per day (last 30 days)</h2>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data ?? []} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            tickFormatter={d => d.slice(5)}
          />
          <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ backgroundColor: "#1f2937", border: "none", borderRadius: "8px" }}
            labelStyle={{ color: "#f3f4f6" }}
            itemStyle={{ color: "#d1d5db" }}
          />
          <Bar dataKey="brews" fill="#f59e0b" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
