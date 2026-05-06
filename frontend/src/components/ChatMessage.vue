<template>
  <div class="message-row" :class="message.role">
    <span class="avatar">{{ message.role === 'user' ? 'ME' : 'AI' }}</span>
    <div class="bubble">{{ message.content }}</div>
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

