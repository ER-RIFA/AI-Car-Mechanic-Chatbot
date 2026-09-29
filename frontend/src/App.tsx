import { useState } from 'react'
import type { FormEvent } from 'react'
import { sendChatMessage } from './api/chatApi'
import type { ChatStatus } from './api/types'

type Message = {
  id: number
  role: 'user' | 'assistant'
  content: string
  status?: ChatStatus
}

const statusLabels: Record<ChatStatus, string> = {
  needs_information: 'More detail needed',
  ambiguous: 'Needs clarification',
  matched: 'Possible match',
  unsupported: 'Outside my scope',
}

const initialMessage: Message = {
  id: 0,
  role: 'assistant',
  content: 'Tell me what your vehicle is doing, and I will help you think through the next useful detail.',
}

function App() {
  const [messages, setMessages] = useState<Message[]>([initialMessage])
  const [conversationId, setConversationId] = useState<string>()
  const [draft, setDraft] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string>()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const message = draft.trim()
    if (!message || isSubmitting) return

    setMessages((current) => [...current, { id: Date.now(), role: 'user', content: message }])
    setDraft('')
    setError(undefined)
    setIsSubmitting(true)

    try {
      const response = await sendChatMessage({
        ...(conversationId ? { conversation_id: conversationId } : {}),
        message,
      })
      setConversationId(response.conversation_id)
      setMessages((current) => [...current, {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.reply,
        status: response.status,
      }])
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'The assistant could not respond. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#f3f1ec] px-4 py-5 text-[#17221f] sm:px-8 sm:py-8">
      <div className="mx-auto flex min-h-[calc(100vh-2.5rem)] max-w-6xl flex-col overflow-hidden rounded-[2rem] border border-[#d9d5cc] bg-[#fbfaf7] shadow-[0_24px_80px_rgba(34,43,39,0.12)] sm:min-h-[calc(100vh-4rem)] lg:flex-row">
        <aside className="flex shrink-0 flex-col justify-between bg-[#163b36] p-6 text-[#f5f0e7] sm:p-8 lg:w-[31%] lg:p-10">
          <div>
            <div className="mb-16 flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#e9a44b] text-lg font-bold text-[#163b36]">+</span>
              <span className="text-sm font-bold uppercase tracking-[0.2em]">Motive AI</span>
            </div>
            <p className="mb-4 text-xs font-bold uppercase tracking-[0.18em] text-[#e9a44b]">Virtual mechanic</p>
            <h1 className="max-w-sm text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl">A clearer next step for your car.</h1>
            <p className="mt-6 max-w-sm text-base leading-7 text-[#c7d4cc]">Describe a symptom in plain language. I can help you organize what to check and what detail matters next.</p>
          </div>
          <div className="mt-12 border-t border-[#52716a] pt-5 text-sm leading-6 text-[#c7d4cc]">
            <p className="font-semibold text-[#f5f0e7]">Safety first</p>
            <p className="mt-1">This is an AI assistant, not a substitute for a trained technician. Stop driving and seek professional help if the vehicle feels unsafe.</p>
          </div>
        </aside>

        <section className="flex min-h-0 flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-[#e5e1d8] px-5 py-5 sm:px-8">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#718078]">Your conversation</p>
              <h2 className="mt-1 text-xl font-semibold tracking-tight">Ask the garage</h2>
            </div>
            <span className="flex items-center gap-2 text-xs font-semibold text-[#718078]"><span className="h-2 w-2 rounded-full bg-[#4eaa72]" />Online</span>
          </header>

          <div className="flex-1 space-y-5 overflow-y-auto px-5 py-6 sm:px-8 sm:py-8" aria-live="polite">
            {messages.map((message) => (
              <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={message.role === 'user' ? 'max-w-[85%] rounded-2xl rounded-br-md bg-[#e9a44b] px-4 py-3 text-[#17221f] sm:max-w-[70%]' : 'max-w-[90%] rounded-2xl rounded-bl-md border border-[#e3dfd6] bg-white px-4 py-3 text-[#30403a] shadow-sm sm:max-w-[75%]'}>
                  {message.status && <p className="mb-2 text-xs font-bold uppercase tracking-[0.12em] text-[#718078]">{statusLabels[message.status]}</p>}
                  <p className="whitespace-pre-wrap text-[0.95rem] leading-7">{message.content}</p>
                </div>
              </div>
            ))}
            {isSubmitting && <div className="flex justify-start"><div className="rounded-2xl rounded-bl-md border border-[#e3dfd6] bg-white px-4 py-4 shadow-sm"><div className="flex items-center gap-1.5" aria-label="Assistant is typing"><span className="typing-dot" /><span className="typing-dot [animation-delay:120ms]" /><span className="typing-dot [animation-delay:240ms]" /></div></div></div>}
            {error && <div role="alert" className="rounded-xl border border-[#e2b7a8] bg-[#fff4ef] px-4 py-3 text-sm leading-6 text-[#8d4939]">{error}</div>}
          </div>

          <form onSubmit={handleSubmit} className="border-t border-[#e5e1d8] bg-[#f7f5f0] p-4 sm:p-6">
            <label htmlFor="message" className="sr-only">Describe your car problem</label>
            <div className="flex items-end gap-3 rounded-2xl border border-[#d9d5cc] bg-white p-2 pl-4 shadow-sm focus-within:border-[#4e8a7b] focus-within:ring-2 focus-within:ring-[#4e8a7b]/20">
              <textarea id="message" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="What is your car doing?" rows={1} disabled={isSubmitting} className="max-h-32 min-h-11 flex-1 resize-none bg-transparent py-2 text-sm leading-6 text-[#17221f] outline-none placeholder:text-[#9aa39e]" onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }} />
              <button type="submit" disabled={isSubmitting || !draft.trim()} className="flex h-11 shrink-0 items-center justify-center rounded-xl bg-[#163b36] px-4 text-sm font-bold text-white transition hover:bg-[#25554d] disabled:cursor-not-allowed disabled:opacity-40">{isSubmitting ? 'Sending' : 'Send'}</button>
            </div>
            <p className="mt-3 text-center text-xs text-[#8a938d]">Do not use this chat for emergencies or immediate safety concerns.</p>
          </form>
        </section>
      </div>
    </main>
  )
}

export default App
