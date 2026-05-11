import { StatusBadge } from "./components/StatusBadge"

export default function App() {
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">CREMA</h1>
        <StatusBadge />
      </header>
      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        <p className="text-gray-500 text-sm">Components loading...</p>
      </main>
    </div>
  )
}
