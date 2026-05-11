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
              <CartesianGrid strokeDasharray="3 3" stroke="#d4bca0" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: "#967259", fontSize: 11, fontFamily: "'IBM Plex Mono'" }}
                tickFormatter={d => d.slice(5)}
              />
              <YAxis tick={{ fill: "#967259", fontSize: 11, fontFamily: "'IBM Plex Mono'" }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ backgroundColor: "#ece0d1", border: "1px solid #c4a88a", borderRadius: "4px" }}
                labelStyle={{ color: "#38220f", fontFamily: "'IBM Plex Mono'", fontSize: 12 }}
                itemStyle={{ color: "#b87018", fontFamily: "'IBM Plex Mono'", fontSize: 12 }}
              />
              <Bar dataKey="brews" fill="#b87018" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )
      }
    </div>
  )
}
