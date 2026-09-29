import type { ChatErrorBody, ChatRequest, ChatResponse } from './types'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  let response: Response

  try {
    response = await fetch(`${apiBaseUrl}/api/chat/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
  } catch {
    throw new Error('The backend is unreachable. Check that the server is running and try again.')
  }

  const body = (await response.json().catch(() => null)) as ChatResponse | ChatErrorBody | null
  if (!response.ok) {
    const errorBody = body as ChatErrorBody | null
    throw new Error(errorBody?.error?.message ?? `The request failed (${response.status}).`)
  }

  return body as ChatResponse
}
