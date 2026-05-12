import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { workspaceClient } from '@/lib/api/workspaceClient'
import {
  listProjectFilesRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdFilesGet,
  uploadProjectFileRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdFilesPost,
  deleteProjectFileRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdFilesFileIdDelete,
} from '@/generated/workspace-api/sdk.gen'
import { formDataBodySerializer } from '@/generated/workspace-api/client'
import type { ProjectFile } from '@/types'

const FILES_KEY = 'project-files'

// ── Generated SDK wrappers ──

export function useProjectFiles(workspaceId: string | undefined, projectId: string | undefined) {
  return useQuery<{ items: ProjectFile[]; total: number }>({
    queryKey: [FILES_KEY, workspaceId, projectId],
    queryFn: () =>
      listProjectFilesRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdFilesGet({
        client: workspaceClient,
        path: { workspace_id: workspaceId!, project_id: projectId! },
      }).then((res) => res.data as { items: ProjectFile[]; total: number }),
    enabled: !!workspaceId && !!projectId,
  })
}

export function useUploadProjectFile(workspaceId: string | undefined, projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation<ProjectFile, Error, File>({
    mutationFn: async (file) => {
      const res = await uploadProjectFileRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdFilesPost({
        client: workspaceClient,
        path: { workspace_id: workspaceId!, project_id: projectId! },
        body: { file },
        bodySerializer: formDataBodySerializer.bodySerializer,
      })
      return res.data as ProjectFile
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILES_KEY, workspaceId, projectId] })
    },
  })
}

export function useDeleteProjectFile(workspaceId: string | undefined, projectId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (fileId) =>
      deleteProjectFileRouteApiV1WorkspacesWorkspaceIdProjectsProjectIdFilesFileIdDelete({
        client: workspaceClient,
        path: { workspace_id: workspaceId!, project_id: projectId!, file_id: fileId },
      }).then(() => undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [FILES_KEY, workspaceId, projectId] })
    },
  })
}

export function getProjectFileUrl(workspaceId: string, projectId: string, fileId: string): string {
  return `/v1/workspaces/${workspaceId}/projects/${projectId}/files/${fileId}`
}

export function getProjectFileDownloadUrl(workspaceId: string, projectId: string, fileId: string): string {
  return `/v1/workspaces/${workspaceId}/projects/${projectId}/files/${fileId}?download=true`
}
