//frontend/scripts/project-detail.js
let currentToken = null;
let currentSlug = null;
let currentComponentId = null;

document.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(window.location.search);
  currentSlug = params.get('slug');
  currentComponentId = params.get('component_id');

  if (!currentSlug) {
    const nameEl = document.getElementById('project-name');
    if (nameEl) nameEl.textContent = 'No project specified';
    return;
  }

  document.title = `ValaDeploy - ${currentSlug}`;
  const nameEl = document.getElementById('project-name');
  if (nameEl) nameEl.textContent = currentSlug;

  initUserSession(
    (user, accessToken) => {
      currentToken = accessToken;
      console.log("Session valide, chargement pour:", currentSlug, currentComponentId ? `composant ${currentComponentId}` : 'projet complet');
      
      // 1. Récupérer et afficher le vrai statut depuis la BDD
      fetchAndSetInitialStatus(currentSlug, currentComponentId);
      
      // 2. Démarrer les logs
      startLogsStream(currentSlug, currentComponentId, currentToken);
      
      // 3. Charger les variables d'environnement (une seule fois)
      loadEnvVars(currentSlug);
      
      // 4. Configurer les boutons
      setupControlButtons(currentSlug, currentComponentId);
    },
    (error) => {
      console.error('Erreur lors de l\'initialisation:', error);
      if (error.message && (error.message.includes('Session expirée') || error.message.includes('401'))) {
         window.location.href = 'login.html';
      }
    }
  );
});

// --- Récupération du statut réel ---
function fetchAndSetInitialStatus(slug, componentId) {
    getProjects().then(projects => {
        const project = projects.find(p => p.slug === slug);
        if (!project) return;

        let finalStatus = project.status;

        // Si c'est un composant spécifique, on va chercher son statut à lui
        if (componentId && project.id) {
            getStackDetail(project.id).then(detail => {
                const comp = detail.components.find(c => c.id == componentId);
                finalStatus = comp ? comp.status : project.status;
                updateStatusUI(finalStatus);
                // Démarrer le polling des métriques selon le statut
                startMetricsPolling(slug, finalStatus);
            }).catch(() => {
                updateStatusUI(project.status);
                startMetricsPolling(slug, project.status);
            });
        } else {
            updateStatusUI(finalStatus);
            // Démarrer le polling des métriques selon le statut
            startMetricsPolling(slug, finalStatus);
        }
    }).catch(err => console.error("Échec récupération statut:", err));
}

function updateStatusUI(status) {
  const container = document.getElementById('status-badge-container');
  const dot = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  if (!container || !dot || !text) return;

  // Reset des classes de base
  container.className = 'flex items-center gap-xs px-2 py-1 rounded border font-label-sm text-label-sm uppercase tracking-wider';
  dot.className = 'w-2 h-2 rounded-full';
  
  const statusLower = (status || 'unknown').toLowerCase();

  if (statusLower === 'running') {
    container.classList.add('bg-[#12B76A]/10', 'text-[#12B76A]', 'border-[#12B76A]/20');
    dot.classList.add('bg-[#12B76A]');
    text.textContent = 'Running';
  } else if (statusLower === 'stopped') {
    container.classList.add('bg-gray-500/10', 'text-gray-500', 'border-gray-500/20');
    dot.classList.add('bg-gray-500');
    text.textContent = 'Stopped';
  } else if (statusLower === 'building') {
    container.classList.add('bg-blue-500/10', 'text-blue-500', 'border-blue-500/20');
    dot.classList.add('bg-blue-500', 'animate-pulse');
    text.textContent = 'Building';
  } else if (statusLower === 'failed') {
    container.classList.add('bg-red-500/10', 'text-red-500', 'border-red-500/20');
    dot.classList.add('bg-red-500');
    text.textContent = 'Failed';
  } else {
    container.classList.add('bg-gray-500/10', 'text-gray-500', 'border-gray-500/20');
    dot.classList.add('bg-gray-500');
    text.textContent = status || 'Unknown';
  }
}

// --- Logs ---
function startLogsStream(slug, componentId, accessToken) {
  const terminal = document.getElementById('log-terminal');
  const indicator = document.getElementById('live-indicator');
  if (!terminal || !indicator) return;

  connectLogsWebSocket(slug, componentId, accessToken, {
    onOpen: () => {
      indicator.classList.remove('disconnected');
      indicator.classList.add('connected');
      appendLogLine(terminal, `--- Connected to ${slug} ---`, 'meta');
    },
    onMessage: (data) => {
      appendLogLine(terminal, data, 'default');
    },
    onClose: () => {
      indicator.classList.remove('connected');
      indicator.classList.add('disconnected');
      appendLogLine(terminal, '--- Connection closed ---', 'meta');
    },
    onTokenExpired: (newAccessToken) => {
      currentToken = newAccessToken;
      startLogsStream(slug, componentId, currentToken);
    },
    onError: () => {
      appendLogLine(terminal, '--- Connection error ---', 'error');
    },
  });
}

