export type ChatStatus =
  | 'needs_information'
  | 'ambiguous'
  | 'matched'
  | 'unsupported'

export interface ChatRequest {
  conversation_id?: string
  message: string
}

export interface ChatResponse {
  conversation_id: string
  status: ChatStatus
  reply: string
  diagnosis: string | null
  possible_diagnoses: string[]
  recommended_service: string | null
  safety_guidance: string | null
  matched_rule: string | null
  matched_rules: Array<Record<string, unknown>>
  missing_information: string[]
  next_follow_up_question: string | null
}

export type DiagnosisSource = 'rule' | 'gemini' | 'hybrid'

export interface DiagnosisRequest {
  conversation_id: string
}

export interface DiagnosisResponse {
  conversation_id: string
  diagnosis_id: number | null
  status: ChatStatus
  diagnosis: string | null
  result: Record<string, unknown> | null
  recommended_service: string | null
  safety_guidance: string | null
  source: DiagnosisSource | null
  message: string | null
}

export interface BookingRequest {
  diagnosis_id: number
  conversation_id: string
  customer_name: string
  phone: string
  email: string
  vehicle_make: string
  vehicle_model: string
  vehicle_year: number | null
  preferred_date: string
  preferred_time: string
  service_address: string
}

export type BookingStatus = 'pending' | 'confirmed' | 'cancelled'

export interface BookingResponse extends BookingRequest {
  id: number
  status: BookingStatus
  created_at: string
}

export interface ChatErrorBody {
  error?: {
    code?: string
    message?: string
    fields?: Record<string, string[]>
  }
}

export type AttachmentType = 'image' | 'audio' | 'video'

export interface UploadRequest {
  conversation_id: string
  file: File
}

export interface AttachmentMetadata {
  id: number
  file_type: AttachmentType
  file_size: number
  url: string
  filename: string
}

export interface UploadResponse {
  conversation_id: string
  message_id: number
  attachment: AttachmentMetadata
}
