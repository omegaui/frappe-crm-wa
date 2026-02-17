<template>
  <Dialog
    v-model="show"
    :options="{ title: __('Create new user') }"
    @close="show = false"
  >
    <template #body-content>
      <div class="flex gap-1 border rounded mb-4 p-2 text-ink-gray-5">
        <FeatherIcon name="info" class="size-3.5 mt-0.5" />
        <p class="text-p-sm">
          {{
            __(
              'Create a new user with a password. They can log in immediately without email verification.',
            )
          }}
        </p>
      </div>

      <div class="flex flex-col gap-3">
        <FormControl
          v-model="form.email"
          :label="__('Email')"
          :placeholder="__('john@example.com')"
          type="email"
        />
        <div class="flex gap-3">
          <FormControl
            v-model="form.first_name"
            :label="__('First name')"
            :placeholder="__('John')"
            class="flex-1"
          />
          <FormControl
            v-model="form.last_name"
            :label="__('Last name')"
            :placeholder="__('Doe')"
            class="flex-1"
          />
        </div>
        <FormControl
          v-model="form.password"
          :label="__('Password')"
          :placeholder="__('Enter password')"
          type="password"
        />
        <FormControl
          type="select"
          v-model="form.role"
          :label="__('Role')"
          :options="roleOptions"
          :description="description"
        />
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button
          variant="solid"
          :label="__('Create')"
          :disabled="!canSubmit"
          @click="createUser.submit()"
          :loading="createUser.loading"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { usersStore } from '@/stores/users'
import { createResource, toast } from 'frappe-ui'
import { ref, computed, reactive } from 'vue'

const { users, isAdmin, isManager } = usersStore()

const show = defineModel()

const form = reactive({
  email: '',
  first_name: '',
  last_name: '',
  password: '',
  role: 'Sales User',
})

const canSubmit = computed(() => {
  return form.email && form.first_name && form.password
})

const description = computed(() => {
  return {
    'System Manager':
      'Can manage all aspects of the CRM, including user management, customizations and settings.',
    'Sales Manager':
      'Can manage and invite new users, and create public & private views (reports).',
    'Sales User':
      'Can work with leads and deals and create private views (reports).',
  }[form.role]
})

const roleOptions = computed(() => {
  return [
    { value: 'Sales User', label: __('Sales user') },
    ...(isManager() ? [{ value: 'Sales Manager', label: __('Manager') }] : []),
    ...(isAdmin() ? [{ value: 'System Manager', label: __('Admin') }] : []),
  ]
})

const createUser = createResource({
  url: 'crm.api.user.create_crm_user',
  makeParams: () => ({
    email: form.email,
    first_name: form.first_name,
    last_name: form.last_name,
    password: form.password,
    role: form.role,
  }),
  onSuccess: () => {
    toast.success(__('User {0} created successfully', [form.email]))
    form.email = ''
    form.first_name = ''
    form.last_name = ''
    form.password = ''
    form.role = 'Sales User'
    show.value = false
    users.reload()
  },
  onError: (error) => {
    toast.error(error.messages?.[0] || __('Failed to create user'))
  },
})
</script>
