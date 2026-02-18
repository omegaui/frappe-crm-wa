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
            class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-surface-gray-3 text-ink-gray-5 overflow-hidden"
          >
            <img
              v-if="chat.photo_url"
              :src="chat.photo_url"
              class="h-10 w-10 rounded-full object-cover"
              @error="chat.photo_url = ''"
            />
            <FeatherIcon v-else name="user" class="h-5 w-5" />
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
              <div class="ml-1 flex flex-shrink-0 items-center gap-1">
                <UserAvatar
                  v-if="chat.assigned_to"
                  :user="chat.assigned_to"
                  size="xs"
                />
                <span
                  v-if="unreadJids.has(chat.jid)"
                  class="h-2.5 w-2.5 rounded-full bg-green-500"
                />
              </div>
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
            class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-surface-gray-3 text-ink-gray-5 overflow-hidden"
          >
            <img
              v-if="selectedChatPhoto"
              :src="selectedChatPhoto"
              class="h-9 w-9 rounded-full object-cover"
              @error="selectedChatPhoto = ''"
            />
            <FeatherIcon v-else name="user" class="h-4 w-4" />
          </div>
          <div class="flex-1">
            <div class="text-sm font-medium text-ink-gray-9">
              {{ selectedChat?.contact_name || selectedChat?.phone || __('Unknown') }}
            </div>
            <div v-if="selectedChat?.phone" class="text-xs text-ink-gray-4">
              {{ selectedChat?.phone }}
            </div>
          </div>
          <!-- Assignment -->
          <div class="relative">
            <div
              v-if="selectedChat?.assigned_to"
              class="flex items-center gap-1.5"
            >
              <UserAvatar :user="selectedChat.assigned_to" size="md" />
              <span class="text-xs text-ink-gray-6">
                {{ getUser(selectedChat.assigned_to).full_name }}
              </span>
              <button
                v-if="isManager()"
                class="ml-0.5 rounded p-0.5 text-ink-gray-4 hover:bg-surface-gray-2 hover:text-ink-gray-6"
                @click="unassignChat"
              >
                <FeatherIcon name="x" class="h-3 w-3" />
              </button>
            </div>
            <div v-else-if="isManager()">
              <Button
                variant="ghost"
                size="sm"
                @click="showAssignDropdown = !showAssignDropdown"
              >
                <template #prefix>
                  <FeatherIcon name="user-check" class="h-3.5 w-3.5" />
                </template>
                {{ __('Assign') }}
              </Button>
            </div>
            <div
              v-if="showAssignDropdown && isManager()"
              class="absolute right-0 top-full z-10 mt-1 w-56 rounded-lg border bg-surface-white p-1 shadow-lg"
            >
              <Autocomplete
                :options="crmUserOptions"
                :placeholder="__('Search staff...')"
                @update:modelValue="assignChatToUser"
              />
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
            v-if="chatMessages.loading && !messages.length"
            class="flex flex-1 items-center justify-center"
          >
            <LoadingIndicator class="h-5 w-5" />
          </div>
          <div v-else-if="messages.length">
            <div
              v-for="msg in messages"
              :key="msg._tempId || msg.name"
              class="mb-3 flex gap-2"
              :class="msg.type === 'Outgoing' ? 'flex-row-reverse' : ''"
              @contextmenu.prevent="showContextMenu($event, msg)"
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
                <div
                  v-else-if="msg.type === 'Outgoing' && msg.from_name && msg.from_name !== __('You')"
                  class="mb-1 text-xs font-semibold text-blue-600"
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
                  <FeatherIcon
                    v-if="msg._pending"
                    name="clock"
                    class="h-3 w-3 text-ink-gray-3"
                  />
                  <CheckIcon
                    v-else-if="msg.type === 'Outgoing'"
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
          @submit="handleComposerSubmit"
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

  <!-- Message Context Menu -->
  <Teleport to="body">
    <div
      v-if="contextMenu.visible"
      class="fixed z-50 min-w-[140px] rounded-lg border bg-surface-white py-1 shadow-lg"
      :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }"
      @click.stop
    >
      <button
        class="flex w-full items-center gap-2 px-3 py-2 text-sm text-ink-red-3 hover:bg-surface-gray-2"
        @click="confirmDeleteMessage"
      >
        <FeatherIcon name="trash-2" class="h-3.5 w-3.5" />
        {{ __('Delete') }}
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
import UserAvatar from '@/components/UserAvatar.vue'
import { globalStore } from '@/stores/global'
import { usersStore } from '@/stores/users'
import { formatDate } from '@/utils'
import {
  createResource,
  Autocomplete,
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
// Single reactive source for all displayed messages (loaded + optimistic pending)
const messages = ref([])
const selectedChatPhoto = ref('')
const contextMenu = ref({ visible: false, x: 0, y: 0, msg: null })

const router = useRouter()
const { getUser, users: usersResource, isManager } = usersStore()
const linkedDoc = ref(null)
const convertingToLead = ref(false)
const showAssignDropdown = ref(false)

const crmUserOptions = computed(() => {
  const crmUsers = usersResource.data?.crmUsers || []
  return crmUsers.map((u) => ({
    label: u.full_name || u.name,
    value: u.name,
  }))
})

function assignChatToUser(option) {
  showAssignDropdown.value = false
  if (!selectedChat.value || !option) return
  const user = option.value
  createResource({
    url: 'crm.api.whatsapp.assign_chat',
    params: { jid: selectedJid.value, user },
    auto: true,
    onSuccess: () => {
      selectedChat.value.assigned_to = user
      chatList.reload()
    },
  })
}

function unassignChat() {
  if (!selectedChat.value) return
  createResource({
    url: 'crm.api.whatsapp.assign_chat',
    params: { jid: selectedJid.value, user: '' },
    auto: true,
    onSuccess: () => {
      selectedChat.value.assigned_to = ''
      chatList.reload()
    },
  })
}

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
        assigned_to: selectedChat.value.assigned_to || '',
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
        chat.last_message_time !== prev
      ) {
        if (chat.jid === selectedJid.value) {
          // Selected chat has new messages — reload messages (fallback for missed socket events)
          lastSeenTimes.value.set(chat.jid, chat.last_message_time)
          shouldAutoScroll.value = isNearBottom()
          chatMessages.reload()
        } else {
          unreadJids.value.add(chat.jid)
          unreadJids.value = new Set(unreadJids.value)
          lastSeenTimes.value.set(chat.jid, chat.last_message_time)
        }
      }
    }
  },
})

