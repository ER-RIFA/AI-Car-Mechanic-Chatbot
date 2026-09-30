import type { ChatErrorBody, UploadRequest, UploadResponse } from './types'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
const maxUploadSizeMb = Number(import.meta.env.VITE_MAX_UPLOAD_SIZE_MB ?? '10')
export const maxUploadSizeBytes = maxUploadSizeMb * 1024 * 1024

const supportedExtensions = new Set([
  '.jpg', '.jpeg', '.png', '.webp', '.mp3', '.wav', '.ogg', '.mp4', '.mov', '.webm',
])

const supportedMimeTypes = new Set([
  'image/jpeg', 'image/png', 'image/webp', 'audio/mpeg', 'audio/mp3', 'audio/wav',
  'audio/x-wav', 'audio/wave', 'audio/ogg', 'video/mp4', 'video/quicktime',
  'audio/webm', 'video/webm',
])

export function validateMediaFile(file: File): string | undefined {
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!supportedExtensions.has(extension)) {
    return 'Choose a JPG, PNG, WebP, MP3, WAV, OGG, MP4, MOV, or WebM file.'
  }
  if (file.type && !supportedMimeTypes.has(file.type.toLowerCase())) {
    return 'The selected file type does not match a supported image, audio, or video format.'
  }
  if (extension === '.webm' && file.type && !['audio/webm', 'video/webm'].includes(file.type.toLowerCase())) {
    return 'WebM files must be audio/webm or video/webm.'
  }
  if (file.size > maxUploadSizeBytes) {
    return `Files must be ${maxUploadSizeMb} MB or smaller.`
  }
  return undefined
}

export async function uploadMedia({ conversation_id, file }: UploadRequest): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('conversation_id', conversation_id)
  formData.append('file', file)

  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}/upload/`, {
      method: 'POST',
      body: formData,
    })
  } catch {
    throw new Error('The backend is unreachable. Check that the server is running and try again.')
  }

  const body = (await response.json().catch(() => null)) as UploadResponse | ChatErrorBody | null
  if (!response.ok) {
    const errorBody = body as ChatErrorBody | null
    throw new Error(errorBody?.error?.message ?? `The upload failed (${response.status}).`)
  }

  const result = body as UploadResponse
  return {
    ...result,
    attachment: {
      ...result.attachment,
      url: new URL(result.attachment.url, apiBaseUrl || window.location.origin).toString(),
    },
  }
}