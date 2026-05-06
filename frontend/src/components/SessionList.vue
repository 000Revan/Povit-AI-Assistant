<template>
  <section class="panel session-panel">
    <div class="panel-title">
      <span><i></i>会话</span>
      <el-button circle type="primary" :icon="Plus" @click="$emit('create')" />
    </div>
    <div class="session-list">
      <button
        v-for="session in sessions"
        :key="session.id"
        class="session-item"
        :class="{ active: session.id === activeId }"
        @click="$emit('select', session.id)"
      >
        <strong>{{ session.title }}</strong>
        <small>{{ formatTime(session.created_at) }}</small>
        <el-button text :icon="Delete" @click.stop="$emit('remove', session.id)" />
      </button>
    </div>
  </section>
</template>

<script setup>
import { Delete, Plus } from '@element-plus/icons-vue'

defineProps({
  sessions: { type: Array, default: () => [] },
  activeId: { type: String, default: '' },
})

defineEmits(['create', 'select', 'remove'])

const formatTime = (value) => (value ? value.slice(11, 16) : '')
</script>

