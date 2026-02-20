<template>
  <LayoutHeader>
    <template #left-header>
      <ViewBreadcrumbs routeName="Chats" />
    </template>
    <template #right-header>
      <Button variant="ghost" @click="chatList.reload()" :loading="chatList.loading">
        <template #icon><FeatherIcon name="refresh-cw" class="h-4" /></template>
      </Button>
      <Button
        v-if="isManager()"
        variant="subtle"
        :label="__('Merge Duplicates')"
        :loading="mergingDuplicates"
        @click="mergeDuplicateChats"
      >
        <template #prefix><FeatherIcon name="git-merge" class="h-4" /></template>
      </Button>
      <Button
        v-if="isAdmin()"
        variant="subtle"
        :label="__('Templates')"
        @click="showTemplatesDialog = true"
      >
        <template #prefix><FeatherIcon name="file-text" class="h-4" /></template>
      </Button>
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
                <span v-if="chat.last_message_is_from_me && chat.last_message_sender_name" class="font-medium text-ink-gray-6">{{ chat.last_message_sender_name.split(' ')[0] }}: </span>{{ chat.last_message || chat.phone }}
              </span>
              <div class="ml-1 flex flex-shrink-0 items-center gap-1">
                <span
                  v-if="chat.assigned_to"
                  class="text-[10px] px-1.5 py-0.5 rounded-full font-medium truncate max-w-[80px]"
                  :class="getAssigneeColor(chat.assigned_to)"
                >
                  {{ getUser(chat.assigned_to).full_name?.split(' ')[0] || chat.assigned_to }}
                </span>
                <span
                  v-if="unreadJids.has(chat.jid)"
                  class="h-2.5 w-2.5 rounded-full bg-green-500"
                />
              </div>
            </div>
            <div v-if="chat.user_status || chat.plan || chat.shop_type" class="flex flex-wrap gap-1 mt-1">
              <span v-if="chat.user_status" class="text-[9px] leading-tight px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700">{{ chat.user_status }}</span>
              <span v-if="chat.plan" class="text-[9px] leading-tight px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700">{{ chat.plan }}</span>
              <span v-if="chat.shop_type" class="text-[9px] leading-tight px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700">{{ chat.shop_type }}</span>
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
            :class="{ 'cursor-pointer': selectedChatPhoto }"
            @click="selectedChatPhoto && openImageFullscreen(selectedChatPhoto)"
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
              {{ selectedChat?.contact_name || selectedChatPhone || __('Unknown') }}
            </div>
            <div v-if="selectedChatPhone" class="flex items-center gap-1 text-xs text-ink-gray-5">
              <span>{{ selectedChatPhone }}</span>
              <button
                class="rounded p-0.5 text-ink-gray-4 hover:bg-surface-gray-2 hover:text-ink-gray-6"
                @click="copyPhone"
              >
                <FeatherIcon name="copy" class="h-3 w-3" />
              </button>
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

          <!-- Delete Chat -->
          <Button
            v-if="isManager()"
            variant="ghost"
            size="sm"
            @click="confirmDeleteChat"
          >
            <template #icon>
              <FeatherIcon name="trash-2" class="h-3.5 w-3.5 text-ink-red-3" />
            </template>
          </Button>

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

        <!-- Tags Row -->
        <div :key="'tags-' + selectedJid" class="flex items-center gap-2 border-b px-4 py-1.5">
          <span class="text-[10px] font-medium text-ink-gray-4 uppercase">Tags</span>
          <FormControl
            type="select"
            :modelValue="selectedChat?.user_status || ''"
            :options="[{label: 'Status...', value: ''}, ...TAG_OPTIONS.user_status.map(o => ({label: o, value: o}))]"
            class="!text-xs !h-6"
            size="sm"
            @update:modelValue="(val) => updateTag('user_status', val)"
          />
          <FormControl
            type="select"
            :modelValue="selectedChat?.plan || ''"
            :options="[{label: 'Plan...', value: ''}, ...TAG_OPTIONS.plan.map(o => ({label: o, value: o}))]"
            class="!text-xs !h-6"
            size="sm"
            @update:modelValue="(val) => updateTag('plan', val)"
          />
          <FormControl
            type="select"
            :modelValue="selectedChat?.shop_type || ''"
            :options="[{label: 'Shop...', value: ''}, ...TAG_OPTIONS.shop_type.map(o => ({label: o, value: o}))]"
            class="!text-xs !h-6"
            size="sm"
            @update:modelValue="(val) => updateTag('shop_type', val)"
          />
        </div>

        <!-- Notes Area -->
        <div class="border-b px-4 py-2 max-h-32 overflow-y-auto bg-surface-gray-1">
          <div v-for="note in chatNotes" :key="note.id" class="flex items-start gap-2 mb-1.5 group">
            <template v-if="editingNoteId === note.id">
              <TextInput
                v-model="editingNoteContent"
                class="flex-1 text-xs"
                size="sm"
                @keyup.enter="saveEditNote(note.id)"
              />
              <Button variant="subtle" size="sm" @click="saveEditNote(note.id)">
                <template #icon><FeatherIcon name="check" class="h-3 w-3" /></template>
              </Button>
              <Button variant="ghost" size="sm" @click="editingNoteId = null">
                <template #icon><FeatherIcon name="x" class="h-3 w-3" /></template>
              </Button>
            </template>
            <template v-else>
              <span class="flex-1 text-xs text-ink-gray-7">{{ note.content }}</span>
              <span class="text-[10px] text-ink-gray-4 whitespace-nowrap">{{ note.created_by?.split('@')[0] }}</span>
              <button class="text-ink-gray-4 hover:text-ink-gray-6 opacity-0 group-hover:opacity-100" @click="startEditNote(note)">
                <FeatherIcon name="edit-2" class="h-3 w-3" />
              </button>
              <button class="text-ink-gray-4 hover:text-ink-red-3 opacity-0 group-hover:opacity-100" @click="deleteNote(note.id)">
                <FeatherIcon name="x" class="h-3 w-3" />
              </button>
            </template>
          </div>
          <div class="flex gap-2 mt-1">
            <TextInput
              v-model="newNoteContent"
              :placeholder="__('Add a note...')"
              class="flex-1 text-xs"
              size="sm"
              @keyup.enter="addNote"
            />
            <Button variant="subtle" size="sm" :disabled="!newNoteContent.trim()" @click="addNote">
              {{ __('Add') }}
            </Button>
          </div>
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

    <!-- Right Panel: Lead Details -->
    <Resizer
      v-if="linkedDoc && linkedDoc.doctype === 'CRM Lead'"
      :key="linkedDoc.name"
      class="flex flex-col overflow-hidden border-l"
      side="right"
      :defaultWidth="320"
      :minWidth="280"
      :maxWidth="480"
    >
      <div class="flex h-[45px] items-center justify-between border-b px-4">
        <router-link
          :to="{ name: 'Lead', params: { leadId: linkedDoc.name } }"
          class="flex items-center gap-1.5 text-sm font-medium text-ink-gray-7 hover:text-ink-gray-9"
        >
          {{ linkedDoc.name }}
          <FeatherIcon name="external-link" class="h-3 w-3" />
        </router-link>
      </div>
      <div
        v-if="leadSections.data"
        class="flex flex-1 flex-col overflow-hidden"
      >
        <SidePanelLayout
          :key="linkedDoc.name"
          :sections="leadSections.data"
          doctype="CRM Lead"
          :docname="linkedDoc.name"
          @reload="leadSections.reload"
        />
      </div>
      <div v-else class="flex flex-1 items-center justify-center">
        <LoadingIndicator class="h-5 w-5" />
      </div>
    </Resizer>
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
        <FormControl
          v-if="chatTemplates.length"
          type="select"
          :label="__('Template')"
          :modelValue="selectedTemplateId"
          :options="[{label: __('None'), value: ''}, ...chatTemplates.map(t => ({label: t.name, value: String(t.id)}))]"
          @change="applyTemplate"
        />
        <FormControl
          v-model="newChatMessage"
          type="textarea"
          :label="__('Message')"
          :placeholder="__('Type your first message...')"
          rows="3"
        />
        <Button
          variant="solid"
          :label="__('Start Chat')"
          :disabled="!newChatPhone || !newChatMessage.trim() || sendingNewChat"
          :loading="sendingNewChat"
          @click="startNewChat"
        />
      </div>
    </template>
  </Dialog>

  <!-- Templates Management Dialog -->
  <Dialog
    v-model="showTemplatesDialog"
    :options="{
      title: __('Chat Templates'),
      size: 'lg',
    }"
  >
    <template #body-content>
      <div class="flex flex-col gap-3">
        <div v-for="tpl in chatTemplates" :key="tpl.id" class="flex items-start gap-2 rounded-lg border p-3">
          <div class="flex-1">
            <div class="text-sm font-medium text-ink-gray-9">{{ tpl.name }}</div>
            <div class="mt-1 text-xs text-ink-gray-6 whitespace-pre-wrap">{{ tpl.content }}</div>
          </div>
          <Button variant="ghost" size="sm" @click="startEditTemplate(tpl)">
            <template #icon><FeatherIcon name="edit-2" class="h-3.5 w-3.5" /></template>
          </Button>
          <Button variant="ghost" size="sm" @click="removeTemplate(tpl.id)">
            <template #icon><FeatherIcon name="trash-2" class="h-3.5 w-3.5 text-ink-red-3" /></template>
          </Button>
        </div>
        <div v-if="!chatTemplates.length" class="py-4 text-center text-sm text-ink-gray-4">
          {{ __('No templates yet. Create one below.') }}
        </div>
        <div class="flex flex-col gap-2 rounded-lg border border-dashed p-3">
          <div class="text-xs font-medium text-ink-gray-5">{{ editingTemplateId ? __('Edit Template') : __('New Template') }}</div>
          <FormControl
            v-model="templateName"
            :placeholder="__('Template name')"
            size="sm"
          />
          <FormControl
            v-model="templateContent"
            type="textarea"
            :placeholder="__('Template message content...')"
            rows="3"
          />
          <div class="flex gap-2">
            <Button
              variant="solid"
              size="sm"
              :label="editingTemplateId ? __('Update') : __('Create')"
              :disabled="!templateName.trim() || !templateContent.trim()"
              @click="saveTemplate"
            />
            <Button
              v-if="editingTemplateId"
              variant="ghost"
              size="sm"
              :label="__('Cancel')"
              @click="cancelEditTemplate"
            />
          </div>
        </div>
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
import Resizer from '@/components/Resizer.vue'
import SidePanelLayout from '@/components/SidePanelLayout.vue'
import { globalStore } from '@/stores/global'
import { usersStore } from '@/stores/users'
import { formatDate } from '@/utils'
import {
  createResource,
  call,
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

const ASSIGNEE_COLORS = [
  'bg-blue-100 text-blue-700', 'bg-green-100 text-green-700',
  'bg-purple-100 text-purple-700', 'bg-orange-100 text-orange-700',
  'bg-pink-100 text-pink-700', 'bg-teal-100 text-teal-700',
  'bg-red-100 text-red-700', 'bg-indigo-100 text-indigo-700',
  'bg-yellow-100 text-yellow-700', 'bg-cyan-100 text-cyan-700',
  'bg-rose-100 text-rose-700', 'bg-emerald-100 text-emerald-700',
]

function getAssigneeColor(email) {
  let hash = 0
  for (let i = 0; i < email.length; i++) {
    hash = ((hash << 5) - hash) + email.charCodeAt(i)
    hash |= 0
  }
  return ASSIGNEE_COLORS[Math.abs(hash) % ASSIGNEE_COLORS.length]
}

const TAG_OPTIONS = {
  user_status: ['New User', "Didn't pick", 'Unreachable', 'Not Interested', 'Spoke will try app', 'Busy, Followup', 'Really Interested', 'Interested', 'Cut after BF mentioned', 'DND', 'Language issue'],
  plan: ['LITE PLAN', 'PREMIUM', 'ULTRA', 'Confused'],
  shop_type: ['grocery', 'hardware', 'petStore', 'cosmetics', 'electronics', 'bookStore', 'stationary', 'toysAndSports', 'restaurant', 'bakery', 'shoes', 'clothing', 'jewellery', 'others'],
}

const searchQuery = ref('')
const selectedJid = ref(null)
const selectedChat = ref(null)
const messagesContainer = ref(null)

const showNewChatDialog = ref(false)
const newChatPhone = ref('')
const newChatMessage = ref('')
const sendingNewChat = ref(false)
const mergingDuplicates = ref(false)
const fullscreenImage = ref(null)
const unreadJids = ref(new Set())
const lastSeenTimes = ref(new Map())
// Single reactive source for all displayed messages (loaded + optimistic pending)
const messages = ref([])
const selectedChatPhoto = ref('')
const contextMenu = ref({ visible: false, x: 0, y: 0, msg: null })

const router = useRouter()
const { getUser, users: usersResource, isManager, isAdmin } = usersStore()
const linkedDoc = ref(null)
const convertingToLead = ref(false)
const showAssignDropdown = ref(false)

// Notes state
const chatNotes = ref([])
const newNoteContent = ref('')
const editingNoteId = ref(null)
const editingNoteContent = ref('')

// Templates state
const showTemplatesDialog = ref(false)
const chatTemplates = ref([])
const templateName = ref('')
const templateContent = ref('')
const editingTemplateId = ref(null)
const selectedTemplateId = ref('')

// Lead side panel sections (cached, shared with Lead page)
const leadSections = createResource({
  url: 'crm.fcrm.doctype.crm_fields_layout.crm_fields_layout.get_sidepanel_sections',
  cache: ['sidePanelSections', 'CRM Lead'],
  params: { doctype: 'CRM Lead' },
  auto: true,
})

const selectedChatPhone = computed(() => {
  if (!selectedChat.value) return ''
  if (selectedChat.value.phone) return selectedChat.value.phone
  // Derive phone from JID for @s.whatsapp.net contacts
  const jid = selectedJid.value || ''
  if (jid.endsWith('@s.whatsapp.net')) {
    return '+' + jid.split('@')[0].split(':')[0]
  }
  return ''
})

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

function copyPhone() {
  if (!selectedChatPhone.value) return
  navigator.clipboard.writeText(selectedChatPhone.value)
  toast.success(__('Phone number copied'))
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
          // Desktop notification + sound for incoming messages detected via polling
          if (!chat.last_message_is_from_me) {
            playNotificationSound()
            showDesktopNotification({
              chat_jid: chat.jid,
              phone: chat.phone,
              message: { message: chat.last_message, type: 'Incoming' },
            })
          }
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
  loadNotes(chat.jid)
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

// -- Tags --
function updateTag(tagType, value) {
  if (!selectedJid.value) return
  const jid = selectedJid.value
  const params = { jid }
  params[tagType] = value || ''
  call('crm.api.whatsapp.set_chat_tags', params)
    .then(() => {
      if (selectedChat.value) selectedChat.value[tagType] = value
      const chatEntry = chatList.data?.find((c) => c.jid === jid)
      if (chatEntry) chatEntry[tagType] = value
    })
    .catch((e) => {
      console.error('Failed to save tag:', tagType, value, e)
      toast.error(__('Failed to save tag'))
    })
}

// -- Notes --
function loadNotes(jid) {
  chatNotes.value = []
  newNoteContent.value = ''
  editingNoteId.value = null
  if (!jid) return
  createResource({
    url: 'crm.api.whatsapp.get_chat_notes',
    params: { jid },
    auto: true,
    onSuccess: (data) => {
      if (selectedJid.value === jid) chatNotes.value = data || []
    },
  })
}

function addNote() {
  const content = newNoteContent.value.trim()
  if (!content || !selectedJid.value) return
  newNoteContent.value = ''
  createResource({
    url: 'crm.api.whatsapp.add_chat_note',
    params: { jid: selectedJid.value, content },
    auto: true,
    onSuccess: (note) => {
      if (note && note.id) chatNotes.value.unshift(note)
    },
    onError: () => toast.error(__('Failed to add note')),
  })
}

function startEditNote(note) {
  editingNoteId.value = note.id
  editingNoteContent.value = note.content
}

function saveEditNote(noteId) {
  const content = editingNoteContent.value.trim()
  if (!content || !selectedJid.value) return
  createResource({
    url: 'crm.api.whatsapp.update_chat_note',
    params: { jid: selectedJid.value, note_id: noteId, content },
    auto: true,
    onSuccess: (updated) => {
      editingNoteId.value = null
      if (updated) {
        const idx = chatNotes.value.findIndex((n) => n.id === noteId)
        if (idx !== -1) chatNotes.value.splice(idx, 1, updated)
      }
    },
    onError: () => toast.error(__('Failed to update note')),
  })
}

function deleteNote(noteId) {
  if (!selectedJid.value) return
  createResource({
    url: 'crm.api.whatsapp.delete_chat_note',
    params: { jid: selectedJid.value, note_id: noteId },
    auto: true,
    onSuccess: () => {
      chatNotes.value = chatNotes.value.filter((n) => n.id !== noteId)
    },
    onError: () => toast.error(__('Failed to delete note')),
  })
}

// -- Templates --
function loadTemplates() {
  createResource({
    url: 'crm.api.whatsapp.get_chat_templates',
    params: {},
    auto: true,
    onSuccess: (data) => {
      chatTemplates.value = data || []
    },
  })
}

function saveTemplate() {
  const name = templateName.value.trim()
  const content = templateContent.value.trim()
  if (!name || !content) return

  if (editingTemplateId.value) {
    createResource({
      url: 'crm.api.whatsapp.update_chat_template',
      params: { template_id: editingTemplateId.value, name, content },
      auto: true,
      onSuccess: (updated) => {
        if (updated) {
          const idx = chatTemplates.value.findIndex((t) => t.id === editingTemplateId.value)
          if (idx !== -1) chatTemplates.value.splice(idx, 1, updated)
        }
        cancelEditTemplate()
      },
      onError: () => toast.error(__('Failed to update template')),
    })
  } else {
    createResource({
      url: 'crm.api.whatsapp.add_chat_template',
      params: { name, content },
      auto: true,
      onSuccess: (tpl) => {
        if (tpl && tpl.id) chatTemplates.value.unshift(tpl)
        templateName.value = ''
        templateContent.value = ''
      },
      onError: () => toast.error(__('Failed to create template')),
    })
  }
}

function startEditTemplate(tpl) {
  editingTemplateId.value = tpl.id
  templateName.value = tpl.name
  templateContent.value = tpl.content
}

function cancelEditTemplate() {
  editingTemplateId.value = null
  templateName.value = ''
  templateContent.value = ''
}

function removeTemplate(id) {
  createResource({
    url: 'crm.api.whatsapp.delete_chat_template',
    params: { template_id: id },
    auto: true,
    onSuccess: () => {
      chatTemplates.value = chatTemplates.value.filter((t) => t.id !== id)
    },
    onError: () => toast.error(__('Failed to delete template')),
  })
}

function applyTemplate(val) {
  const id = typeof val === 'object' ? val.target?.value || '' : val
  selectedTemplateId.value = id
  if (!id) return
  const tpl = chatTemplates.value.find((t) => String(t.id) === String(id))
  if (tpl) newChatMessage.value = tpl.content
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
    if (data.chat_update.last_message_is_from_me !== undefined) {
      chat.last_message_is_from_me = data.chat_update.last_message_is_from_me
    }
    if (data.chat_update.last_message_sender_name !== undefined) {
      chat.last_message_sender_name = data.chat_update.last_message_sender_name
    }
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

function mergeDuplicateChats() {
  mergingDuplicates.value = true
  createResource({
    url: 'crm.api.whatsapp.merge_duplicate_chats',
    params: {},
    auto: true,
    onSuccess: (data) => {
      mergingDuplicates.value = false
      const merged = data?.merged || 0
      if (merged > 0) {
        toast.success(__('Merged {0} duplicate chat(s)', [merged]))
        chatList.reload()
        // Clear selection since the selected chat may have been merged
        selectedJid.value = null
        selectedChat.value = null
        messages.value = []
      } else {
        toast.info(__('No duplicate chats found'))
      }
    },
    onError: () => {
      mergingDuplicates.value = false
      toast.error(__('Failed to merge duplicate chats'))
    },
  })
}

function confirmDeleteChat() {
  if (!selectedChat.value || !selectedJid.value) return
  const chatName = selectedChat.value.contact_name || selectedChat.value.phone || __('this chat')
  if (!window.confirm(__('Delete chat with {0}? This will remove all messages.', [chatName]))) return

  createResource({
    url: 'crm.api.whatsapp.delete_chat',
    params: { jid: selectedJid.value },
    auto: true,
    onSuccess: () => {
      // Remove from local list
      if (chatList.data) {
        const idx = chatList.data.findIndex((c) => c.jid === selectedJid.value)
        if (idx !== -1) chatList.data.splice(idx, 1)
      }
      selectedJid.value = null
      selectedChat.value = null
      messages.value = []
      linkedDoc.value = null
      toast.success(__('Chat deleted'))
    },
    onError: () => {
      toast.error(__('Failed to delete chat'))
    },
  })
}

function startNewChat() {
  let phone = newChatPhone.value.trim().replace(/[\s-]/g, '')
  if (!phone) return
  if (!phone.startsWith('+')) {
    phone = '+' + phone
  }
  const message = newChatMessage.value.trim()
  if (!message) return

  sendingNewChat.value = true
  const capturedPhone = phone

  createResource({
    url: 'crm.api.whatsapp.send_chat_message',
    params: { phone, message },
    auto: true,
    onSuccess: async (data) => {
      const chatJid = data?.chat_jid || ''
      showNewChatDialog.value = false
      newChatPhone.value = ''
      newChatMessage.value = ''
      sendingNewChat.value = false

      // Reload chat list so the bridge-created chat appears
      await chatList.reload()
      const chat = chatList.data?.find((c) => c.jid === chatJid)
      if (chat) {
        selectChat(chat)
      } else {
        selectChat({ jid: chatJid, phone: capturedPhone, contact_name: '' })
      }
    },
    onError: (error) => {
      sendingNewChat.value = false
      toast.error(error.messages?.[0] || __('Failed to send message'))
    },
  })
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

// Build a digits→name map from the chat list for resolving @mentions
// Maps both phone digits (919876543210) and JID prefixes (215414101512439 for @lid) to names
const mentionNameMap = computed(() => {
  const map = new Map()
  if (!chatList.data) return map
  for (const chat of chatList.data) {
    if (!chat.contact_name || chat.is_group) continue
    // Map phone digits → name
    if (chat.phone) {
      const digits = chat.phone.replace(/[+\s-]/g, '')
      if (digits) map.set(digits, chat.contact_name)
    }
    // Map JID prefix → name (covers @lid JIDs like 215414101512439@lid)
    if (chat.jid && chat.jid.includes('@')) {
      const jidPrefix = chat.jid.split('@')[0].split(':')[0]
      if (jidPrefix && !map.has(jidPrefix)) {
        map.set(jidPrefix, chat.contact_name)
      }
    }
  }
  return map
})

function formatMessage(text) {
  if (!text) return ''
  let msg = text
  // 1. Extract URLs into placeholders (before other formatting to protect URL characters)
  const urls = []
  msg = msg.replace(/(https?:\/\/[^\s<]+)/g, (match) => {
    urls.push(match)
    return `__URL_${urls.length - 1}__`
  })
  // 2. Resolve @mentions: @919876543210 or @215414101512439 (LID) → @ContactName or @+phone
  msg = msg.replace(/@(\d{7,20})/g, (match, digits) => {
    const name = mentionNameMap.value.get(digits)
    if (name) {
      return `<span class="font-semibold text-blue-600">@${name}</span>`
    }
    return `<span class="font-semibold text-blue-600">@+${digits}</span>`
  })
  // 3. WhatsApp text formatting
  msg = msg.replace(/\*(.*?)\*/g, '<b>$1</b>')
  msg = msg.replace(/_(.*?)_/g, '<i>$1</i>')
  msg = msg.replace(/~(.*?)~/g, '<s>$1</s>')
  msg = msg.replace(/```(.*?)```/g, '<code>$1</code>')
  // 4. Restore URLs as clickable links
  msg = msg.replace(/__URL_(\d+)__/g, (_, i) => {
    const url = urls[parseInt(i)]
    return `<a href="${url}" target="_blank" rel="noopener" class="text-blue-600 underline break-all">${url}</a>`
  })
  // 5. Newlines
  msg = msg.replace(/\n/g, '<br>')
  return msg
}

// Notification sound using Web Audio API (no file needed)
let _audioCtx = null
function playNotificationSound() {
  try {
    if (!_audioCtx) _audioCtx = new (window.AudioContext || window.webkitAudioContext)()
    const ctx = _audioCtx
    // Resume suspended AudioContext (browsers require user interaction first)
    if (ctx.state === 'suspended') {
      ctx.resume()
    }
    const now = ctx.currentTime
    // Two-tone chime (like WhatsApp)
    const playTone = (freq, start, dur) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0.45, start)
      gain.gain.exponentialRampToValueAtTime(0.01, start + dur)
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start(start)
      osc.stop(start + dur)
    }
    playTone(880, now, 0.18)
    playTone(1320, now + 0.15, 0.18)
  } catch (_) {
    // Audio not available
  }
}

// Desktop notifications for incoming messages
function requestNotificationPermission() {
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission()
  }
}

function showDesktopNotification(data) {
  if (!('Notification' in window) || Notification.permission !== 'granted') return

  const msg = data.message || {}
  const chatJid = data.chat_jid || ''
  // Resolve contact name from chat list
  const chat = chatList.data?.find((c) => c.jid === chatJid)
  const title = chat?.contact_name || data.phone || __('New WhatsApp Message')
  const body = msg.message || msg.content_type || ''

  const notification = new Notification(title, {
    body,
    icon: chat?.photo_url || '/assets/crm/frontend/images/whatsapp.png',
    tag: chatJid,
  })
  notification.onclick = () => {
    window.focus()
    if (chat) selectChat(chat)
    notification.close()
  }
}

// Realtime updates via socket
let syncInterval = null

onMounted(() => {
  requestNotificationPermission()
  loadTemplates()
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
        // Desktop notification + sound for unseen incoming messages
        if (data.message?.type === 'Incoming') {
          playNotificationSound()
          showDesktopNotification(data)
        }
      }
    }
  })

  // 5s fallback sync for chat list — also triggers message reload
  // for selected chat if new messages detected (covers missed socket events)
  syncInterval = setInterval(() => {
    chatList.reload()
  }, 5000)
})

onBeforeUnmount(() => {
  $socket.off('whatsapp_chat_update')
  if (syncInterval) clearInterval(syncInterval)
  document.removeEventListener('click', hideContextMenu)
})
</script>
