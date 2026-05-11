import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from "recharts"
import { api } from "../api"
import { usePolling } from "../hooks/usePolling"
import { SkeletonBlock } from "./Skeleton"

export function DailyChart() {
  const { data } = usePolling(api.dailyStats, 300_000)

  return (
    <div className="bg-surface rounded p-5">
      <h2 className="font-display italic text-muted text-base mb-5">Last 30 days</h2>
      {data == null
        ? <SkeletonBlock className="h-[200px]" />
        : (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#3a2212" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: "#9a7e60", fontSize: 11, fontFamily: "'IBM Plex Mono'" }}
                tickFormatter={d => d.slice(5)}
              />
              <YAxis tick={{ fill: "#9a7e60", fontSize: 11, fontFamily: "'IBM Plex Mono'" }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ backgroundColor: "#301d0c", border: "1px solid #4e3018", borderRadius: "4px" }}
                labelStyle={{ color: "#f0e2c8", fontFamily: "'IBM Plex Mono'", fontSize: 12 }}
                itemStyle={{ color: "#d4920a", fontFamily: "'IBM Plex Mono'", fontSize: 12 }}
              />
              <Bar dataKey="brews" fill="#d4920a" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )
      }
    </div>
  )
}
