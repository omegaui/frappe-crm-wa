<template>
  <div v-if="whatsappBridgeMode">
    <SettingsPage doctype="CRM WhatsApp Bridge Settings" class="p-8" />
    <div class="mt-4 px-8 pb-8">
      <h3 class="text-lg font-semibold text-ink-gray-8 mb-4">
        {{ __('Connection Status') }}
      </h3>
      <div v-if="bridgeStatus?.connected" class="flex items-center gap-2">
        <div class="h-2.5 w-2.5 rounded-full bg-green-500" />
        <span class="text-sm font-medium text-green-700">
          {{ __('Connected to WhatsApp') }}
        </span>
      </div>
      <div v-else class="flex flex-col items-center gap-4 py-4">
        <div v-if="qrData?.qr_base64" class="flex flex-col items-center gap-3">
          <p class="text-sm text-ink-gray-5">
            {{ __('Scan this QR code with WhatsApp to connect:') }}
          </p>
          <img :src="qrData.qr_base64" class="w-64 h-64 rounded-lg border" />
          <Button
            :label="__('Refresh QR')"
            variant="subtle"
            @click="refreshStatus"
          />
        </div>
        <div v-else-if="qrData?.connected" class="flex items-center gap-2">
          <div class="h-2.5 w-2.5 rounded-full bg-green-500" />
          <span class="text-sm font-medium text-green-700">
            {{ __('Connected to WhatsApp') }}
          </span>
        </div>
        <div v-else class="flex flex-col items-center gap-3">
          <p class="text-sm text-ink-gray-5">
            {{ __('Waiting for QR code from bridge...') }}
          </p>
          <Button
            :label="__('Refresh')"
            variant="subtle"
            @click="refreshStatus"
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
import { createResource } from 'frappe-ui'
import { ref, watch } from 'vue'

const loading = ref(true)
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

watch(
  whatsappBridgeMode,
  (enabled) => {
    if (enabled) {
      statusResource.fetch()
      qrResource.fetch()
    }
  },
  { immediate: true },
)

function refreshStatus() {
  statusResource.fetch()
  qrResource.fetch()
}
</script>
