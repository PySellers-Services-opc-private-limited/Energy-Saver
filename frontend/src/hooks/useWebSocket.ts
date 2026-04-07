/**
 * WebSocket hook – connects to /ws/stream and returns the latest reading.
 */

import { useEffect, useRef, useState } from 'react'
import type { LiveReading } from '../api/types'

interface UseWebSocketResult {
  reading: LiveReading | null
  connected: boolean
  history: LiveReading[]
}

export function useWebSocket(maxHistory = 60): UseWebSocketResult {
  const [reading, setReading] = useState<LiveReading | null>(null)
  const [connected, setConnected] = useState(false)
  const [history, setHistory] = useState<LiveReading[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    function connect() {
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${protocol}://${window.location.host}/ws/stream`)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)

      ws.onmessage = (event) => {
        try {
          const data: LiveReading = JSON.parse(event.data as string)
          setReading(data)
          setHistory((prev) => {
            const next = [...prev, data]
            return next.length > maxHistory ? next.slice(next.length - maxHistory) : next
          })
        } catch {
          // ignore malformed messages
        }
      }

      ws.onerror = () => ws.close()

      ws.onclose = () => {
        setConnected(false)
        // Reconnect after 3 s
        setTimeout(connect, 3000)
      }
    }

    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [maxHistory])

  return { reading, connected, history }
}
