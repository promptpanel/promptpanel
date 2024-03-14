/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["../../**/*.{html,js}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#2D72D2",
          dark: "#2D72D2",
        },
      },
      screens: {
        "-2xl": { max: "1536px" },
        "-xl": { max: "1280px" },
        "-lg": { max: "1024px" },
        "-md": { max: "768px" },
        "-sm": { max: "640px" },
      },
      fontFamily: {
        sans: ["-apple-system, ui-sans-serif,  system-ui"],
      },
      listStyleType: {
        square: "square",
      },
    },
  },
  plugins: [require("@tailwindcss/typography"), require("@tailwindcss/aspect-ratio"), require("@tailwindcss/container-queries")],
};
