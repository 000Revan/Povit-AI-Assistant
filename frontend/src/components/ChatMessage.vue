<template>
  <div class="message-row" :class="message.role">
    <span class="avatar">{{ message.role === 'user' ? 'ME' : 'AI' }}</span>
    <div class="bubble" :class="{ thinking: message.thinking }">
      <span v-if="message.thinking" class="thinking-spinner" aria-hidden="true"></span>
      <span>{{ message.content }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: {
    type: Object,
    required: true,
  },
})
</script>
