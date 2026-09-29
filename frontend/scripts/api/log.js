// scripts/api/log.js
// Connexion WebSocket vers /logs/{slug} pour le streaming des logs d'un
// conteneur. Ce fichier ne touche PAS au DOM : il expose des callbacks
// (onOpen, onMessage, onClose, onTokenExpired, onError) que l'appelant
// (project-detail.js) branche sur l'UI. Dépend de auth.js (refreshAccessToken,
// currentAccessToken) et de config.js (WS_BASE_URL).

function connectLogsWebSocket(slug, componentId, accessToken, callbacks = {}) {
  const { onOpen, onMessage, onClose, onTokenExpired, onError } = callbacks;

  // Construction propre de l'URL avec les paramètres de requête
  const wsUrl = new URL(`${WS_BASE_URL}/api/logs/${slug}`);
  wsUrl.searchParams.append('token', accessToken);
  
  // Ajoute component_id uniquement s'il est fourni (mode multi-composants)
  if (componentId) {
    wsUrl.searchParams.append('component_id', componentId);
  }

  const ws = new WebSocket(wsUrl.toString());

  ws.onopen = () => {
    onOpen?.();
  };

  ws.onmessage = (event) => {
    onMessage?.(event.data);
  };

  ws.onclose = (event) => {
    if (event.code === 4401) {
      // Token expiré pendant le stream -> on rafraîchit puis on laisse
      // l'appelant décider de reconnecter (via onTokenExpired)
      refreshAccessToken()
        .then(data => {
          currentAccessToken = data.access_token;
          onTokenExpired?.(currentAccessToken);
        })
        .catch(err => {
          onError?.(err);
        });
    } else {
      onClose?.(event);
    }
  };

  ws.onerror = (event) => {
    onError?.(event);
  };

  return ws;
}