function appendLogLine(terminal, text, kind) {
  const line = document.createElement('div');
  if (kind === 'meta') line.className = 'text-[#666]';
  if (kind === 'error') line.className = 'text-error';
  line.textContent = text;
  terminal.appendChild(line);
  terminal.scrollTop = terminal.scrollHeight;
}

// --- Start / Stop / Restart ---
function setupControlButtons(slug, componentId) {
  const btnStop = document.getElementById('btn-stop');
  const btnRestart = document.getElementById('btn-restart');
  const btnStart = document.getElementById('btn-start');
  const terminal = document.getElementById('log-terminal');

    const callAction = async (action) => {
    // Désactiver les boutons
    [btnStop, btnRestart, btnStart].forEach(btn => { if(btn) btn.disabled = true; });
    appendLogLine(terminal, `--- Demande d'action: ${action.toUpperCase()} ---`, 'meta');

    try {
      const result = await executeProjectAction(slug, action, componentId);
      
      //Gestion robuste : si result est null ou n'a pas de message, on met un message par défaut(sinon les logs ne continueront pas à s'afficher correctement)
      const successMessage = (result && result.message) ? result.message : `Action '${action}' traitée avec succès`;
      appendLogLine(terminal, `--- SUCCÈS: ${successMessage} ---`, 'meta');
      
      const actionLabel = action === 'stop' ? 'arrêté' : (action === 'start' ? 'démarré' : 'redémarré');
      ValaToast.show({ 
          type: 'success', 
          title: 'Action réussie', 
          message: `Le conteneur a bien été ${actionLabel}.` 
      });

      // 1. Mettre à jour le badge de statut immédiatement (optimiste)
      const newStatus = (action === 'stop') ? 'stopped' : 'running';
      updateStatusUI(newStatus);

       //  Mettre à jour le polling des métriques selon la nouvelle action
      refreshMetricsForStatus(slug, newStatus);

      // 2. Reconnecter les logs automatiquement après un start ou restart
      if (action === 'start' || action === 'restart') {
         appendLogLine(terminal, `--- Reconnexion aux logs en cours (délai de 2s)... ---`, 'meta');
         setTimeout(() => {
            startLogsStream(slug, componentId, currentToken);
         }, 2000); // 2 secondes pour laisser le temps au conteneur de démarrer
      }
      
    } catch (error) {
      console.error("Erreur détaillée lors de l'action:", error);
      appendLogLine(terminal, `--- ÉCHEC: ${error.message || 'Erreur inconnue du serveur'} ---`, 'error');
      ValaToast.show({ 
          type: 'error', 
          title: 'Échec de l\'action', 
          message: error.message || 'Le serveur a refusé l\'action.' 
      });
    } finally {
      // Réactiver les boutons dans tous les cas
      [btnStop, btnRestart, btnStart].forEach(btn => { if(btn) btn.disabled = false; });
    }
  };

  if (btnStop) btnStop.addEventListener('click', () => callAction('stop'));
  if (btnRestart) btnRestart.addEventListener('click', () => callAction('restart'));
  if (btnStart) btnStart.addEventListener('click', () => callAction('start'));
}

// ============ METRICS & ENV VARS ============

let metricsPollingInterval = null;
const METRICS_POLL_INTERVAL = 5000; // 5 secondes

/**
 * Démarre le polling des métriques (uniquement si projet running)
 */
function startMetricsPolling(slug, currentStatus) {
    stopMetricsPolling(); // Sécurité : éviter les doublons
    
    if (currentStatus !== 'running') {
        renderMetricsUnavailable();
        return;
    }
    
    // Premier chargement immédiat
    loadMetrics(slug);
    
    // Puis polling toutes les 5s
    metricsPollingInterval = setInterval(() => {
        loadMetrics(slug);
    }, METRICS_POLL_INTERVAL);
}

/**
 * Arrête le polling
 */
function stopMetricsPolling() {
    if (metricsPollingInterval) {
        clearInterval(metricsPollingInterval);
        metricsPollingInterval = null;
    }
}

/**
 * Charge les métriques depuis l'API
 */
function loadMetrics(slug) {
    getProjectMetrics(slug)
        .then(data => {
            renderMetrics(data);
        })
        .catch(err => {
            console.error('Erreur chargement métriques:', err);
            renderMetricsError();
        });
}

/**
 * Affiche les métriques dans le DOM
 */
