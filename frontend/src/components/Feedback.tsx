export function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="w-8 h-8 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="mx-6 mt-6 rounded-lg bg-red-900/30 border border-red-800 px-4 py-3 text-sm text-red-300">
      ⚠ {message}
    </div>
  )
}
