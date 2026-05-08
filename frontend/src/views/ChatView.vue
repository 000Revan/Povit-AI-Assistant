<template>
  <div class="content-grid chat-grid">
    <SessionList
      :sessions="sessions"
      :active-id="activeSessionId"
      @create="handleCreate"
      @select="selectSession"
      @remove="handleRemove"
    />

    <section class="panel chat-panel">
      <div class="conversation-hero">
        <div>
          <span>当前会话</span>
          <h2>{{ activeTitle }}</h2>
        </div>
        <el-tag effect="light" type="success">在线</el-tag>
      </div>

      <div ref="messageBox" class="messages">
        <ChatMessage
          v-for="message in messages"
          :key="message.id || message.localId || `${message.role}-${message.content}`"
          :message="message"
        />
      </div>

      <form class="composer" @submit.prevent="handleSend">
        <el-input v-model="draft" placeholder="输入消息，或点击右侧麦克风进行语音输入" :disabled="sending" />
        <VoiceInput @result="appendVoiceText" />
        <el-button circle type="primary" :icon="Promotion" :loading="sending" native-type="submit" />
      </form>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion } from '@element-plus/icons-vue'
import { createSession, deleteSession, getMessages, getSessions, streamMessage } from '../api/chat'
import ChatMessage from '../components/ChatMessage.vue'
import SessionList from '../components/SessionList.vue'
import VoiceInput from '../components/VoiceInput.vue'

const sessions = ref([])
const activeSessionId = ref('')
const messages = ref([])
const draft = ref('')
const sending = ref(false)
const messageBox = ref(null)

const activeTitle = computed(() => sessions.value.find((item) => item.id === activeSessionId.value)?.title || '云端知识助手')

const makeLocalId = () => {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const scrollToBottom = async () => {
  await nextTick()
  if (messageBox.value) {
    messageBox.value.scrollTop = messageBox.value.scrollHeight
  }
}

const loadSessions = async () => {
  sessions.value = await getSessions()
  if (!activeSessionId.value && sessions.value.length) {
    await selectSession(sessions.value[0].id)
  }
}

const selectSession = async (id) => {
  activeSessionId.value = id
  messages.value = await getMessages(id)
  if (!messages.value.length) {
    messages.value = [
      {
        localId: makeLocalId(),
        role: 'assistant',
        content: '你好，我是 MultiAI Assistant。你可以在这里选择会话、创建新会话，也可以点击语音按钮开始输入。',
      },
    ]
  }
  await scrollToBottom()
}

const handleCreate = async () => {
  const session = await createSession('新建会话')
  sessions.value.unshift(session)
  await selectSession(session.id)
}

const handleRemove = async (id) => {
  await deleteSession(id)
  if (activeSessionId.value === id) {
    activeSessionId.value = ''
    messages.value = []
  }
  await loadSessions()
}

const handleSend = async () => {
  const text = draft.value.trim()
  if (!text || !activeSessionId.value || sending.value) return

  draft.value = ''
  messages.value.push({ localId: makeLocalId(), role: 'user', content: text })
  messages.value.push({ localId: makeLocalId(), role: 'assistant', content: '助手思考中', thinking: true })
  const assistantIndex = messages.value.length - 1
  sending.value = true
  await scrollToBottom()

  try {
    await streamMessage(activeSessionId.value, text, async (chunk) => {
      if (!chunk) return
      if (messages.value[assistantIndex].thinking) {
        messages.value[assistantIndex].thinking = false
        messages.value[assistantIndex].content = ''
      }
      messages.value[assistantIndex].content += chunk
      await scrollToBottom()
    })
    if (messages.value[assistantIndex]?.thinking) {
      messages.value[assistantIndex].thinking = false
      messages.value[assistantIndex].content = '暂时没有收到有效回复，请稍后再试。'
    }
  } catch (error) {
    messages.value.splice(assistantIndex, 1)
    ElMessage.error(error?.message || '消息发送失败')
  } finally {
    sending.value = false
    await loadSessions()
  }
}

const appendVoiceText = (text) => {
  if (!text) {
    ElMessage.warning('当前浏览器不支持语音输入')
    return
  }
  draft.value = `${draft.value}${text}`
}

onMounted(loadSessions)
</script>
