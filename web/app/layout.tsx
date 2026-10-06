import type { Metadata } from 'next'
import './globals.css'

const siteUrl = 'https://harnessdiff.vercel.app'

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: 'HarnessDiff — See what each agent harness layer fixes',
  description:
    'A hands-on lab that measures how tool design, sandboxing, permissions, retries, and verification turn a fragile agent into a reliable one. Baseline 50% → full harness 83.3%.',
  authors: [{ name: 'Nagaraju Poralla', url: 'https://github.com/Porallanagaraju13' }],
  openGraph: {
    type: 'website',
    url: siteUrl,
    title: 'HarnessDiff — Before vs after harness engineering',
    description:
      'Watch success climb from 50% to 83.3% as each harness layer is added. Built from Understanding Harness Engineering by @techNmak.',
    siteName: 'HarnessDiff',
    images: [
      {
        url: '/og.png',
        width: 1200,
        height: 630,
        alt: 'HarnessDiff: 50% baseline to 83.3% with full harness',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'HarnessDiff — Before vs after harness engineering',
    description: 'Baseline 50% → full harness 83.3%. See what each layer fixes.',
    images: ['/og.png'],
  },
  icons: {
    icon: [{ url: '/favicon.svg', type: 'image/svg+xml' }],
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Outfit:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  )
}