function renderMetrics(data) {
    const cpuValue = document.getElementById('cpu-value');
    const memValue = document.getElementById('mem-value');
    const cpuBar = document.getElementById('cpu-bar');
    const memBar = document.getElementById('mem-bar');
    const statusText = document.getElementById('metrics-status');
    
    if (!cpuValue || !memValue || !cpuBar || !memBar) return;
    
    if (data.container_count === 0) {
        renderMetricsUnavailable();
        return;
    }
    
    // CPU
    const cpuPercent = Math.min(data.total_cpu_percent, 100); // Cap à 100%
    cpuValue.textContent = `${cpuPercent.toFixed(1)}%`;
    cpuBar.style.width = `${cpuPercent}%`;
    
    // Couleur CPU selon charge
    cpuBar.className = 'h-full transition-all duration-500 ';
    if (cpuPercent > 80) cpuBar.classList.add('bg-red-500');
    else if (cpuPercent > 50) cpuBar.classList.add('bg-orange-500');
    else cpuBar.classList.add('bg-primary-container');
    
    // Memory
    memValue.textContent = data.memory_usage_formatted;
    const memPercent = data.total_memory_limit > 0 
        ? (data.total_memory_usage / data.total_memory_limit) * 100 
        : 0;
    memBar.style.width = `${Math.min(memPercent, 100)}%`;
    
    // Couleur mémoire selon charge
    memBar.className = 'h-full transition-all duration-500 ';
    if (memPercent > 80) memBar.classList.add('bg-red-500');
    else if (memPercent > 50) memBar.classList.add('bg-orange-500');
    else memBar.classList.add('bg-tertiary-container');
    
    // Status text
    if (statusText) {
        statusText.textContent = `${data.container_count} conteneur(s) actif(s) • Mis à jour à l'instant`;
        statusText.classList.remove('text-error');
        statusText.classList.add('text-secondary');
    }
}

/**
 * Affiche l'état "indisponible" (projet stopped)
 */
function renderMetricsUnavailable() {
    const cpuValue = document.getElementById('cpu-value');
    const memValue = document.getElementById('mem-value');
    const cpuBar = document.getElementById('cpu-bar');
    const memBar = document.getElementById('mem-bar');
    const statusText = document.getElementById('metrics-status');
    
    if (cpuValue) cpuValue.textContent = '0%';
    if (memValue) memValue.textContent = '0B / 0B';
    if (cpuBar) cpuBar.style.width = '0%';
    if (memBar) memBar.style.width = '0%';
    
    if (statusText) {
        statusText.textContent = 'Projet arrêté — aucune métrique disponible';
        statusText.classList.remove('text-error');
        statusText.classList.add('text-secondary');
    }
}

/**
 * Affiche une erreur de chargement
 */
function renderMetricsError() {
    const statusText = document.getElementById('metrics-status');
    if (statusText) {
        statusText.textContent = ' Error loading metrics';
        statusText.classList.add('text-error');
    }
}

/**
 * Charge et affiche les variables d'environnement
 */
function loadEnvVars(slug) {
    const container = document.getElementById('env-vars-container');
    if (!container) return;
    
    getProjectEnvVars(slug)
        .then(data => {
            renderEnvVars(container, data.variables);
        })
        .catch(err => {
            console.error('Erreur chargement env vars:', err);
            container.innerHTML = '<div class="text-error text-body-sm">⚠ Impossible to load environment variables.</div>';
        });
}

/**
 * Rend les variables d'environnement dans le DOM
 */
function renderEnvVars(container, variables) {
    if (!variables || variables.length === 0) {
        container.innerHTML = '<div class="text-secondary text-body-sm italic">No environment variables defined.</div>';
        return;
    }
    
    container.innerHTML = '';
    
    variables.forEach(envVar => {
        const div = document.createElement('div');
        div.className = 'group flex flex-col p-sm rounded border border-transparent hover:border-outline-variant hover:bg-surface-container-lowest transition-all';
        
        const keySpan = document.createElement('span');
        keySpan.className = 'font-mono-code text-[12px] text-secondary';
        keySpan.textContent = envVar.key;
        
        const valueWrapper = document.createElement('div');
        valueWrapper.className = 'flex items-center justify-between gap-2';
        
        const valueSpan = document.createElement('span');
        valueSpan.className = 'font-mono-code text-body-sm text-on-surface truncate';
        valueSpan.textContent = envVar.value;
        valueSpan.id = `env-value-${envVar.key}`;
        
        valueWrapper.appendChild(valueSpan);
        
        // Bouton eye pour les vars sensibles (pour le moment, juste visuel)
        if (envVar.is_sensitive) {
            const eyeBtn = document.createElement('button');
            eyeBtn.className = 'text-secondary opacity-0 group-hover:opacity-100 transition-opacity';
            eyeBtn.title = 'Révéler la valeur (bientôt)';
            eyeBtn.innerHTML = '<span class="material-symbols-outlined text-[16px]">visibility</span>';
            eyeBtn.addEventListener('click', () => {
                ValaToast.show({ 
                    type: 'info', 
                    title: 'This feature is coming soon', 
                    message: 'The revelation of sensitive values will be available soon.' 
                });
            });
            valueWrapper.appendChild(eyeBtn);
        }
        
        div.appendChild(keySpan);
        div.appendChild(valueWrapper);
        container.appendChild(div);
    });
}

/**
 * Met à jour le polling des métriques quand le statut change
 * (appelée après une action start/stop/restart)
 */
function refreshMetricsForStatus(slug, newStatus) {
    if (newStatus === 'running') {
        startMetricsPolling(slug, 'running');
    } else {
        stopMetricsPolling();
        renderMetricsUnavailable();
    }
}