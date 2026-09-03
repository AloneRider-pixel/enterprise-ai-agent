import React, { useState, useEffect } from 'react'
import { api } from '../services/api'

function DocumentUpload() {
  const [documents, setDocuments] = useState([])
  const [uploading, setUploading] = useState(false)
  const [processing, setProcessing] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    loadDocuments()
  }, [])

  const loadDocuments = async () => {
    try {
      const data = await api.listDocuments()
      setDocuments(data.documents || [])
    } catch (err) {
      console.error('Failed to load documents:', err)
    }
  }

  const handleUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    setUploading(true)
    setError('')

    try {
      const result = await api.uploadDocument(file)
      await loadDocuments()
      
      // Auto-ingest after upload
      setProcessing(result.document_id)
      try {
        await api.ingestDocument(result.document_id)
      } catch (err) {
        setError(`Ingestion failed: ${err.message}`)
      }
      setProcessing(null)
      await loadDocuments()
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(false)
    }
  }

  const handleIngest = async (docId) => {
    setProcessing(docId)
    try {
      await api.ingestDocument(docId)
      await loadDocuments()
    } catch (err) {
      setError(`Ingestion failed: ${err.message}`)
    } finally {
      setProcessing(null)
    }
  }

  const handleDelete = async (docId) => {
    if (!confirm('Delete this document and all its chunks?')) return
    try {
      await api.deleteDocument(docId)
      await loadDocuments()
    } catch (err) {
      setError(err.message)
    }
  }

  const getStatusBadge = (status) => {
    const styles = {
      uploaded: 'bg-yellow-100 text-yellow-700',
      processing: 'bg-blue-100 text-blue-700',
      indexed: 'bg-green-100 text-green-700',
      failed: 'bg-red-100 text-red-700',
    }
    return styles[status] || 'bg-gray-100 text-gray-700'
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        {/* Upload Section */}
        <div className="bg-white rounded-xl shadow-sm border p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            📄 Document Management
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Upload documents to add them to the knowledge base. Supported formats: PDF, TXT, DOCX, Markdown.
          </p>

          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-primary-400 transition-colors">
            <input
              type="file"
              id="file-upload"
              onChange={handleUpload}
              accept=".pdf,.txt,.docx,.md"
              className="hidden"
              disabled={uploading}
            />
            <label
              htmlFor="file-upload"
              className="cursor-pointer"
            >
              <div className="text-3xl mb-2">
                {uploading ? '⏳' : '📁'}
              </div>
              <p className="text-sm font-medium text-gray-700">
                {uploading ? 'Uploading & Processing...' : 'Click to upload or drag & drop'}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                PDF, TXT, DOCX, MD up to 50MB
              </p>
            </label>
          </div>

          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
              {error}
            </div>
          )}
        </div>

        {/* Documents List */}
        <div className="bg-white rounded-xl shadow-sm border">
          <div className="px-6 py-4 border-b">
            <h3 className="font-medium text-gray-800">
              Indexed Documents ({documents.length})
            </h3>
          </div>

          {documents.length === 0 ? (
            <div className="p-8 text-center text-gray-400">
              <p>No documents uploaded yet.</p>
              <p className="text-sm mt-1">Upload a document to get started.</p>
            </div>
          ) : (
            <div className="divide-y">
              {documents.map((doc) => (
                <div key={doc.document_id} className="px-6 py-4 flex items-center justify-between hover:bg-gray-50">
                  <div className="flex items-center gap-3">
                    <span className="text-xl">
                      {doc.file_type === 'pdf' ? '📕' : doc.file_type === 'docx' ? '📘' : '📄'}
                    </span>
                    <div>
                      <p className="text-sm font-medium text-gray-800">{doc.filename}</p>
                      <p className="text-xs text-gray-400">
                        {doc.chunk_count} chunks • {new Date(doc.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusBadge(doc.status)}`}>
                      {doc.status}
                    </span>

                    {doc.status === 'uploaded' && (
                      <button
                        onClick={() => handleIngest(doc.document_id)}
                        disabled={processing === doc.document_id}
                        className="px-3 py-1 text-xs bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
                      >
                        {processing === doc.document_id ? 'Processing...' : 'Index'}
                      </button>
                    )}

                    <button
                      onClick={() => handleDelete(doc.document_id)}
                      className="px-3 py-1 text-xs text-red-600 border border-red-200 rounded-md hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default DocumentUpload
