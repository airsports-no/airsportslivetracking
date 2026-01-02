module.exports = {
  content: [
    // Path to your Django templates
    './src/display/templates/**/*.html', 
    './src/templates/**/*.html',
    
    // Path to your React components
    './react_vite/index.html',
    './react_vite/src/**/*.{js,jsx,ts,tsx}', 
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require("daisyui"), // or require('flowbite/plugin')
  ],
  daisyui: {
    themes: ["light", "dark"],
  },
}