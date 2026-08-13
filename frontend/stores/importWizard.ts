import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { ImportPreview } from '~/types/imports'

export type ImportWizardStep =
  | 'idle'
  | 'file-selected'
  | 'uploading'
  | 'validation-ready'
  | 'committing'
  | 'complete'
  | 'error'

export const useImportWizardStore = defineStore('import-wizard', () => {
  const step = ref<ImportWizardStep>('idle')
  const file = ref<File | null>(null)
  const preview = ref<ImportPreview | null>(null)
  const message = ref<string | null>(null)

  const canCommit = computed(
    () => step.value === 'validation-ready' && preview.value?.status === 'validated',
  )

  function selectFile(value: File): void {
    file.value = value
    preview.value = null
    message.value = null
    step.value = 'file-selected'
  }

  function startUpload(): void {
    if (!file.value) throw new Error('Select a workbook first')
    step.value = 'uploading'
  }

  function setPreview(value: ImportPreview): void {
    preview.value = value
    step.value = 'validation-ready'
  }

  function startCommit(): void {
    if (!canCommit.value) throw new Error('The batch is not ready to commit')
    step.value = 'committing'
  }

  function complete(text: string): void {
    message.value = text
    step.value = 'complete'
  }

  function fail(text: string): void {
    message.value = text
    step.value = 'error'
  }

  function reset(): void {
    step.value = 'idle'
    file.value = null
    preview.value = null
    message.value = null
  }

  return {
    step,
    file,
    preview,
    message,
    canCommit,
    selectFile,
    startUpload,
    setPreview,
    startCommit,
    complete,
    fail,
    reset,
  }
})
