/**
 * API service for communicating with the FastAPI backend.
 */

const API_BASE = '/api'

function getHeaders() {
  const token = localStorage.getItem('token')
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  }
}

export const api = {
  // ─── Auth ───
  async login(email, password) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) throw new Error((await res.json()).detail || 'Login failed')
    return res.json()
  },

  async register(email, password, fullName) {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, full_name: fullName }),
    })
    if (!res.ok) throw new Error((await res.json()).detail || 'Registration failed')
    return res.json()
  },

  async getMe() {
    const res = await fetch(`${API_BASE}/auth/me`, { headers: getHeaders() })
    if (!res.ok) throw new Error('Not authenticated')
    return res.json()
  },

  // ─── Chat ───
  async sendMessage(sessionId, message, stream = true) {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ session_id: sessionId, message, stream }),
    })
    
    if (!res.ok) throw new Error((await res.json()).detail || 'Chat failed')
    
    if (stream) {
      return res // Return the response for SSE streaming
    }
    return res.json()
  },

  async getHistory(sessionId) {
    const res = await fetch(`${API_BASE}/chat/history/${sessionId}`, {
      headers: getHeaders(),
    })
    if (!res.ok) throw new Error('Failed to get history')
    return res.json()
  },

  async clearHistory(sessionId) {
    const res = await fetch(`${API_BASE}/chat/history/${sessionId}`, {
      method: 'DELETE',
      headers: getHeaders(),
    })
    if (!res.ok) throw new Error('Failed to clear history')
    return res.json()
  },

  // ─── Documents ───
  async uploadDocument(file) {
    const formData = new FormData()
    formData.append('file', file)
    
    const res = await fetch(`${API_BASE}/documents/upload`, {
      method: 'POST',
      headers: {
        ...(localStorage.getItem('token') && { Authorization: `Bearer ${localStorage.getItem('token')}` }),
      },
      body: formData,
    })
    if (!res.ok) throw new Error((await res.json()).detail || 'Upload failed')
    return res.json()
  },

  async ingestDocument(documentId) {
    const res = await fetch(`${API_BASE}/documents/ingest/${documentId}`, {
      method: 'POST',
      headers: getHeaders(),
    })
    if (!res.ok) throw new Error((await res.json()).detail || 'Ingestion failed')
    return res.json()
  },

  async listDocuments() {
    const res = await fetch(`${API_BASE}/documents`, { headers: getHeaders() })
    if (!res.ok) throw new Error('Failed to list documents')
    return res.json()
  },

  async deleteDocument(documentId) {
    const res = await fetch(`${API_BASE}/documents/${documentId}`, {
      method: 'DELETE',
      headers: getHeaders(),
    })
    if (!res.ok) throw new Error('Failed to delete document')
    return res.json()
  },

  // ─── Admin ───
  async getMetrics() {
    const res = await fetch(`${API_BASE}/admin/metrics`, { headers: getHeaders() })
    if (!res.ok) throw new Error('Failed to get metrics')
    return res.json()
  },

  async runEvaluation(datasetName = 'default') {
    const res = await fetch(`${API_BASE}/evaluation/run`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ dataset_name: datasetName }),
    })
    if (!res.ok) throw new Error('Evaluation failed')
    return res.json()
  },

  async getHealth() {
    const res = await fetch(`${API_BASE}/health`)
    if (!res.ok) throw new Error('Health check failed')
    return res.json()
  },
}
