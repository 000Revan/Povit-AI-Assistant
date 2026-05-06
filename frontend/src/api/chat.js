import { apiClient } from './client'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export const getSessions = async () => (await apiClient.get('/api/sessions')).data
export const createSession = async (title = '新会话') => (await apiClient.post('/api/sessions', { title })).data
export const deleteSession = async (id) => (await apiClient.delete(`/api/sessions/${id}`)).data
export const getMessages = async (id) => (await apiClient.get(`/api/sessions/${id}/messages`)).data
export const sendMessage = async (sessionId, message) =>
  (await apiClient.post('/api/chat', { session_id: sessionId, message })).data

export const streamMessage = async (sessionId, message, onChunk) => {
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ session_id: sessionId, message, stream: true }),
  })

  if (!response.ok || !response.body) {
    const detail = await response.text()
    throw new Error(detail || '消息发送失败')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    onChunk(decoder.decode(value, { stream: true }))
  }

  const rest = decoder.decode()
  if (rest) onChunk(rest)
}
