import { apiClient } from './client'

export const getKnowledgeFiles = async () => (await apiClient.get('/api/knowledge/files')).data
export const uploadKnowledgeFile = async (file) => {
  const form = new FormData()
  form.append('file', file)
  return (await apiClient.post('/api/knowledge/upload', form)).data
}
export const deleteKnowledgeFile = async (id) => (await apiClient.delete(`/api/knowledge/files/${id}`)).data

