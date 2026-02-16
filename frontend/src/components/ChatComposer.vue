<template>
  <div
    v-if="reply?.message"
    class="flex items-center justify-around gap-2 px-3 pt-2 sm:px-10"
  >
    <div
      class="mb-1 ml-13 flex-1 cursor-pointer rounded border-0 border-l-4 bg-surface-gray-2 p-2 text-base text-ink-gray-5"
      :class="reply.type == 'Incoming' ? 'border-green-500' : 'border-blue-400'"
    >
      <div
        class="mb-1 text-sm font-bold"
        :class="
          reply.type == 'Incoming' ? 'text-ink-green-2' : 'text-ink-blue-link'
        "
      >
        {{ reply.from_name || __('You') }}
      </div>
      <div class="max-h-12 overflow-hidden" v-html="reply.message" />
    </div>
    <Button variant="ghost" icon="x" @click="reply = {}" />
  </div>
  <div class="flex items-end gap-2 px-3 py-2.5 sm:px-10">
    <div class="flex h-8 items-center gap-2">
      <FileUploader @success="(file) => uploadFile(file)">
        <template v-slot="{ openFileSelector }">
          <div class="flex items-center space-x-2">
            <Dropdown :options="uploadOptions(openFileSelector)">
              <FeatherIcon
                name="plus"
                class="size-4.5 cursor-pointer text-ink-gray-5"
              />
            </Dropdown>
          </div>
        </template>
      </FileUploader>
      <IconPicker
        v-model="emoji"
        v-slot="{ togglePopover }"
        @update:modelValue="
          () => {
            content += emoji
            $refs.textareaRef.el.focus()
          }
        "
      >
        <SmileIcon
          @click="togglePopover"
          class="flex size-4.5 cursor-pointer rounded-sm text-xl leading-none text-ink-gray-4"
        />
      </IconPicker>
    </div>
    <Textarea
      ref="textareaRef"
      type="textarea"
      class="min-h-8 w-full"
      :rows="rows"
      v-model="content"
      :placeholder="__('Type your message here...')"
      @focus="rows = 6"
      @blur="rows = 1"
      @keydown.enter.stop="(e) => sendTextMessage(e)"
    />
  </div>
</template>

<script setup>
import IconPicker from '@/components/IconPicker.vue'
import SmileIcon from '@/components/Icons/SmileIcon.vue'
import {
  createResource,
  Textarea,
  FileUploader,
  Dropdown,
  toast,
} from 'frappe-ui'
import { ref, watch } from 'vue'

const props = defineProps({
  phone: String,
  jid: String,
})

const emit = defineEmits(['sent'])

const reply = defineModel('reply')

const rows = ref(1)
const textareaRef = ref(null)
const emoji = ref('')
const content = ref('')
const fileType = ref('')
const attachUrl = ref('')

function uploadFile(file) {
  attachUrl.value = file.file_url
  fileType.value = fileType.value || 'document'
  sendWhatsAppMessage()
}

function sendTextMessage(event) {
  if (event.shiftKey) return
  sendWhatsAppMessage()
  textareaRef.value.el?.blur()
  content.value = ''
}

async function sendWhatsAppMessage() {
  const args = {
    phone: props.phone,
    jid: props.jid || '',
    message: content.value,
    attach: attachUrl.value || '',
    content_type: fileType.value || 'text',
    reply_to: reply.value?.name || '',
  }
  content.value = ''
  fileType.value = ''
  attachUrl.value = ''
  reply.value = {}
  createResource({
    url: 'crm.api.whatsapp.send_chat_message',
    params: args,
    auto: true,
    onSuccess: () => emit('sent'),
    onError: (error) => {
      toast.error(error.messages?.[0] || __('Failed to send WhatsApp message'))
    },
  })
}

function uploadOptions(openFileSelector) {
  return [
    {
      label: __('Upload document'),
      icon: 'file',
      onClick: () => {
        fileType.value = 'document'
        openFileSelector()
      },
    },
    {
      label: __('Upload image'),
      icon: 'image',
      onClick: () => {
        fileType.value = 'image'
        openFileSelector('image/*')
      },
    },
    {
      label: __('Upload video'),
      icon: 'video',
      onClick: () => {
        fileType.value = 'video'
        openFileSelector('video/*')
      },
    },
  ]
}

watch(reply, (value) => {
  if (value?.message) {
    textareaRef.value?.el?.focus()
  }
})

defineExpose({
  focus: () => textareaRef.value?.el?.focus(),
})
</script>
