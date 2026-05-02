module.exports = {
  content: ["./src/gui/web/**/*.{html,js}"],
  theme: {
    extend: {
      colors: {
        // Atelier Lightbox palette
        bg:        '#F4EFE6',  // warm paper cream
        surface:   '#FFFFFF',
        surface2:  '#F8F4ED',  // off-white
        ink: {
          DEFAULT: '#1F1A14',  // deep charcoal
          soft:    '#3D362D',
        },
        muted:     '#7A7166',  // warm grey
        line:      '#E5DCC9',  // hairline border
        accent:    '#4A1F38',  // deep aubergine
        gold:      '#A8814E',  // muted gold (darker than dark-mode gold for contrast vs cream)
        gold2:     '#C5A46A',
        // Legacy aliases so old class names don't break
        primary:   { DEFAULT: '#A8814E' },
        text:      { primary: '#1F1A14', muted: '#7A7166', dim: '#9C9388' },
      },
      borderRadius: { DEFAULT: '0.5rem', lg: '1rem', xl: '1.5rem', '2xl': '2rem', full: '9999px' },
      fontFamily: {
        sans:  ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Noto Sans TC', 'PingFang TC', 'Microsoft JhengHei', 'sans-serif'],
        body:  ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Noto Sans TC', 'PingFang TC', 'sans-serif'],
        mono:  ['JetBrains Mono', 'Menlo', 'Consolas', 'monospace'],
      },
      boxShadow: {
        soft:  '0 4px 24px -8px rgba(31,26,20,0.10)',
        card:  '0 12px 32px -12px rgba(31,26,20,0.16)',
        deep:  '0 24px 60px -20px rgba(31,26,20,0.24)',
      },
    },
  },
  plugins: [],
};
