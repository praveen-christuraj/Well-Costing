// Node 22+ provides Object.groupBy. This fallback keeps lint usable on older bootstrap
// machines while the documented and CI runtime remains Node 22 LTS.
if (!Object.groupBy) {
  Object.groupBy = (items, callback) => {
    const result = Object.create(null)
    let index = 0
    for (const item of items) {
      const key = callback(item, index++)
      ;(result[key] ||= []).push(item)
    }
    return result
  }
}

const { default: withNuxt } = await import('./.nuxt/eslint.config.mjs')

export default withNuxt({
  rules: {
    'vue/multi-word-component-names': 'off',
  },
})
