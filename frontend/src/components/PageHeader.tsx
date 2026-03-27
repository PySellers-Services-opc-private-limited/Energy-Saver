interface PageHeaderProps {
  title: string
  subtitle?: string
}

export default function PageHeader({ title, subtitle }: PageHeaderProps) {
  return (
    <div className="px-6 py-6 border-b border-gray-800">
      <h1 className="text-xl font-bold text-gray-100">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-gray-400">{subtitle}</p>}
    </div>
  )
}
