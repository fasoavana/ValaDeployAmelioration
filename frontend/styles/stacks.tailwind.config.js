// stacks.tailwind.config.js
// Configuration Tailwind extraite du nouveau design (design tokens : couleurs,
// radius, spacing, typographie).

tailwind.config = {
    darkMode: "class",
    theme: {
        extend: {
            colors: {
                "secondary-fixed": "#e2e2e2",
                "on-error-container": "#93000a",
                "surface-variant": "#d9e3fb",
                "error-container": "#ffdad6",
                "surface-bright": "#f9f9ff",
                "tertiary-container": "#0096fd",
                "primary": "#a73a00",
                "surface-container-high": "#dfe8ff",
                "secondary": "#5e5e5e",
                "on-surface-variant": "#5b4137",
                "on-tertiary": "#ffffff",
                "on-secondary-fixed-variant": "#474747",
                "on-tertiary-container": "#002d51",
                "secondary-container": "#e2e2e2",
                "error": "#ba1a1a",
                "secondary-fixed-dim": "#c6c6c6",
                "primary-fixed-dim": "#ffb59a",
                "tertiary-fixed": "#d2e4ff",
                "tertiary": "#0061a6",
                "outline": "#8f7065",
                "on-primary-container": "#521800",
                "primary-container": "#ff5c00",
                "inverse-on-surface": "#ecf0ff",
                "on-background": "#111c2d",
                "on-error": "#ffffff",
                "on-primary": "#ffffff",
                "on-secondary-fixed": "#1b1b1b",
                "on-tertiary-fixed-variant": "#00497f",
                "on-secondary": "#ffffff",
                "inverse-primary": "#ffb59a",
                "surface-dim": "#d0daf2",
                "on-secondary-container": "#646464",
                "surface-tint": "#a73a00",
                "on-surface": "#111c2d",
                "on-primary-fixed": "#370e00",
                "inverse-surface": "#273143",
                "surface-container": "#e8eeff",
                "surface-container-highest": "#d9e3fb",
                "outline-variant": "#e4beb1",
                "background": "#f9f9ff",
                "on-tertiary-fixed": "#001c37",
                "surface": "#f9f9ff",
                "on-primary-fixed-variant": "#802a00",
                "surface-container-low": "#f0f3ff",
                "tertiary-fixed-dim": "#a0c9ff",
                "primary-fixed": "#ffdbce",
                "surface-container-lowest": "#ffffff"
            },
            borderRadius: {
                "DEFAULT": "0.125rem",
                "lg": "0.25rem",
                "xl": "0.5rem",
                "full": "0.75rem"
            },
            spacing: {
                "xs": "4px",
                "margin-mobile": "16px",
                "md": "16px",
                "unit": "4px",
                "margin-desktop": "32px",
                "max-width": "1280px",
                "xxl": "80px",
                "lg": "24px",
                "sm": "8px",
                "gutter": "24px",
                "xl": "40px"
            },
            fontFamily: {
                "body-md": ["Inter", "sans-serif"],
                "mono-code": ["JetBrains Mono", "monospace"],
                "body-lg": ["Inter", "sans-serif"],
                "label-md": ["Inter", "sans-serif"],
                "headline-lg": ["Inter", "sans-serif"],
                "headline-lg-mobile": ["Inter", "sans-serif"],
                "body-sm": ["Inter", "sans-serif"],
                "label-sm": ["Inter", "sans-serif"],
                "display": ["Inter", "sans-serif"],
                "headline-md": ["Inter", "sans-serif"]
            },
            fontSize: {
                "body-md": ["16px", { "lineHeight": "24px", "fontWeight": "400" }],
                "mono-code": ["14px", { "lineHeight": "20px", "fontWeight": "400" }],
                "body-lg": ["18px", { "lineHeight": "28px", "fontWeight": "400" }],
                "label-md": ["14px", { "lineHeight": "20px", "fontWeight": "500" }],
                "headline-lg": ["32px", { "lineHeight": "40px", "letterSpacing": "-0.02em", "fontWeight": "600" }],
                "headline-lg-mobile": ["24px", { "lineHeight": "32px", "letterSpacing": "-0.01em", "fontWeight": "600" }],
                "body-sm": ["14px", { "lineHeight": "20px", "fontWeight": "400" }],
                "label-sm": ["12px", { "lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "600" }],
                "display": ["48px", { "lineHeight": "56px", "letterSpacing": "-0.02em", "fontWeight": "700" }],
                "headline-md": ["24px", { "lineHeight": "32px", "letterSpacing": "-0.01em", "fontWeight": "600" }]
            }
        }
    }
};