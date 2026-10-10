import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { opsApi } from '@/api/ops'

export function useIndexManifest(spaceId?: string) {
  return useQuery({
    queryKey: ['index', 'manifest', spaceId ?? 'active'],
    queryFn: () => opsApi.getIndexManifest(spaceId),
  })
}

export function useBuildIndex() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (spaceId?: string) => opsApi.buildIndex(spaceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['index'] })
    },
  })
}

export function useRebuildIndex() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (spaceId?: string) => opsApi.rebuildIndex(spaceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['index'] })
    },
  })
}
