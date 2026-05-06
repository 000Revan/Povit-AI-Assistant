<template>
  <el-button circle :icon="Microphone" :loading="listening" @click="start" aria-label="语音输入" />
</template>

<script setup>
import { ref } from 'vue'
import { Microphone } from '@element-plus/icons-vue'

const emit = defineEmits(['result'])
const listening = ref(false)

const start = () => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    emit('result', '')
    return
  }
  const recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  listening.value = true
  recognition.onresult = (event) => emit('result', event.results[0][0].transcript)
  recognition.onend = () => {
    listening.value = false
  }
  recognition.start()
}
</script>

