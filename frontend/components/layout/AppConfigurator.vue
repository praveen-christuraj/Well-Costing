<script setup lang="ts">
/**
 * Theme configurator, modelled on the PrimeVue Sakai panel.
 *
 * Changes are applied live through `@primeuix/themes` and remembered by
 * `useLayout`, so a chosen preset, primary colour, surface palette, and menu
 * mode survive a reload.
 */
import { onMounted, ref } from 'vue'
import { $t, updatePreset, updateSurfacePalette } from '@primeuix/themes'
import type { Preset } from '@primeuix/themes/types'
import Aura from '@primeuix/themes/aura'
import Lara from '@primeuix/themes/lara'
import Nora from '@primeuix/themes/nora'
import Button from 'primevue/button'
import SelectButton from 'primevue/selectbutton'
import { useLayout } from '~/composables/useLayout'
import type { MenuMode } from '~/composables/useLayout'

type Palette = Record<string, string>

const { layoutConfig, isDarkTheme, changeMenuMode, setPreset, setPrimary, setSurface } = useLayout()

const presets: Record<string, Preset> = { Aura, Lara, Nora }
const presetOptions = Object.keys(presets)
const preset = ref(layoutConfig.preset)

const menuMode = ref<MenuMode>(layoutConfig.menuMode)
const menuModeOptions: { label: string, value: MenuMode }[] = [
  { label: 'Static', value: 'static' },
  { label: 'Overlay', value: 'overlay' },
]

