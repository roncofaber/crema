import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from "recharts"
import { api } from "../api"
import { usePolling } from "../hooks/usePolling"

export function DailyChart() {
  const { data } = usePolling(api.dailyStats, 300_000)

  return (
    <div className="bg-espresso-800 rounded p-5">
      <h2 className="font-display italic text-parchment-600 text-base mb-5">Last 30 days</h2>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data ?? []} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#281a0e" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: "#8a7868", fontSize: 11, fontFamily: "'IBM Plex Mono'" }}
            tickFormatter={d => d.slice(5)}
          />
          <YAxis tick={{ fill: "#8a7868", fontSize: 11, fontFamily: "'IBM Plex Mono'" }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ backgroundColor: "#1c1209", border: "1px solid #3a2614", borderRadius: "4px" }}
            labelStyle={{ color: "#f2e8d5", fontFamily: "'IBM Plex Mono'", fontSize: 12 }}
            itemStyle={{ color: "#dfa040", fontFamily: "'IBM Plex Mono'", fontSize: 12 }}
          />
          <Bar dataKey="brews" fill="#c4882a" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
