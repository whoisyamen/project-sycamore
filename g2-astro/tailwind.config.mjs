/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,ts,tsx,vue,svelte}'],
  theme: {
    extend: {
      colors: {
        // From 02-design/DESIGN_SYSTEM.md — dark investigative palette
        ink: {
          900: '#070A0F',  // page base (near-black)
          800: '#0B1018',  // panel base
          700: '#11182A',  // panel raised
          600: '#1A2238',  // borders
          500: '#252F49'   // hover
        },
        cyan: {
          alive: '#3DF7FF'  // only "live" color
        },
        risk: {
          red: '#FF3B5C',   // confirmed critical
          amber: '#F5A524', // watching
          green: '#2EE59D'  // de-escalating
        },
        muted: {
          DEFAULT: '#8A93A6',
          dim: '#5A6378'
        }
      },
      fontFamily: {
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace']
      },
      boxShadow: {
        'panel': '0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)',
        'glow-cyan': '0 0 12px rgba(61,247,255,0.5)',
        'glow-red': '0 0 12px rgba(255,59,92,0.5)'
      },
      keyframes: {
        pulseCyan: {
          '0%,100%': { boxShadow: '0 0 0 0 rgba(61,247,255,0.7)' },
          '50%':     { boxShadow: '0 0 0 8px rgba(61,247,255,0)' }
        },
        marquee: {
          '0%':   { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' }
        }
      },
      animation: {
        'pulse-cyan': 'pulseCyan 2s ease-in-out infinite',
        'marquee':    'marquee 60s linear infinite'
      }
    }
  },
  plugins: []
};
