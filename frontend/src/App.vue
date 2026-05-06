<template>
  <main class="app-shell">
    <div class="cloud cloud-a"></div>
    <div class="cloud cloud-b"></div>
    <aside class="rail">
      <RouterLink class="brand-mark" to="/chat" aria-label="首页">
        <Connection />
      </RouterLink>
      <RouterLink class="rail-button" to="/chat" aria-label="聊天">
        <ChatRound />
      </RouterLink>
      <RouterLink class="rail-button" to="/knowledge" aria-label="向量库">
        <Folder />
      </RouterLink>
    </aside>
    <section class="workspace">
      <header class="topbar">
        <div>
          <p class="eyebrow">Pivot AI ASSISTANT</p>
          <h1>灵枢智能助手</h1>
        </div>
        <nav class="mode-tabs" aria-label="页面切换">
          <RouterLink to="/chat">聊天</RouterLink>
          <RouterLink to="/knowledge">向量库</RouterLink>
        </nav>
      </header>
      <RouterView />
    </section>
  </main>
</template>

<script setup>
import { ChatRound, Connection, Folder } from '@element-plus/icons-vue'
</script>
