/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: { 950: '#061724', 900: '#0a2234', 800: '#103149', 700: '#16415f' },
        clinical: { 50: '#ecfeff', 100: '#cffafe', 400: '#22d3ee', 500: '#06b6d4', 600: '#0891b2' },
      },
      boxShadow: { card: '0 12px 30px rgba(15, 42, 62, 0.07)' },
    },
  },
  plugins: [],
}

