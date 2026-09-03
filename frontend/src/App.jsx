import React, { useState } from 'react'
import ChatWindow from './components/ChatWindow'
import DocumentUpload from './components/DocumentUpload'
import Login from './components/Login'
import { api } from './services/api'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('token'))
  const [activeTab, setActiveTab] = useState('chat')

  const handleLogin = (token) => {
    localStorage.setItem('token', token)
    setIsAuthenticated(true)
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    setIsAuthenticated(false)
  }

  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
            <span className="text-white text-lg">🤖</span>
          </div>
          <div>
            <h1 className="text-lg font-semibold text-gray-900">Enterprise AI Agent</h1>
            <p className="text-xs text-gray-500">RAG + LangGraph Support Platform</p>
          </div>
        </div>
        
        {/* Tabs */}
        <nav className="flex gap-1 bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setActiveTab('chat')}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'chat'
                ? 'bg-white text-primary-700 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            💬 Chat
          </button>
          <button
            onClick={() => setActiveTab('documents')}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'documents'
                ? 'bg-white text-primary-700 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            📄 Documents
          </button>
        </nav>

        {/* User Menu */}
        <button
          onClick={handleLogout}
          className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 border border-gray-200 rounded-md hover:bg-gray-50"
        >
          Logout
        </button>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-hidden">
        {activeTab === 'chat' && <ChatWindow />}
        {activeTab === 'documents' && <DocumentUpload />}
      </main>
    </div>
  )
}

export default App
