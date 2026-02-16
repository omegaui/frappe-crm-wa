<template>
  <LayoutHeader>
    <template #left-header>
      <ViewBreadcrumbs routeName="Chats" />
    </template>
    <template #right-header>
      <Button
        variant="solid"
        :label="__('New Chat')"
        @click="showNewChatDialog = true"
      >
        <template #prefix><FeatherIcon name="plus" class="h-4" /></template>
      </Button>
    </template>
  </LayoutHeader>
  <div class="flex flex-1 overflow-hidden">
    <!-- Left Panel: Conversation List -->
    <div class="flex w-80 flex-shrink-0 flex-col overflow-hidden border-r">
      <div class="p-3">
        <TextInput
          v-model="searchQuery"
          type="text"
          :placeholder="__('Search chats...')"
          :debounce="300"
        >
          <template #prefix>
            <FeatherIcon name="search" class="h-4 w-4 text-ink-gray-4" />
          </template>
        </TextInput>
      </div>
      <div class="flex-1 overflow-y-auto">
        <div
          v-if="chatList.loading && !chatList.data?.length"
          class="flex items-center justify-center py-10"
        >
          <LoadingIndicator class="h-5 w-5" />
        </div>
        <div
          v-else-if="!filteredChats.length"
          class="flex flex-col items-center justify-center py-10 text-sm text-ink-gray-4"
        >
          <FeatherIcon name="message-circle" class="mb-2 h-8 w-8" />
          <span>{{ __('No conversations yet') }}</span>
        </div>
        <div
          v-for="chat in filteredChats"
          :key="chat.jid"
          class="flex cursor-pointer items-center gap-3 px-3 py-2.5 transition-colors hover:bg-surface-gray-2"
          :class="{
            'bg-surface-gray-2': selectedJid === chat.jid,
          }"
          @click="selectChat(chat)"
        >
          <div
            class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-surface-gray-3 text-ink-gray-5"
          >
            <FeatherIcon name="user" class="h-5 w-5" />
          </div>
          <div class="flex-1 overflow-hidden">
            <div class="flex items-center justify-between">
              <span class="truncate text-sm font-medium text-ink-gray-9">
                {{ chat.contact_name || chat.phone || __('Unknown') }}
              </span>
              <span class="flex-shrink-0 text-2xs text-ink-gray-4">
                {{ formatTime(chat.last_message_time) }}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span class="truncate text-xs text-ink-gray-5">
                {{ chat.last_message || chat.phone }}
              </span>
              <span
                v-if="unreadJids.has(chat.jid)"
                class="ml-1 h-2.5 w-2.5 flex-shrink-0 rounded-full bg-green-500"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right Panel: Chat Thread -->
    <div class="flex flex-1 flex-col overflow-hidden">
      <template v-if="selectedJid">
        <!-- Chat Header -->
        <div class="flex items-center gap-3 border-b px-4 py-2.5">
          <div
            class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-surface-gray-3 text-ink-gray-5"
          >
            <FeatherIcon name="user" class="h-4 w-4" />
          </div>
          <div class="flex-1">
            <div class="text-sm font-medium text-ink-gray-9">
              {{ selectedChat?.contact_name || selectedChat?.phone || __('Unknown') }}
            </div>
            <div v-if="selectedChat?.phone" class="text-xs text-ink-gray-4">
              {{ selectedChat?.phone }}
            </div>
          </div>
          <template v-if="!selectedChat?.is_group">
            <router-link
              v-if="linkedDoc"
              :to="linkedDoc.doctype === 'CRM Lead'
                ? { name: 'Lead', params: { leadId: linkedDoc.name } }
                : { name: 'Deal', params: { dealId: linkedDoc.name } }
              "
              class="flex items-center gap-1.5 rounded-md bg-surface-gray-2 px-2.5 py-1.5 text-xs font-medium text-ink-gray-7 hover:bg-surface-gray-3"
            >
              <FeatherIcon name="external-link" class="h-3.5 w-3.5" />
              {{ linkedDoc.doctype === 'CRM Lead' ? __('View Lead') : __('View Deal') }}
            </router-link>
            <Button
              v-else
              variant="subtle"
              size="sm"
              :label="__('Convert to Lead')"
              :loading="convertingToLead"
              @click="convertToLead"
            >
              <template #prefix>
                <FeatherIcon name="user-plus" class="h-3.5 w-3.5" />
              </template>
            </Button>
          </template>
        </div>

        <!-- Messages Area -->
        <div
          ref="messagesContainer"
          class="flex flex-1 flex-col overflow-y-auto px-3 py-4 sm:px-10"
        >
          <div
            v-if="chatMessages.loading && !chatMessages.data?.length"
            class="flex flex-1 items-center justify-center"
          >
            <LoadingIndicator class="h-5 w-5" />
          </div>
          <div v-else-if="chatMessages.data?.length">
            <div
              v-for="msg in chatMessages.data"
              :key="msg.name"
              class="mb-3 flex gap-2"
              :class="msg.type === 'Outgoing' ? 'flex-row-reverse' : ''"
            >
              <div
                class="relative max-w-[75%] rounded-lg p-2.5 text-sm shadow-sm"
                :class="
                  msg.type === 'Outgoing'
                    ? 'bg-green-50 text-ink-gray-9'
                    : 'bg-surface-gray-1 text-ink-gray-9'
                "
              >
                <div
                  v-if="msg.type === 'Incoming' && msg.from_name"
                  class="mb-1 text-xs font-semibold text-green-700"
                >
                  {{ msg.from_name }}
                </div>
                <div v-if="msg.content_type === 'image' && msg.attach">
                  <img
                    :src="msg.attach"
                    class="max-h-60 cursor-pointer rounded-md"
                    @click="openImageFullscreen(msg.attach)"
                  />
                </div>
                <div v-else-if="msg.content_type === 'video' && msg.attach">
                  <video
                    :src="msg.attach"
                    controls
                    class="max-h-60 rounded-md"
                  />
                </div>
                <div
                  v-else-if="msg.content_type === 'audio' && msg.attach"
                >
                  <audio
                    :src="msg.attach"
                    controls
                    class="max-w-[260px]"
                  />
                </div>
                <div
                  v-else-if="msg.content_type === 'document' && msg.attach"
                  class="flex items-center gap-2"
                >
                  <FeatherIcon
                    name="file-text"
                    class="h-5 w-5 flex-shrink-0 text-ink-gray-5"
                  />
                  <a
                    :href="msg.attach"
                    target="_blank"
                    class="truncate text-sm text-blue-600 underline"
                  >
                    {{ __('Document') }}
                  </a>
                </div>
                <div v-if="msg.message" v-html="formatMessage(msg.message)" />
                <div class="mt-1 flex items-center justify-end gap-1">
                  <span class="text-2xs text-ink-gray-4">
                    {{ formatMsgTime(msg.creation) }}
                  </span>
                  <CheckIcon
                    v-if="msg.type === 'Outgoing'"
                    class="h-3.5 w-3.5 text-ink-gray-4"
                  />
                </div>
              </div>
            </div>
          </div>
          <div
            v-else
            class="flex flex-1 flex-col items-center justify-center text-sm text-ink-gray-4"
          >
            <FeatherIcon name="message-circle" class="mb-2 h-8 w-8" />
            <span>{{ __('No messages yet. Send the first message!') }}</span>
          </div>
        </div>

        <!-- Composer -->
        <ChatComposer
          :phone="selectedChat?.phone || ''"
          :jid="selectedJid || ''"
          @sent="onMessageSent"
        />
      </template>

      <!-- Empty State -->
      <div
        v-else
        class="flex flex-1 flex-col items-center justify-center text-ink-gray-4"
      >
        <WhatsAppIcon class="mb-3 h-12 w-12" />
        <p class="text-lg font-medium text-ink-gray-5">
          {{ __('WhatsApp Chats') }}
        </p>
        <p class="mt-1 text-sm">
          {{ __('Select a conversation to start messaging') }}
        </p>
      </div>
    </div>
  </div>

  <!-- New Chat Dialog -->
  <Dialog
    v-model="showNewChatDialog"
    :options="{
      title: __('New Chat'),
      size: 'sm',
    }"
  >
    <template #body-content>
      <div class="flex flex-col gap-3">
        <FormControl
          v-model="newChatPhone"
          :label="__('Phone Number')"
          :placeholder="__('+91 98765 43210')"
        />
        <Button
          variant="solid"
          :label="__('Start Chat')"
          :disabled="!newChatPhone"
          @click="startNewChat"
        />
      </div>
    </template>
  </Dialog>

  <!-- Fullscreen Image Overlay -->
  <Teleport to="body">
    <div
      v-if="fullscreenImage"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
      @click="fullscreenImage = null"
    >
      <img
        :src="fullscreenImage"
        class="max-h-[90vh] max-w-[90vw] rounded-lg object-contain"
        @click.stop
      />
      <button
        class="absolute right-4 top-4 rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
        @click="fullscreenImage = null"
      >
        <FeatherIcon name="x" class="h-6 w-6" />
      </button>
    </div>
  </Teleport>
