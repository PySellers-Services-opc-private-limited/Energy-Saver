/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#edfff5',
          100: '#d5ffe8',
          200: '#aeffd3',
          300: '#70ffb3',
          400: '#2bef87',
          500: '#06d669',
          600: '#00b054',
          700: '#008a43',
          800: '#006b36',
          900: '#00572c',
        },
      },
    },
  },
  plugins: [],
}
