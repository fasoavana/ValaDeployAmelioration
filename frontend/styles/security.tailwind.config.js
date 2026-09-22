tailwind.config = {
    darkMode: "class",
    theme: {
        extend: {
            "colors": {
                "tertiary-container": "#0096fd",
                "primary-container": "#ff5c00",
                "outline-variant": "#e4beb1",
                "on-secondary-container": "#646464",
                "on-surface": "#111c2d",
                "background": "#f9f9ff",
                "surface": "#f9f9ff",
                "surface-container": "#e8eeff",
                "surface-container-lowest": "#ffffff",
                "primary": "#a73a00",
                "error-container": "#ffdad6",
                "error": "#ba1a1a",
                "on-surface-variant": "#5b4137",
                "surface-container-low": "#f0f3ff",
                "outline": "#8f7065",
                "surface-container-highest": "#d9e3fb",
                "secondary": "#5e5e5e",
                "surface-container-high": "#dfe8ff",
                "on-primary": "#ffffff",
                "on-background": "#111c2d"
            },
            "borderRadius": {
                "DEFAULT": "0.125rem",
                "lg": "0.25rem",
                "xl": "0.5rem",
                "full": "0.75rem"
            },
            "spacing": {
                "xs": "4px",
                "margin-mobile": "16px",
                "sm": "8px",
                "xxl": "80px",
                "xl": "40px",
                "max-width": "1280px",
                "gutter": "24px",
                "md": "16px",
                "margin-desktop": "32px",
                "lg": "24px"
            },
            "fontFamily": {
                "body-md": ["Inter"],
                "headline-lg-mobile": ["Inter"],
                "body-lg": ["Inter"],
                "headline-md": ["Inter"],
                "label-sm": ["Inter"],
                "display": ["Inter"],
                "label-md": ["Inter"],
                "body-sm": ["Inter"],
                "headline-lg": ["Inter"],
                "mono-code": ["JetBrains Mono"]
            },
            "fontSize": {
                "body-md": ["16px", { "lineHeight": "24px", "fontWeight": "400" }],
                "headline-lg-mobile": ["24px", { "lineHeight": "32px", "letterSpacing": "-0.01em", "fontWeight": "600" }],
                "body-lg": ["18px", { "lineHeight": "28px", "fontWeight": "400" }],
                "headline-md": ["24px", { "lineHeight": "32px", "letterSpacing": "-0.01em", "fontWeight": "600" }],
                "label-sm": ["12px", { "lineHeight": "16px", "letterSpacing": "0.05em", "fontWeight": "600" }],
                "display": ["48px", { "lineHeight": "56px", "letterSpacing": "-0.02em", "fontWeight": "700" }],
                "label-md": ["14px", { "lineHeight": "20px", "fontWeight": "500" }],
                "body-sm": ["14px", { "lineHeight": "20px", "fontWeight": "400" }],
                "headline-lg": ["32px", { "lineHeight": "40px", "letterSpacing": "-0.02em", "fontWeight": "600" }],
                "mono-code": ["14px", { "lineHeight": "20px", "fontWeight": "400" }]
            }
        }
    }
}
