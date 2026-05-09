import React, { useState } from 'react'
import { FileText, X, Download, Eye, ExternalLink } from 'lucide-react'

interface DocumentViewerProps {
  projectId: string
  projectTitle: string
}

interface ProjectDocument {
  id: string
  name: string
  type: 'pdf' | 'docx' | 'txt' | 'other'
  url: string
  uploadedAt: string
}

export function DocumentViewer({ projectId, projectTitle }: DocumentViewerProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [selectedDoc, setSelectedDoc] = useState<ProjectDocument | null>(null)

  // Demo documents — in production these would come from an API
  const demoDocs: ProjectDocument[] = [
    {
      id: '1',
      name: `${projectTitle} - SRS.pdf`,
      type: 'pdf',
      url: '#',
      uploadedAt: new Date().toISOString(),
    },
  ]

  const handleView = (doc: ProjectDocument) => {
    setSelectedDoc(doc)
  }

  const getFileIcon = (type: string) => {
    switch (type) {
      case 'pdf':
        return <span className="text-red-500 font-bold text-xs">PDF</span>
      case 'docx':
        return <span className="text-blue-500 font-bold text-xs">DOCX</span>
      case 'txt':
        return <span className="text-gray-500 font-bold text-xs">TXT</span>
      default:
        return <span className="text-gray-500 font-bold text-xs">FILE</span>
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-2 rounded-lg border border-border bg-white px-4 py-2 text-sm font-semibold text-text hover:bg-surface-alt transition-colors whitespace-nowrap"
      >
        <FileText className="h-4 w-4" /> Documents
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-4xl rounded-xl border border-gray-200 bg-white shadow-xl flex flex-col max-h-[90vh]">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
              <div>
                <h2 className="text-sm font-semibold text-gray-900">Project Documents</h2>
                <p className="text-xs text-gray-500">{projectTitle}</p>
              </div>
              <button
                type="button"
                onClick={() => { setIsOpen(false); setSelectedDoc(null); }}
                className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex flex-1 min-h-0">
              {/* Document List Sidebar */}
              <div className="w-64 border-r border-gray-100 flex flex-col">
                <div className="p-3 border-b border-gray-100">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Documents</p>
                </div>
                <div className="flex-1 overflow-y-auto p-2">
                  {demoDocs.map((doc) => (
                    <button
                      key={doc.id}
                      onClick={() => handleView(doc)}
                      className={`w-full text-left rounded-lg p-2.5 mb-1 transition-colors ${
                        selectedDoc?.id === doc.id
                          ? 'bg-blue-50 border border-blue-200'
                          : 'hover:bg-gray-50 border border-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        {getFileIcon(doc.type)}
                        <span className="text-xs font-medium text-gray-700 truncate">{doc.name}</span>
                      </div>
                    </button>
                  ))}
                  {demoDocs.length === 0 && (
                    <p className="text-xs text-gray-400 text-center py-4">No documents uploaded yet.</p>
                  )}
                </div>
              </div>

              {/* Viewer Area */}
              <div className="flex-1 flex flex-col min-h-0 bg-gray-50">
                {selectedDoc ? (
                  <>
                    <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-white">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900">{selectedDoc.name}</span>
                        <span className="text-xs text-gray-400">{selectedDoc.type.toUpperCase()}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <a
                          href={selectedDoc.url}
                          download
                          className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
                        >
                          <Download className="h-3 w-3" /> Download
                        </a>
                      </div>
                    </div>
                    <div className="flex-1 p-4 overflow-auto">
                      {selectedDoc.type === 'pdf' && (
                        <div className="bg-white rounded-lg border border-gray-200 shadow-sm h-full flex items-center justify-center">
                          <div className="text-center">
                            <FileText className="h-12 w-12 text-gray-300 mx-auto mb-3" />
                            <p className="text-sm text-gray-600 mb-2">PDF Viewer</p>
                            <p className="text-xs text-gray-400 mb-4">Preview not available in this build.</p>
                            <a
                              href={selectedDoc.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-medium text-white hover:bg-blue-700"
                            >
                              <ExternalLink className="h-3 w-3" />
                              Open in New Tab
                            </a>
                          </div>
                        </div>
                      )}
                      {selectedDoc.type === 'docx' && (
                        <div className="bg-white rounded-lg border border-gray-200 shadow-sm h-full flex items-center justify-center">
                          <div className="text-center">
                            <FileText className="h-12 w-12 text-blue-300 mx-auto mb-3" />
                            <p className="text-sm text-gray-600 mb-2">DOCX Document</p>
                            <p className="text-xs text-gray-400 mb-4">Word documents can be downloaded and viewed locally.</p>
                            <a
                              href={selectedDoc.url}
                              download
                              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-medium text-white hover:bg-blue-700"
                            >
                              <Download className="h-3 w-3" />
                              Download Document
                            </a>
                          </div>
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                      <Eye className="h-10 w-10 text-gray-300 mx-auto mb-3" />
                      <p className="text-sm text-gray-500">Select a document to view</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
