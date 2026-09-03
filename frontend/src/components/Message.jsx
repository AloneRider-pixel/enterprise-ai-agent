import React from 'react'

function Message({ message }) {
  const isUser = message.role === 'user'
  const isError = message.isError

  return (
    <div className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0 ${
        isUser ? 'bg-gray-200' : 'bg-primary-100'
      }`}>
        {isUser ? '👤' : '🤖'}
      </div>

      {/* Message Content */}
      <div className={`max-w-[80%] ${isUser ? 'text-right' : ''}`}>
        <div className={`inline-block rounded-lg px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-primary-600 text-white'
            : isError
              ? 'bg-red-50 text-red-700 border border-red-200'
              : 'bg-white border border-gray-200 shadow-sm text-gray-800'
        }`}>
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.citations.slice(0, 3).map((cite, i) => (
              <span
                key={i}
                className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700 border border-blue-100"
              >
                📄 Source {cite.source_number || i + 1}
              </span>
            ))}
          </div>
        )}

        {/* Tool Calls */}
        {!isUser && message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.toolCalls.map((tc, i) => (
              <span
                key={i}
                className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-green-50 text-green-700 border border-green-100"
              >
                🔧 {tc.tool}
              </span>
            ))}
          </div>
        )}

        {/* Metadata */}
        {!isUser && message.metadata && message.metadata.latency_ms && (
          <div className="mt-1 text-xs text-gray-400">
            ⏱ {Math.round(message.metadata.latency_ms)}ms
            {message.metadata.retrieval_method && ` • ${message.metadata.retrieval_method} retrieval`}
            {message.metadata.chunks_retrieved > 0 && ` • ${message.metadata.chunks_retrieved} chunks`}
          </div>
        )}
      </div>
    </div>
  )
}

export default Message
