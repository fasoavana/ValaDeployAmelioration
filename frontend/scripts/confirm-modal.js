// scripts/confirm-modal.js
//
// API globale pour le composant components/confirm-modal.html
//
// Le composant est 100% autonome visuellement : tout le CSS nécessaire
// (couleurs, espacements, radius, police) est injecté ici en dur, sans
// dépendre des tokens Tailwind custom de la page hôte (bg-danger-red,
// text-primary-dark, px-lg, etc.). Ainsi il rend pareil sur toutes les
// pages, quelle que soit leur config Tailwind (account.tailwind.config.js,
// dashboard.tailwind.config.js, ...).
//
// Utilisation :
//   const ok = await ValaModal.confirm({
//       title: "Delete Account",
//       message: "This action is permanent and cannot be undone.",
//       confirmLabel: "Delete Account",
//       cancelLabel: "Cancel",
//       variant: "danger" // ou "default"
//   });
//   if (ok) { /* action confirmée */ }
//
// Le composant doit être présent une seule fois par page :
//   <div data-component="components/confirm-modal.html"></div>

const ValaModal = (() => {
    let resolvePromise = null;

    function injectStyles() {
        if (document.getElementById("vala-modal-styles")) return;

        const style = document.createElement("style");
        style.id = "vala-modal-styles";
        style.textContent = `
            .vala-modal-overlay {
                display: none;
                position: fixed;
                inset: 0;
                z-index: 9999;
                align-items: center;
                justify-content: center;
                background: rgba(0, 0, 0, 0.45);
                backdrop-filter: blur(1px);
                -webkit-backdrop-filter: blur(1px);
                padding: 16px;
                box-sizing: border-box;
            }
            .vala-modal-overlay.vala-modal-open {
                display: flex;
            }

            .vala-modal-card {
                width: 100%;
                max-width: 384px;
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1);
                padding: 24px;
                box-sizing: border-box;
                opacity: 0;
                transform: scale(0.95);
                transition: opacity 150ms ease, transform 150ms ease;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }
            .vala-modal-overlay.vala-modal-visible .vala-modal-card {
                opacity: 1;
                transform: scale(1);
            }

            .vala-modal-icon-wrap {
                width: 44px;
                height: 44px;
                border-radius: 9999px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-bottom: 16px;
            }
            .vala-modal-icon-wrap.vala-modal-icon-wrap-danger {
                background: rgba(220, 38, 38, 0.12);
            }
            .vala-modal-icon-wrap.vala-modal-icon-wrap-default {
                background: #f3f4f6;
            }

            .vala-modal-icon {
                font-size: 22px;
                line-height: 1;
            }
            .vala-modal-icon.vala-modal-icon-danger {
                color: #dc2626;
            }
            .vala-modal-icon.vala-modal-icon-default {
                color: #f97316;
            }

            .vala-modal-title {
                margin: 0 0 4px 0;
                font-size: 18px;
                line-height: 24px;
                font-weight: 600;
                color: #111827;
            }

            .vala-modal-message {
                margin: 0 0 24px 0;
                font-size: 14px;
                line-height: 20px;
                color: #6b7280;
            }

            .vala-modal-actions {
                display: flex;
                justify-content: flex-end;
                gap: 8px;
            }

            .vala-modal-btn {
                font-size: 14px;
                font-weight: 500;
                padding: 8px 20px;
                border-radius: 8px;
                border: 1px solid transparent;
                cursor: pointer;
                transition: opacity 150ms ease, background-color 150ms ease;
                box-sizing: border-box;
            }

            .vala-modal-btn-cancel {
                background: #ffffff;
                border-color: #e5e7eb;
                color: #111827;
            }
            .vala-modal-btn-cancel:hover {
                background: #f3f4f6;
            }

            .vala-modal-btn-confirm.vala-modal-btn-danger {
                background: #dc2626;
                color: #ffffff;
            }
            .vala-modal-btn-confirm.vala-modal-btn-default {
                background: #f97316;
                color: #ffffff;
            }
            .vala-modal-btn-confirm:hover {
                opacity: 0.9;
            }

            body.vala-modal-locked { overflow: hidden; }
        `;
        document.head.appendChild(style);
    }

    injectStyles();

    // Variantes : classes purement internes au composant (vala-modal-*),
    // aucune dépendance à la config Tailwind de la page hôte.
    const VARIANTS = {
        danger: {
            iconWrapClass: "vala-modal-icon-wrap-danger",
            iconClass: "vala-modal-icon-danger",
            icon: "warning",
            confirmClass: "vala-modal-btn-danger"
        },
        default: {
            iconWrapClass: "vala-modal-icon-wrap-default",
            iconClass: "vala-modal-icon-default",
            icon: "help",
            confirmClass: "vala-modal-btn-default"
        }
    };

    function getEls() {
        return {
            overlay: document.getElementById("vala-modal-overlay"),
            iconWrap: document.getElementById("vala-modal-icon-wrap"),
            icon: document.getElementById("vala-modal-icon"),
            title: document.getElementById("vala-modal-title"),
            message: document.getElementById("vala-modal-message"),
            cancelBtn: document.getElementById("vala-modal-cancel"),
            confirmBtn: document.getElementById("vala-modal-confirm")
        };
    }

    function close(result) {
        const { overlay } = getEls();
        if (!overlay) return;

        overlay.classList.remove("vala-modal-visible");
        document.body.classList.remove("vala-modal-locked");

        setTimeout(() => {
            overlay.classList.remove("vala-modal-open");
            overlay.setAttribute("aria-hidden", "true");
        }, 150);

        document.removeEventListener("keydown", onKeydown);

        if (resolvePromise) {
            resolvePromise(result);
            resolvePromise = null;
        }
    }

    function onKeydown(e) {
        if (e.key === "Escape") close(false);
    }

    function confirm({
        title = "Confirmer l'action",
        message = "Êtes-vous sûr de vouloir continuer ?",
        confirmLabel = "Confirmer",
        cancelLabel = "Annuler",
        variant = "default"
    } = {}) {
        const els = getEls();

        if (!els.overlay) {
            console.error("ValaModal : composant introuvable. Vérifiez l'inclusion du HTML.");
            return Promise.resolve(false);
        }

        const style = VARIANTS[variant] || VARIANTS.default;

        els.title.textContent = title;
        els.message.textContent = message;
        els.confirmBtn.textContent = confirmLabel;
        els.cancelBtn.textContent = cancelLabel;

        // Icône
        els.iconWrap.className = "vala-modal-icon-wrap " + style.iconWrapClass;
        els.icon.className = "material-symbols-outlined vala-modal-icon " + style.iconClass;
        els.icon.textContent = style.icon;

        // Bouton confirmer
        els.confirmBtn.className = "vala-modal-btn vala-modal-btn-confirm " + style.confirmClass;

        // Bouton annuler (toujours la même apparence, quelle que soit la variante)
        els.cancelBtn.className = "vala-modal-btn vala-modal-btn-cancel";

        // Clone pour éviter l'accumulation d'écouteurs d'événements
        const newConfirmBtn = els.confirmBtn.cloneNode(true);
        els.confirmBtn.parentNode.replaceChild(newConfirmBtn, els.confirmBtn);

        const newCancelBtn = els.cancelBtn.cloneNode(true);
        els.cancelBtn.parentNode.replaceChild(newCancelBtn, els.cancelBtn);

        newConfirmBtn.addEventListener("click", () => close(true));
        newCancelBtn.addEventListener("click", () => close(false));

        els.overlay.onclick = (e) => {
            if (e.target === els.overlay) close(false);
        };

        els.overlay.classList.add("vala-modal-open");
        els.overlay.setAttribute("aria-hidden", "false");
        document.body.classList.add("vala-modal-locked");
        document.addEventListener("keydown", onKeydown);

        requestAnimationFrame(() => {
            els.overlay.classList.add("vala-modal-visible");
        });

        return new Promise((resolve) => {
            resolvePromise = resolve;
        });
    }

    return { confirm };
})();

window.ValaModal = ValaModal;