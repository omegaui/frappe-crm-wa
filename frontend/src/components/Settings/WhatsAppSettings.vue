<template>
  <div v-if="whatsappBridgeMode">
    <SettingsPage doctype="CRM WhatsApp Bridge Settings" class="p-8" />
    <div class="mt-4 px-8 pb-8">
      <h3 class="text-lg font-semibold text-ink-gray-8 mb-4">
        {{ __('Connection Status') }}
      </h3>
      <div v-if="bridgeStatus?.connected" class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div class="h-2.5 w-2.5 rounded-full bg-green-500" />
          <span class="text-sm font-medium text-green-700">
            {{ __('Connected to WhatsApp') }}
          </span>
        </div>
        <Button
          :label="__('Disconnect')"
          theme="red"
          variant="subtle"
          :loading="actionLoading"
          @click="disconnect"
        />
      </div>
      <div v-else class="flex flex-col items-center gap-4 py-4">
        <div v-if="qrData?.qr_base64" class="flex flex-col items-center gap-3">
          <p class="text-sm text-ink-gray-5 text-center max-w-sm">
            {{ __('On your phone: WhatsApp → Settings → Linked Devices → Link a Device, then scan:') }}
          </p>
          <img :src="qrData.qr_base64" class="w-64 h-64 rounded-lg border" />
          <p class="text-xs text-ink-gray-4">
            {{ __('Waiting for scan… this refreshes automatically.') }}
          </p>
        </div>
        <div v-else class="flex flex-col items-center gap-3">
          <div class="flex items-center gap-2">
            <div class="h-2.5 w-2.5 rounded-full bg-red-500" />
            <span class="text-sm font-medium text-red-700">{{ __('Not connected') }}</span>
          </div>
          <p class="text-sm text-ink-gray-5 text-center max-w-sm">
            {{ __('Click Connect to generate a QR code, then scan it from WhatsApp → Linked Devices.') }}
          </p>
          <Button
            :label="__('Connect / Re-link')"
            variant="solid"
            :loading="actionLoading"
            @click="connect"
          />
        </div>
      </div>
    </div>
  </div>
  <div v-else-if="!loading">
    <SettingsPage doctype="CRM WhatsApp Bridge Settings" class="p-8" />
  </div>
</template>
<script setup>
import SettingsPage from '@/components/Settings/SettingsPage.vue'
import { whatsappBridgeMode } from '@/composables/settings'
import { createResource, toast } from 'frappe-ui'
import { ref, watch, onUnmounted } from 'vue'

const loading = ref(true)
const actionLoading = ref(false)
let pollTimer = null
const bridgeModeCheck = createResource({
  url: 'crm.integrations.whatsapp.handler.is_bridge_enabled',
  auto: true,
  onSuccess: () => { loading.value = false },
  onError: () => { loading.value = false },
})

const bridgeStatus = ref(null)
const qrData = ref(null)

const statusResource = createResource({
  url: 'crm.integrations.whatsapp.handler.get_bridge_status',
  onSuccess: (data) => {
    bridgeStatus.value = data
  },
})

const qrResource = createResource({
  url: 'crm.integrations.whatsapp.handler.get_qr_code',
  onSuccess: (data) => {
    qrData.value = data
  },
})

const relinkResource = createResource({
  url: 'crm.integrations.whatsapp.handler.relink_bridge',
  onSuccess: () => {
    actionLoading.value = false
    toast.success(__('Generating QR code…'))
    startPolling()
  },
  onError: () => {
    actionLoading.value = false
    toast.error(__('Failed to start WhatsApp pairing'))
  },
})

const logoutResource = createResource({
  url: 'crm.integrations.whatsapp.handler.logout_bridge',
  onSuccess: () => {
    actionLoading.value = false
    qrData.value = null
    refreshStatus()
    toast.success(__('Disconnected from WhatsApp'))
  },
  onError: () => {
    actionLoading.value = false
    toast.error(__('Failed to disconnect'))
  },
})

function connect() {
  actionLoading.value = true
  relinkResource.fetch()
}

function disconnect() {
  actionLoading.value = true
  logoutResource.fetch()
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    statusResource.fetch()
    if (!bridgeStatus.value?.connected) qrResource.fetch()
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

watch(bridgeStatus, (s) => {
  if (s?.connected) {
    qrData.value = null
    stopPolling()
  }
})

watch(
  whatsappBridgeMode,
  (enabled) => {
    if (enabled) {
      statusResource.fetch()
      qrResource.fetch()
      startPolling()
    }
  },
  { immediate: true },
)

onUnmounted(stopPolling)

function refreshStatus() {
  statusResource.fetch()
  qrResource.fetch()
}
</script>