const primaryColors: { name: string, palette: Palette }[] = [
  { name: 'noir', palette: {} },
  { name: 'emerald', palette: { 50: '#ecfdf5', 100: '#d1fae5', 200: '#a7f3d0', 300: '#6ee7b7', 400: '#34d399', 500: '#10b981', 600: '#059669', 700: '#047857', 800: '#065f46', 900: '#064e3b', 950: '#022c22' } },
  { name: 'green', palette: { 50: '#f0fdf4', 100: '#dcfce7', 200: '#bbf7d0', 300: '#86efac', 400: '#4ade80', 500: '#22c55e', 600: '#16a34a', 700: '#15803d', 800: '#166534', 900: '#14532d', 950: '#052e16' } },
  { name: 'teal', palette: { 50: '#f0fdfa', 100: '#ccfbf1', 200: '#99f6e4', 300: '#5eead4', 400: '#2dd4bf', 500: '#14b8a6', 600: '#0d9488', 700: '#0f766e', 800: '#115e59', 900: '#134e4a', 950: '#042f2e' } },
  { name: 'cyan', palette: { 50: '#ecfeff', 100: '#cffafe', 200: '#a5f3fc', 300: '#67e8f9', 400: '#22d3ee', 500: '#06b6d4', 600: '#0891b2', 700: '#0e7490', 800: '#155e75', 900: '#164e63', 950: '#083344' } },
  { name: 'sky', palette: { 50: '#f0f9ff', 100: '#e0f2fe', 200: '#bae6fd', 300: '#7dd3fc', 400: '#38bdf8', 500: '#0ea5e9', 600: '#0284c7', 700: '#0369a1', 800: '#075985', 900: '#0c4a6e', 950: '#082f49' } },
  { name: 'blue', palette: { 50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd', 400: '#60a5fa', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8', 800: '#1e40af', 900: '#1e3a8a', 950: '#172554' } },
  { name: 'indigo', palette: { 50: '#eef2ff', 100: '#e0e7ff', 200: '#c7d2fe', 300: '#a5b4fc', 400: '#818cf8', 500: '#6366f1', 600: '#4f46e5', 700: '#4338ca', 800: '#3730a3', 900: '#312e81', 950: '#1e1b4b' } },
  { name: 'violet', palette: { 50: '#f5f3ff', 100: '#ede9fe', 200: '#ddd6fe', 300: '#c4b5fd', 400: '#a78bfa', 500: '#8b5cf6', 600: '#7c3aed', 700: '#6d28d9', 800: '#5b21b6', 900: '#4c1d95', 950: '#2e1065' } },
  { name: 'amber', palette: { 50: '#fffbeb', 100: '#fef3c7', 200: '#fde68a', 300: '#fcd34d', 400: '#fbbf24', 500: '#f59e0b', 600: '#d97706', 700: '#b45309', 800: '#92400e', 900: '#78350f', 950: '#451a03' } },
  { name: 'orange', palette: { 50: '#fff7ed', 100: '#ffedd5', 200: '#fed7aa', 300: '#fdba74', 400: '#fb923c', 500: '#f97316', 600: '#ea580c', 700: '#c2410c', 800: '#9a3412', 900: '#7c2d12', 950: '#431407' } },
  { name: 'rose', palette: { 50: '#fff1f2', 100: '#ffe4e6', 200: '#fecdd3', 300: '#fda4af', 400: '#fb7185', 500: '#f43f5e', 600: '#e11d48', 700: '#be123c', 800: '#9f1239', 900: '#881337', 950: '#4c0519' } },
]

const surfaces: { name: string, palette: Palette }[] = [
  { name: 'slate', palette: { 0: '#ffffff', 50: '#f8fafc', 100: '#f1f5f9', 200: '#e2e8f0', 300: '#cbd5e1', 400: '#94a3b8', 500: '#64748b', 600: '#475569', 700: '#334155', 800: '#1e293b', 900: '#0f172a', 950: '#020617' } },
  { name: 'gray', palette: { 0: '#ffffff', 50: '#f9fafb', 100: '#f3f4f6', 200: '#e5e7eb', 300: '#d1d5db', 400: '#9ca3af', 500: '#6b7280', 600: '#4b5563', 700: '#374151', 800: '#1f2937', 900: '#111827', 950: '#030712' } },
  { name: 'zinc', palette: { 0: '#ffffff', 50: '#fafafa', 100: '#f4f4f5', 200: '#e4e4e7', 300: '#d4d4d8', 400: '#a1a1aa', 500: '#71717a', 600: '#52525b', 700: '#3f3f46', 800: '#27272a', 900: '#18181b', 950: '#09090b' } },
  { name: 'neutral', palette: { 0: '#ffffff', 50: '#fafafa', 100: '#f5f5f5', 200: '#e5e5e5', 300: '#d4d4d4', 400: '#a3a3a3', 500: '#737373', 600: '#525252', 700: '#404040', 800: '#262626', 900: '#171717', 950: '#0a0a0a' } },
  { name: 'stone', palette: { 0: '#ffffff', 50: '#fafaf9', 100: '#f5f5f4', 200: '#e7e5e4', 300: '#d6d3d1', 400: '#a8a29e', 500: '#78716c', 600: '#57534e', 700: '#44403c', 800: '#292524', 900: '#1c1917', 950: '#0c0a09' } },
  { name: 'ocean', palette: { 0: '#ffffff', 50: '#fbfcfc', 100: '#f7f9f8', 200: '#eff3f2', 300: '#dadedd', 400: '#b1b7b6', 500: '#828787', 600: '#5f7274', 700: '#415b61', 800: '#29444e', 900: '#183240', 950: '#0c1920' } },
]

/** Semantic overrides for the chosen primary colour, as Sakai defines them. */
function presetExtension(): Preset {
  const color = primaryColors.find(candidate => candidate.name === layoutConfig.primary)
    ?? primaryColors[3]!
  if (color.name === 'noir') {
    return {
      semantic: {
        primary: Object.fromEntries(
          [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950].map(shade => [shade, `{surface.${shade}}`]),
        ),
        colorScheme: {
          light: {
            primary: { color: '{primary.950}', contrastColor: '#ffffff', hoverColor: '{primary.800}', activeColor: '{primary.700}' },
            highlight: { background: '{primary.950}', focusBackground: '{primary.700}', color: '#ffffff', focusColor: '#ffffff' },
          },
          dark: {
            primary: { color: '{primary.50}', contrastColor: '{primary.950}', hoverColor: '{primary.200}', activeColor: '{primary.300}' },
            highlight: { background: '{primary.50}', focusBackground: '{primary.300}', color: '{primary.950}', focusColor: '{primary.950}' },
          },
        },
      },
    }
  }
  return {
    semantic: {
      primary: color.palette,
      colorScheme: {
        light: {
          primary: { color: '{primary.500}', contrastColor: '#ffffff', hoverColor: '{primary.600}', activeColor: '{primary.700}' },
          highlight: { background: '{primary.50}', focusBackground: '{primary.100}', color: '{primary.700}', focusColor: '{primary.800}' },
        },
        dark: {
          primary: { color: '{primary.400}', contrastColor: '{surface.900}', hoverColor: '{primary.300}', activeColor: '{primary.200}' },
          highlight: {
            background: 'color-mix(in srgb, {primary.400}, transparent 84%)',
            focusBackground: 'color-mix(in srgb, {primary.400}, transparent 76%)',
            color: 'rgba(255,255,255,.87)',
            focusColor: 'rgba(255,255,255,.87)',
          },
        },
      },
    },
  }
}

function applyPrimary(color: { name: string, palette: Palette }): void {
  setPrimary(color.name)
  updatePreset(presetExtension())
}

function applySurface(surface: { name: string, palette: Palette }): void {
  setSurface(surface.name)
  updateSurfacePalette(surface.palette)
}

function applyPreset(): void {
  setPreset(preset.value)
  const surfacePalette = surfaces.find(surface => surface.name === layoutConfig.surface)?.palette
  $t()
    .preset(presets[preset.value] ?? (Aura as Preset))
    .preset(presetExtension())
    .surfacePalette(surfacePalette)
    .use({ useDefaultOptions: true })
}

function applyMenuMode(): void {
  changeMenuMode(menuMode.value)
}

function isSurfaceSelected(name: string): boolean {
  if (layoutConfig.surface) return layoutConfig.surface === name
  return isDarkTheme.value ? name === 'zinc' : name === 'slate'
}

/** Re-apply the remembered theme so a reload looks like the last session. */
onMounted(() => {
  if (layoutConfig.primary !== 'teal' || layoutConfig.preset !== 'Aura' || layoutConfig.surface) {
    preset.value = layoutConfig.preset
    applyPreset()
  }
})
</script>

<template>
  <div class="config-panel" role="dialog" aria-label="Theme configurator">
    <div class="config-panel__section">
      <span class="config-panel__label">Primary</span>
      <div class="config-panel__swatches">
        <button
          v-for="color in primaryColors"
          :key="color.name"
          type="button"
          :title="color.name"
          :aria-label="`Primary colour ${color.name}`"
          :class="['config-swatch', { 'config-swatch--active': layoutConfig.primary === color.name }]"
          :style="{ backgroundColor: color.name === 'noir' ? 'var(--app-ink)' : color.palette['500'] }"
          @click="applyPrimary(color)"
        />
      </div>
    </div>

    <div class="config-panel__section">
      <span class="config-panel__label">Surface</span>
      <div class="config-panel__swatches">
        <button
          v-for="surface in surfaces"
          :key="surface.name"
          type="button"
          :title="surface.name"
          :aria-label="`Surface palette ${surface.name}`"
          :class="['config-swatch', { 'config-swatch--active': isSurfaceSelected(surface.name) }]"
          :style="{ backgroundColor: surface.palette['500'] }"
          @click="applySurface(surface)"
        />
      </div>
    </div>

    <div class="config-panel__section">
      <span class="config-panel__label">Preset</span>
      <SelectButton v-model="preset" :options="presetOptions" :allow-empty="false" @change="applyPreset" />
    </div>

    <div class="config-panel__section">
      <span class="config-panel__label">Menu mode</span>
      <SelectButton
        v-model="menuMode"
        :options="menuModeOptions"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        @change="applyMenuMode"
      />
    </div>

    <Button label="Reset surface" text size="small" @click="setSurface(null)" />
  </div>
</template>
