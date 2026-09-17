export interface User {
  id: number
  name: string
  token: string
  total_brews: number
  total_time: number
  last_brew: number | null
}

export interface Brew {
  id: number
  user: string
  started_at: number
  ended_at: number
  duration: number
  kind: string
  shot_type: string | null
  decaf: boolean | null
  rating: number | null
}

export interface OverallStats {
  total_brews: number
  total_users: number
  total_brew_time: number
  today_brews: number
  top_brewer: string | null
  average_duration: number
  average_rating: number | null
  decaf_brews: number
}

export interface DailyStats {
  date: string
  brews: number
  total_duration: number
}

export interface Status {
  state: string
  user: string | null
  session_started_at: number | null
  brew_started_at: number | null
}
