<template>
  <div class="content-grid knowledge-grid">
    <section class="panel upload-panel">
      <div class="panel-title">
        <span><i></i>文件暂存区</span>
        <el-button size="small" type="primary" plain @click="openPicker">点击上传后入库</el-button>
      </div>

      <input
        ref="fileInput"
        class="hidden-input"
        type="file"
        multiple
        accept=".txt,.pdf,.csv,.doc,.docx,.xls,.xlsx,.md"
        @change="handlePick"
      />

      <div class="drop-zone knowledge-drop" @dragover.prevent @drop.prevent="handleDrop" @click="openPicker">
        <UploadFilled />
        <strong>将 txt、pdf、csv、word、excel 文件放到这里</strong>
      </div>

      <p class="hint">当前后端已完成入库骨架，真实向量化逻辑后续接入 ChromaDB 与 Embedding。</p>

      <div class="upload-row staged-summary">
        <span>{{ pendingFiles.length }} 个文件待上传</span>
        <el-button type="primary" :icon="DocumentAdd" :loading="uploading" @click="uploadAll">上传到向量库</el-button>
      </div>

      <ul class="pending-list">
        <li v-for="file in pendingFiles" :key="`${file.name}-${file.size}`">{{ file.name }}</li>
      </ul>
    </section>

    <section class="panel library-panel vector-panel">
      <div class="stats-row vector-stats">
        <div>
          <span>已存文件</span>
          <strong>{{ summary.total_files }}</strong>
        </div>
        <div>
          <span>向量总数</span>
          <strong>{{ summary.total_vectors }}</strong>
        </div>
        <div>
          <span>排序</span>
          <strong>时间倒序</strong>
        </div>
      </div>

      <div class="knowledge-map" aria-hidden="true">
        <span
          v-for="(node, index) in vectorNodes"
          :key="node.id"
          class="vector-node"
          :class="`node-${(index % 6) + 1}`"
          :style="{
            '--node-color': node.color,
            '--node-size': `${node.size}px`,
            '--node-delay': `${index * 0.38}s`,
          }"
        ></span>
      </div>

      <div class="file-list vector-list">
        <article v-for="file in sortedFiles" :key="file.id" class="file-card vector-item">
          <span class="file-dot file-orb" :style="{ background: getFileColor(file.file_type) }"></span>
          <div>
            <strong>{{ file.filename }}</strong>
            <small>{{ formatFileType(file.file_type) }} · {{ file.chunk_count }} chunks · {{ file.vector_count }} vectors · {{ file.upload_time }}</small>
          </div>
          <el-button text :icon="Delete" @click="removeFile(file.id)" />
        </article>

        <article v-if="!sortedFiles.length" class="empty-vector-card">
          <strong>暂无入库文件</strong>
          <small>上传文件后，右侧地图会按文件类型生成浮动节点。</small>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Delete, DocumentAdd, UploadFilled } from '@element-plus/icons-vue'
import { deleteKnowledgeFile, getKnowledgeFiles, uploadKnowledgeFile } from '../api/knowledge'

const fileInput = ref(null)
const pendingFiles = ref([])
const uploading = ref(false)
const summary = ref({ files: [], total_files: 0, total_vectors: 0 })

const demoNodes = [
  { id: 'demo-word', file_type: 'word', chunk_count: 42, vector_count: 336 },
  { id: 'demo-csv', file_type: 'csv', chunk_count: 24, vector_count: 192 },
  { id: 'demo-pdf', file_type: 'pdf', chunk_count: 31, vector_count: 248 },
]

const sortedFiles = computed(() =>
  [...summary.value.files].sort((a, b) => new Date(b.upload_time) - new Date(a.upload_time)),
)

const vectorNodes = computed(() => {
  const source = sortedFiles.value.length ? sortedFiles.value : demoNodes
  return source.map((file) => ({
    id: `node-${file.id}`,
    color: getFileColor(file.file_type),
    size: getFileNodeSize(file.file_type),
  }))
})

const openPicker = () => fileInput.value?.click()

const appendFiles = (files) => {
  pendingFiles.value = [...pendingFiles.value, ...Array.from(files)]
}

const handlePick = (event) => {
  appendFiles(event.target.files)
  event.target.value = ''
}

const handleDrop = (event) => appendFiles(event.dataTransfer.files)

const loadFiles = async () => {
  summary.value = await getKnowledgeFiles()
}

const uploadAll = async () => {
  if (!pendingFiles.value.length) {
    ElMessage.warning('请先放入要上传的文件')
    return
  }
  uploading.value = true
  try {
    for (const file of pendingFiles.value) {
      await uploadKnowledgeFile(file)
    }
    pendingFiles.value = []
    await loadFiles()
    ElMessage.success('文件已上传到向量库')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

const removeFile = async (id) => {
  await deleteKnowledgeFile(id)
  await loadFiles()
}

const normalizeType = (type = '') => type.toLowerCase().replace('.', '')

const formatFileType = (type = '') => {
  const normalized = normalizeType(type)
  const map = {
    doc: 'Word',
    docx: 'Word',
    word: 'Word',
    xls: 'Excel',
    xlsx: 'Excel',
    excel: 'Excel',
    pdf: 'PDF',
    csv: 'CSV',
    txt: 'TXT',
    md: 'Markdown',
  }
  return map[normalized] || 'File'
}

const getFileColor = (type = '') => {
  const normalized = normalizeType(type)
  const map = {
    doc: '#8f7bff',
    docx: '#8f7bff',
    word: '#8f7bff',
    pdf: '#c7a8ff',
    csv: '#5fcde4',
    txt: '#7ed9ef',
    md: '#92efd5',
    xls: '#70dfb7',
    xlsx: '#70dfb7',
    excel: '#70dfb7',
  }
  return map[normalized] || '#9b88ff'
}

const getFileNodeSize = (type = '') => {
  const normalized = normalizeType(type)
  const map = {
    doc: 68,
    docx: 68,
    word: 68,
    pdf: 58,
    csv: 48,
    txt: 42,
    md: 46,
    xls: 54,
    xlsx: 54,
    excel: 54,
  }
  return map[normalized] || 50
}

onMounted(loadFiles)
</script>
