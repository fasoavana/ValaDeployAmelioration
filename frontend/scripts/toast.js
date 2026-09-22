// scripts/toast.js
// API globale pour les notifications Toast
// Usage : ValaToast.show({ type: 'error', title: 'Échec', message: 'Dockerfile introuvable' });

const ValaToast = (() => {
    // Configuration des variantes
    const VARIANTS = {
        error: {
            icon: 'error',
            colorClass: 'text-danger-red',
            titleDefault: 'Erreur'
        },
        success: {
            icon: 'check_circle',
            colorClass: 'text-success-green',
            titleDefault: 'Succès'
        },
        warning: {
            icon: 'warning',
            colorClass: 'text-warning-orange',
            titleDefault: 'Attention'
        },
        info: {
            icon: 'info',
            colorClass: 'text-primary',
            titleDefault: 'Information'
        }
    };

    function getContainer() {
        return document.getElementById('vala-toast-container');
    }

    function show({ type = 'info', title, message, duration = 5000 }) {
        const container = getContainer();
        if (!container) {
            console.warn('ValaToast : Conteneur introuvable. Ajoutez <div data-component="components/toast-container.html"></div> à votre page.');
            return;
        }

        const config = VARIANTS[type] || VARIANTS.info;
        const toastId = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const finalTitle = title || config.titleDefault;

        // Création du nœud HTML
        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `vala-toast vala-toast--${type}`;
        toast.setAttribute('role', 'alert');
        
        toast.innerHTML = `
            <span class="material-symbols-outlined ${config.colorClass} text-xl shrink-0 mt-0.5">
                ${config.icon}
            </span>
            <div class="flex-1 min-w-0">
                <h4 class="font-label-md text-sm font-semibold text-on-surface mb-0.5">
                    ${finalTitle}
                </h4>
                <p class="font-body-sm text-sm text-on-surface-variant break-words leading-snug">
                    ${message}
                </p>
            </div>
            <button class="vala-toast-close shrink-0 p-1 rounded-md hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface transition-colors" aria-label="Fermer">
                <span class="material-symbols-outlined text-lg">close</span>
            </button>
            <div class="vala-toast-progress" style="animation-duration: ${duration}ms;"></div>
        `;

        // Gestion de la fermeture
        const closeToast = () => {
            toast.classList.remove('vala-toast-visible');
            toast.classList.add('vala-toast-exiting');
            
            // Attendre la fin de l'animation de sortie avant de supprimer du DOM
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 200); // Correspond à transition-duration: 0.2s dans le CSS
        };

        // Événements
        toast.querySelector('.vala-toast-close').addEventListener('click', closeToast);
        
        // Pause de l'animation au survol (UX moderne)
        const progress = toast.querySelector('.vala-toast-progress');
        toast.addEventListener('mouseenter', () => {
            progress.style.animationPlayState = 'paused';
        });
        toast.addEventListener('mouseleave', () => {
            progress.style.animationPlayState = 'running';
        });

        // Injection et animation d'entrée
        container.appendChild(toast);
        
        // Force reflow pour que la transition CSS se déclenche
        requestAnimationFrame(() => {
            toast.classList.add('vala-toast-visible');
        });

        // Auto-fermeture
        if (duration > 0) {
            setTimeout(closeToast, duration);
        }

        return toastId; // Retourne l'ID au cas où on voudrait le fermer manuellement avant
    }

    return { show };
})();

window.ValaToast = ValaToast;