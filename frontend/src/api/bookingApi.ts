import type { BookingRequest, BookingResponse, ChatErrorBody } from './types'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

async function parseResponse<T>(response: Response, fallback: string): Promise<T> {
  const body = (await response.json().catch(() => null)) as T | ChatErrorBody | null
  if (!response.ok) {
    const errorBody = body as ChatErrorBody | null
    throw new Error(errorBody?.error?.message ?? `${fallback} (${response.status}).`)
  }
  return body as T
}

export async function createBooking(request: BookingRequest): Promise<BookingResponse> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}/api/booking/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
  } catch {
    throw new Error('The backend is unreachable. Check that the server is running and try again.')
  }
  return parseResponse<BookingResponse>(response, 'The booking could not be created')
}

export async function getBooking(bookingId: number): Promise<BookingResponse> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}/api/booking/${bookingId}/`)
  } catch {
    throw new Error('The backend is unreachable. Check that the server is running and try again.')
  }
  return parseResponse<BookingResponse>(response, 'The booking could not be loaded')
}