</template>

<script setup>
import LayoutHeader from '@/components/LayoutHeader.vue'
import ViewBreadcrumbs from '@/components/ViewBreadcrumbs.vue'
import ChatComposer from '@/components/ChatComposer.vue'
import WhatsAppIcon from '@/components/Icons/WhatsAppIcon.vue'
import CheckIcon from '@/components/Icons/CheckIcon.vue'
import { globalStore } from '@/stores/global'
import { formatDate } from '@/utils'
import {
  createResource,
  TextInput,
  FormControl,
  Dialog,
  LoadingIndicator,
  FeatherIcon,
  Button,
  toast,
} from 'frappe-ui'
import { ref, computed, nextTick, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'

const { $socket } = globalStore()

const searchQuery = ref('')
const selectedJid = ref(null)
const selectedChat = ref(null)
const messagesContainer = ref(null)

const showNewChatDialog = ref(false)
const newChatPhone = ref('')
const fullscreenImage = ref(null)
const unreadJids = ref(new Set())
const lastSeenTimes = ref(new Map())

const router = useRouter()
const linkedDoc = ref(null)
const convertingToLead = ref(false)

// Check if the selected chat's phone is linked to a Lead/Deal
const chatLeadCheck = createResource({
  url: 'crm.api.whatsapp.get_chat_lead',
  auto: false,
  onSuccess: (data) => {
    linkedDoc.value = data || null
  },
})

watch(selectedJid, () => {
  linkedDoc.value = null
  if (selectedChat.value && !selectedChat.value.is_group) {
    chatLeadCheck.submit({ phone: selectedChat.value.phone })
  }
})

async function convertToLead() {
  if (!selectedChat.value) return
  convertingToLead.value = true
  try {
    const res = await createResource({
      url: 'crm.api.whatsapp.convert_chat_to_lead',
      params: {
        phone: selectedChat.value.phone,
        contact_name: selectedChat.value.contact_name || '',
      },
      auto: true,
    }).promise
    if (res.already_exists) {
      linkedDoc.value = { doctype: res.doctype, name: res.name }
      toast.info(__('This phone is already linked to {0}', [res.name]))
    } else {
      linkedDoc.value = { doctype: res.doctype, name: res.name }
      toast.success(__('Lead {0} created', [res.name]))
    }
  } catch (err) {
    toast.error(err.messages?.[0] || __('Failed to create lead'))
  } finally {
    convertingToLead.value = false
  }
}

function openImageFullscreen(src) {
  fullscreenImage.value = src
}

// Chat list resource - pulls from bridge via CRM backend
const chatList = createResource({
  url: 'crm.api.whatsapp.get_chat_list',
  params: {},
  auto: true,
  onSuccess: (data) => {
    if (!data) return
    for (const chat of data) {
      const prev = lastSeenTimes.value.get(chat.jid)
      if (prev === undefined) {
        // First load — initialize without marking unread
        lastSeenTimes.value.set(chat.jid, chat.last_message_time || '')
      } else if (
        chat.last_message_time &&
        chat.last_message_time !== prev &&
        chat.jid !== selectedJid.value
      ) {
        unreadJids.value.add(chat.jid)
        unreadJids.value = new Set(unreadJids.value)
        lastSeenTimes.value.set(chat.jid, chat.last_message_time)
      }
    }
  },
})

// Chat messages resource - pulls from bridge via CRM backend
const chatMessages = createResource({
  url: 'crm.api.whatsapp.get_chat_messages',
  params: { jid: '' },
  auto: false,
  onSuccess: () => nextTick(() => scrollToBottom()),
})

// Client-side search filtering
const filteredChats = computed(() => {
  if (!chatList.data) return []
  if (!searchQuery.value) return chatList.data
  const q = searchQuery.value.toLowerCase()
  return chatList.data.filter(
    (c) =>
      (c.contact_name || '').toLowerCase().includes(q) ||
      (c.phone || '').includes(q),
  )
})

function selectChat(chat) {
  selectedJid.value = chat.jid
  selectedChat.value = chat
  unreadJids.value.delete(chat.jid)
  unreadJids.value = new Set(unreadJids.value)
  // Record current time so we don't re-mark as unread
  lastSeenTimes.value.set(chat.jid, chat.last_message_time || '')
  chatMessages.update({ params: { jid: chat.jid } })
  chatMessages.reload()
}

function onMessageSent() {
  // Small delay so bridge has time to store the outgoing message
  setTimeout(() => {
    chatMessages.reload()
    chatList.reload()
  }, 1000)
}

function scrollToBottom() {
  if (messagesContainer.value) {
    const el = messagesContainer.value
    el.scrollTop = el.scrollHeight
  }
}

function startNewChat() {
  let phone = newChatPhone.value.trim().replace(/[\s-]/g, '')
  if (!phone) return
  if (!phone.startsWith('+')) {
    phone = '+' + phone
  }
  const jid = phone.replace('+', '') + '@s.whatsapp.net'
  showNewChatDialog.value = false
  newChatPhone.value = ''
  selectChat({ jid, phone, contact_name: '' })
}

function toLocalStr(dateStr) {
  // Convert UTC timestamp to local datetime string for formatDate
  const d = new Date(dateStr)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function formatTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24))
  const local = toLocalStr(dateStr)
  if (diffDays === 0) {
    return formatDate(local, 'hh:mm a')
  } else if (diffDays === 1) {
    return __('Yesterday')
  } else if (diffDays < 7) {
    return formatDate(local, 'ddd')
  }
  return formatDate(local, 'DD/MM/YY')
}

function formatMsgTime(dateStr) {
  if (!dateStr) return ''
  return formatDate(toLocalStr(dateStr), 'hh:mm a')
}

function formatMessage(text) {
  if (!text) return ''
  let msg = text
  msg = msg.replace(/\*(.*?)\*/g, '<b>$1</b>')
  msg = msg.replace(/_(.*?)_/g, '<i>$1</i>')
  msg = msg.replace(/~(.*?)~/g, '<s>$1</s>')
  msg = msg.replace(/```(.*?)```/g, '<code>$1</code>')
  msg = msg.replace(/\n/g, '<br>')
  return msg
}

// Realtime updates via socket + polling fallback
let pollInterval = null

onMounted(() => {
  $socket.on('whatsapp_message', () => {
    chatList.reload()
    if (selectedJid.value) {
      chatMessages.reload()
    }
  })

  // Poll every 5 seconds as fallback for realtime
  pollInterval = setInterval(() => {
    chatList.reload()
    if (selectedJid.value) {
      chatMessages.reload()
    }
  }, 5000)
})

onBeforeUnmount(() => {
  $socket.off('whatsapp_message')
  if (pollInterval) clearInterval(pollInterval)
})
</script>
