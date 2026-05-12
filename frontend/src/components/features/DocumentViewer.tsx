import React, { useState, useRef, useCallback, useEffect } from 'react'
import {
  FileText,
  X,
  Download,
  ExternalLink,
  Upload,
  Trash2,
  File,
  FileImage,
  FileSpreadsheet,
  FileCode,
  Loader2,
  AlertCircle,
  ChevronLeft,
} from 'lucide-react'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { api } from '@/lib/api/client'
import {
  useProjectFiles,
  useUploadProjectFile,
  useDeleteProjectFile,
  getProjectFileUrl,
  getProjectFileDownloadUrl,
} from '@/hooks/useProjectFiles'
import type { ProjectFile } from '@/types'

interface DocumentViewerProps {
  projectId: string
  projectTitle: string
}

const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50 MB
const ALLOWED_EXTENSIONS = new Set([
  '.pdf', '.docx', '.doc', '.txt', '.md', '.csv', '.json', '.xlsx', '.xls',
  '.png', '.jpg', '.jpeg', '.webp', '.gif',
])

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1048576).toFixed(1)} MB`
}

function getFileExtension(name: string): string {
  const idx = name.lastIndexOf('.')
  return idx >= 0 ? name.slice(idx).toLowerCase() : ''
}

function FileIcon({ file }: { file: ProjectFile }) {
  const ext = getFileExtension(file.original_name)
  const ct = file.content_type

  if (ct.startsWith('image/')) {
    return <FileImage className="h-5 w-5 text-emerald-500 shrink-0" />
  }
  if (ct === 'application/pdf') {
    return <FileText className="h-5 w-5 text-red-500 shrink-0" />
  }
  if (ext === '.xlsx' || ext === '.xls' || ext === '.csv') {
    return <FileSpreadsheet className="h-5 w-5 text-green-600 shrink-0" />
  }
  if (ext === '.json' || ext === '.md' || ext === '.txt' || ext === '.py' || ext === '.js' || ext === '.ts') {
    return <FileCode className="h-5 w-5 text-blue-500 shrink-0" />
  }
  return <File className="h-5 w-5 text-gray-400 shrink-0" />
}

function FilePreview({ file, workspaceId, projectId }: { file: ProjectFile; workspaceId: string; projectId: string }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)

  useEffect(() => {
    let revoked = false
    setLoading(true)
    setFetchError(null)

    api
      .getBlob(getProjectFileUrl(workspaceId, projectId, file.id))
      .then((blob) => {
        if (revoked) return
        const url = URL.createObjectURL(blob)
        setBlobUrl(url)
        setLoading(false)
      })
      .catch((err) => {
        if (revoked) return
        setFetchError(err instanceof Error ? err.message : 'Failed to load file')
        setLoading(false)
      })

    return () => {
      revoked = true
      if (blobUrl) URL.revokeObjectURL(blobUrl)
    }
  }, [file.id, workspaceId, projectId])

  const ct = file.content_type
  const ext = getFileExtension(file.original_name)

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <Loader2 className="h-8 w-8 animate-spin text-gray-300" />
      </div>
    )
  }

  if (fetchError || !blobUrl) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <AlertCircle className="h-10 w-10 text-red-300 mx-auto mb-3" />
          <p className="text-sm text-red-500 mb-2">{fetchError || 'Failed to load preview'}</p>
          <a
            href={getProjectFileDownloadUrl(workspaceId, projectId, file.id)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Download className="h-4 w-4" />
            Download
          </a>
        </div>
      </div>
    )
  }

  if (ct.startsWith('image/')) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-100 p-4 overflow-auto">
        <img
          src={blobUrl}
          alt={file.original_name}
          className="max-w-full max-h-full rounded-lg shadow-sm object-contain"
        />
      </div>
    )
  }

  if (ct === 'application/pdf') {
    return (
      <div className="flex-1 flex flex-col min-h-0">
        <iframe
          src={blobUrl}
          title={file.original_name}
          className="w-full h-full border-0 rounded-b-lg"
        />
      </div>
    )
  }

  if (ct.startsWith('text/') || ext === '.json' || ext === '.csv') {
    return (
      <div className="flex-1 flex flex-col min-h-0 bg-white">
        <iframe
          src={blobUrl}
          title={file.original_name}
          className="w-full h-full border-0 rounded-b-lg"
          sandbox=""
        />
      </div>
    )
  }

  return (
    <div className="flex-1 flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <File className="h-16 w-16 text-gray-300 mx-auto mb-4" />
        <p className="text-sm text-gray-600 mb-1">{file.original_name}</p>
        <p className="text-xs text-gray-400 mb-4">{formatBytes(file.file_size)}</p>
        <a
          href={getProjectFileDownloadUrl(workspaceId, projectId, file.id)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Download className="h-4 w-4" />
          Download
        </a>
      </div>
    </div>
  )
}

export function DocumentViewer({ projectId, projectTitle }: DocumentViewerProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<ProjectFile | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const ws = useWorkspaceStore((s) => s.currentWorkspace)
  const workspaceId = ws?.id

  const { data, isLoading, error } = useProjectFiles(workspaceId, projectId)
  const uploadMutation = useUploadProjectFile(workspaceId, projectId)
  const deleteMutation = useDeleteProjectFile(workspaceId, projectId)

  const files = data?.items ?? []

  const handleOpen = useCallback(() => {
    setIsOpen(true)
    setSelectedFile(null)
    setUploadError(null)
  }, [])

  const handleClose = useCallback(() => {
    setIsOpen(false)
    setSelectedFile(null)
    setUploadError(null)
  }, [])

  const validateAndUpload = useCallback(
    (fileList: FileList | null) => {
      setUploadError(null)
      if (!fileList || fileList.length === 0) return

      const file = fileList[0]
      const ext = getFileExtension(file.name)

      if (file.size > MAX_FILE_SIZE) {
        setUploadError(`File exceeds ${MAX_FILE_SIZE / (1024 * 1024)} MB limit.`)
        return
      }
      if (!ALLOWED_EXTENSIONS.has(ext)) {
        setUploadError(`File type "${ext}" not allowed.`)
        return
      }

      uploadMutation.mutate(file, {
        onError: (err) => setUploadError(err.message),
        onSuccess: (newFile) => setSelectedFile(newFile),
      })
    },
    [uploadMutation],
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      validateAndUpload(e.dataTransfer.files)
    },
    [validateAndUpload],
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
  }, [])

  const handleDelete = useCallback(
    (fileId: string) => {
      deleteMutation.mutate(fileId, {
        onSuccess: () => {
          if (selectedFile?.id === fileId) setSelectedFile(null)
        },
      })
    },
    [deleteMutation, selectedFile],
  )

  return (
    <>
      <button
        type="button"
        onClick={handleOpen}
        className="flex items-center gap-2 rounded-lg border border-border bg-white px-4 py-2 text-sm font-semibold text-text hover:bg-surface-alt transition-colors whitespace-nowrap"
      >
        <FileText className="h-4 w-4" /> Documents
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-5xl rounded-xl border border-gray-200 bg-white shadow-xl flex flex-col max-h-[90vh]">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3 shrink-0">
              <div className="flex items-center gap-3">
                {selectedFile && (
                  <button
                    type="button"
                    onClick={() => setSelectedFile(null)}
                    className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                    title="Back to file list"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                )}
                <div>
                  <h2 className="text-sm font-semibold text-gray-900">
                    {selectedFile ? selectedFile.original_name : 'Project Documents'}
                  </h2>
                  <p className="text-xs text-gray-500">{projectTitle}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {selectedFile && (
                  <>
                    <a
                      href={getProjectFileDownloadUrl(workspaceId!, projectId, selectedFile.id)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                      title="Download"
                    >
                      <Download className="h-3.5 w-3.5" />
                      Download
                    </a>
                    <a
                      href={getProjectFileUrl(workspaceId!, projectId, selectedFile.id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                      title="Open in new tab"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      Open
                    </a>
                  </>
                )}
                <button
                  type="button"
                  onClick={handleClose}
                  className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Content */}
            {selectedFile ? (
              <div className="flex-1 min-h-0 flex flex-col">
                {workspaceId && (
                  <FilePreview file={selectedFile} workspaceId={workspaceId} projectId={projectId} />
                )}
              </div>
            ) : (
              <div className="flex flex-1 min-h-0">
                {/* Sidebar — File List */}
                <div className="w-72 border-r border-gray-100 flex flex-col">
                  {/* Upload area */}
                  <div
                    className={`m-3 rounded-lg border-2 border-dashed p-4 transition-colors ${
                      dragOver
                        ? 'border-blue-400 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                  >
                    <div className="text-center">
                      <Upload className="h-6 w-6 text-gray-400 mx-auto mb-2" />
                      <p className="text-xs text-gray-600 mb-1">Drag & drop a file here</p>
                      <p className="text-[10px] text-gray-400 mb-2">PDF, DOCX, TXT, images up to 50 MB</p>
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="text-xs font-medium text-blue-600 hover:text-blue-700"
                      >
                        or click to browse
                      </button>
                    </div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      className="hidden"
                      onChange={(e) => validateAndUpload(e.target.files)}
                    />
                  </div>

                  {uploadError && (
                    <div className="mx-3 mb-2 flex items-center gap-1.5 rounded-md bg-red-50 px-2.5 py-1.5 text-xs text-red-600">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                      {uploadError}
                    </div>
                  )}

                  {/* File list */}
                  <div className="flex-1 overflow-y-auto px-3 pb-3">
                    {isLoading ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                      </div>
                    ) : error ? (
                      <div className="text-center py-6">
                        <AlertCircle className="h-8 w-8 text-red-300 mx-auto mb-2" />
                        <p className="text-xs text-red-500">Failed to load files</p>
                      </div>
                    ) : files.length === 0 ? (
                      <div className="text-center py-8">
                        <FileText className="h-10 w-10 text-gray-200 mx-auto mb-2" />
                        <p className="text-xs text-gray-400">No documents yet</p>
                        <p className="text-[10px] text-gray-300 mt-0.5">Upload your first file above</p>
                      </div>
                    ) : (
                      <div className="space-y-1">
                        {files.map((file) => (
                          <div
                            key={file.id}
                            className="group flex items-center gap-2.5 rounded-lg p-2.5 hover:bg-gray-50 cursor-pointer transition-colors"
                            onClick={() => setSelectedFile(file)}
                          >
                            <FileIcon file={file} />
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-gray-700 truncate">
                                {file.original_name}
                              </p>
                              <p className="text-[10px] text-gray-400">
                                {formatBytes(file.file_size)} · {new Date(file.created_at).toLocaleDateString()}
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleDelete(file.id)
                              }}
                              disabled={deleteMutation.isPending}
                              className="opacity-0 group-hover:opacity-100 p-1 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all shrink-0"
                              title="Delete"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Main — Empty state / Preview hint */}
                <div className="flex-1 flex items-center justify-center bg-gray-50">
                  <div className="text-center">
                    <FileText className="h-14 w-14 text-gray-200 mx-auto mb-3" />
                    <p className="text-sm text-gray-500 mb-1">Select a document to preview</p>
                    <p className="text-xs text-gray-400">PDFs, images, and text files open inline</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}
