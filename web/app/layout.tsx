import './globals.css'

export const metadata = {
  title: 'HarnessDiff - Agent Harness Lab',
  description: 'See exactly what each harness layer fixes',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