const shouldAutoScroll = ref(true)

// Chat messages resource - pulls from bridge via CRM backend
const chatMessages = createResource({
  url: 'crm.api.whatsapp.get_chat_messages',
  params: { jid: '' },
  auto: false,
  onSuccess: (data) => {
    // Preserve any in-flight pending messages so they don't flicker on reload
    const pending = messages.value.filter((m) => m._pending)
    messages.value = [...(data || []), ...pending]
    if (shouldAutoScroll.value) {
      nextTick(() => {
        scrollToBottom()
        shouldAutoScroll.value = false
      })
    }
  },
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
  showAssignDropdown.value = false
  selectedJid.value = chat.jid
  selectedChat.value = chat
  unreadJids.value.delete(chat.jid)
  unreadJids.value = new Set(unreadJids.value)
  // Record current time so we don't re-mark as unread
  lastSeenTimes.value.set(chat.jid, chat.last_message_time || '')
  shouldAutoScroll.value = true
  messages.value = []
  chatMessages.update({ params: { jid: chat.jid } })
  chatMessages.reload()
  // Start with cached photo from chat list, then fetch fresh
  selectedChatPhoto.value = chat.photo_url || ''
  fetchProfilePhoto(chat.jid)
}

function fetchProfilePhoto(jid) {
  createResource({
    url: 'crm.api.whatsapp.get_profile_photo',
    params: { jid },
    auto: true,
    onSuccess: (data) => {
      if (data?.url && selectedJid.value === jid) {
        selectedChatPhoto.value = data.url
        // Also update the chat list entry
        const chatEntry = chatList.data?.find((c) => c.jid === jid)
        if (chatEntry) chatEntry.photo_url = data.url
      }
    },
  })
}

function handleComposerSubmit({ message, content_type, attach, reply_to }) {
  const tempId = `_p_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
  const createdAt = Date.now()

  // Add optimistic pending message immediately — before any async work
  const pendingMsg = {
    name: tempId,
    _tempId: tempId,
    _pending: true,
    _createdAt: createdAt,
    type: 'Outgoing',
    from: '',
    to: selectedChat.value?.phone || '',
    message,
    message_id: '',
    content_type,
    message_type: '',
    status: 'pending',
    creation: new Date().toISOString(),
    attach: attach || '',
    is_reply: false,
    reply_to_message_id: '',
    from_name: window.frappe?.boot?.user?.full_name || __('You'),
  }
  const shouldScroll = isNearBottom()
  messages.value.push(pendingMsg)
  if (shouldScroll) nextTick(() => scrollToBottom())

  // Now fire the API call
  createResource({
    url: 'crm.api.whatsapp.send_chat_message',
    params: {
      phone: selectedChat.value?.phone || '',
      jid: selectedJid.value || '',
      message,
      attach,
      content_type,
      reply_to: reply_to || '',
    },
    auto: true,
    onSuccess: (data) => {
      const message_id = data?.message_id || ''
      const elapsed = Date.now() - createdAt
      const confirm = () => {
        const i = messages.value.findIndex((m) => m._tempId === tempId)
        if (i !== -1) {
          messages.value.splice(i, 1, {
            ...pendingMsg,
            _pending: false,
            message_id,
            name: message_id || tempId,
          })
        }
      }
      if (elapsed < PENDING_MIN_MS) setTimeout(confirm, PENDING_MIN_MS - elapsed)
      else confirm()
    },
    onError: (error) => {
      toast.error(error.messages?.[0] || __('Failed to send WhatsApp message'))
      const i = messages.value.findIndex((m) => m._tempId === tempId)
      if (i !== -1) messages.value.splice(i, 1)
    },
  })
}

function scrollToBottom() {
  if (messagesContainer.value) {
    const el = messagesContainer.value
    el.scrollTop = el.scrollHeight
  }
}

function isNearBottom() {
  const el = messagesContainer.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 150
}

function updateChatListEntry(data) {
  if (!chatList.data) return

  const idx = chatList.data.findIndex(
    (c) => c.jid === data.chat_jid || (data.phone && c.phone === data.phone),
  )

  if (idx === -1) {
    // New conversation — full reload to get metadata from bridge
    chatList.reload()
    return
  }

  const chat = chatList.data[idx]

  if (data.chat_update) {
    chat.last_message = data.chat_update.last_message || chat.last_message
    chat.last_message_time =
      data.chat_update.last_message_time || chat.last_message_time
  }

  // Move chat to top of list
  if (idx > 0) {
    chatList.data.splice(idx, 1)
    chatList.data.unshift(chat)
  }

  // Update lastSeenTimes if this is the selected chat
  if (chat.jid === selectedJid.value) {
    lastSeenTimes.value.set(chat.jid, chat.last_message_time || '')
  }
}

function isForSelectedChat(data) {
  if (!selectedJid.value) return false
  return (
    data.chat_jid === selectedJid.value ||
    (data.phone && data.phone === selectedChat.value?.phone)
  )
}

// Minimum time (ms) a pending message must be visible so the clock icon is seen
const PENDING_MIN_MS = 600

function appendMessageIfNew(message) {
  if (!message) return

  if (message.type === 'Outgoing') {
    const pendingIdx = messages.value.findIndex(
      (m) =>
        m._pending &&
        m.content_type === message.content_type &&
        m.message === message.message &&
        (message.content_type === 'text' || m.attach === message.attach),
    )
    if (pendingIdx !== -1) {
      const pending = messages.value[pendingIdx]
      const elapsed = Date.now() - (pending._createdAt || 0)

      const confirm = () => {
        const i = messages.value.findIndex((m) => m._tempId === pending._tempId)
        if (i !== -1) {
          // Replace pending in-place so it stays at the same scroll position
          messages.value.splice(i, 1, { ...message, _pending: false })
        }
      }

      if (elapsed < PENDING_MIN_MS) {
        setTimeout(confirm, PENDING_MIN_MS - elapsed)
      } else {
        confirm()
      }
      return
    }
  }

  // Dedup by message_id / name (guards against duplicate socket events or already-confirmed sends)
  const exists = messages.value.some(
    (m) =>
      (m.message_id && m.message_id === message.message_id) ||
      (m.name === message.name && !m._pending),
  )
  if (exists) return

  const shouldScroll = isNearBottom()
  messages.value.push(message)
  if (shouldScroll) nextTick(() => scrollToBottom())
}

function showContextMenu(event, msg) {
  if (msg._pending) return // don't allow delete of pending messages
  contextMenu.value = {
    visible: true,
    x: Math.min(event.clientX, window.innerWidth - 160),
    y: Math.min(event.clientY, window.innerHeight - 80),
    msg,
  }
}

function hideContextMenu() {
  contextMenu.value.visible = false
  contextMenu.value.msg = null
}

function confirmDeleteMessage() {
  const msg = contextMenu.value.msg
  hideContextMenu()
  if (!msg || !selectedJid.value) return
  createResource({
    url: 'crm.api.whatsapp.delete_chat_message',
    params: { jid: selectedJid.value, message_id: msg.message_id || msg.name },
    auto: true,
    onSuccess: () => {
      const idx = messages.value.findIndex(
        (m) => m.name === msg.name || m.message_id === msg.message_id,
      )
      if (idx !== -1) messages.value.splice(idx, 1)
    },
    onError: () => {
      toast.error(__('Failed to delete message'))
    },
  })
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

// Realtime updates via socket
let syncInterval = null

onMounted(() => {
  document.addEventListener('click', hideContextMenu)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') hideContextMenu()
  })

  $socket.on('whatsapp_chat_update', (data) => {
    if (data.event_type === 'new_message') {
      updateChatListEntry(data)

      if (isForSelectedChat(data)) {
        appendMessageIfNew(data.message)
      } else if (data.chat_jid) {
        unreadJids.value.add(data.chat_jid)
        unreadJids.value = new Set(unreadJids.value)
      }
    }
  })

  // 15s fallback sync for chat list — also triggers message reload
  // for selected chat if new messages detected (covers missed socket events)
  syncInterval = setInterval(() => {
    chatList.reload()
  }, 15000)
})

onBeforeUnmount(() => {
  $socket.off('whatsapp_chat_update')
  if (syncInterval) clearInterval(syncInterval)
  document.removeEventListener('click', hideContextMenu)
})
</script>
