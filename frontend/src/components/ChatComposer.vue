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
        <template v-slot="{ openFileSelector, uploading, progress }">
          <div class="flex items-center space-x-2">
            <div
              v-if="uploading"
              class="flex items-center gap-1.5 text-xs text-ink-gray-5"
              :title="__('Uploading...')"
            >
              <LoadingIndicator class="h-3.5 w-3.5" />
              <span>{{ progress }}%</span>
            </div>
            <Dropdown v-else :options="uploadOptions(openFileSelector)">
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
    />
    <Button
      variant="solid"
      icon="send"
      class="mb-0.5 shrink-0"
      @click="submit()"
    />
  </div>
</template>

<script setup>
import IconPicker from '@/components/IconPicker.vue'
import SmileIcon from '@/components/Icons/SmileIcon.vue'
import {
  Textarea,
  FileUploader,
  Dropdown,
  LoadingIndicator,
} from 'frappe-ui'
import { ref, watch } from 'vue'

defineProps({
  phone: String,
  jid: String,
})

// Single event: parent owns the API call and optimistic update
const emit = defineEmits(['submit'])

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
  submit()
}

function submit() {
  const message = content.value
  const content_type = fileType.value || 'text'
  const attach = attachUrl.value || ''
  const reply_to = reply.value?.name || ''

  // Reset composer state before emitting so UI clears instantly
  content.value = ''
  fileType.value = ''
  attachUrl.value = ''
  reply.value = {}

  emit('submit', { message, content_type, attach, reply_to })
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
