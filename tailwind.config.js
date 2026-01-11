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
    themes: [
      "light", 
      "dark",
      {
        aviation: {
          "primary": "#FF8C00",
          "primary-content": "#FFFFFF",
          "secondary": "#FF00FF",
          "secondary-content": "#FFFFFF",
          "accent": "#FF00FF",
          "neutral": "#1A202C",
          "base-100": "#0D1117",
          "base-200": "#1A202C",
          "base-300": "#2d3748",
          "info": "#3ABFF8",
          "success": "#22C55E",
          "warning": "#FBBD23",
          "error": "#EF4444",
        },
      },
    ],
    darkTheme: "aviation",
  },
}