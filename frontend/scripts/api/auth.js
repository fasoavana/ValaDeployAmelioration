// scripts/api/auth.js
// Fonctions d'appel à l'API d'authentification (register, login...)
function extractErrorMessage(errorBody) {
  const detail = errorBody.detail;

  if (typeof detail === "string") {
    // Cas HTTPException(detail="...") -> déjà une string simple
    return detail;
  }

  if (Array.isArray(detail)) {
    // Cas erreur Pydantic (422) -> liste d'objets {loc, msg, ...}
    // .map() transforme chaque erreur en une ligne "champ: message"
    // .join("\n") assemble le tableau en une seule string, une erreur par ligne
    return detail
      .map(err => `${err.loc[err.loc.length - 1]}: ${err.msg}`)
      .join("\n");
  }

  return "Une erreur est survenue.";
}

// Fonction commune : transforme une réponse fetch en JSON,
// ou lance une erreur (avec le status HTTP attaché) si ça a échoué
function handleResponse(response) {
    if (!response.ok) {
        // Lire la réponse en texte pour voir ce que c'est
        return response.text().then(function(text) {
            console.log('Réponse brute (erreur) :', text);
            
            // Essayer de parser en JSON si possible
            try {
                var errorBody = JSON.parse(text);
                var error = new Error(extractErrorMessage(errorBody));
                error.status = response.status;
                throw error;
            } catch (e) {
                // Si ce n'est pas du JSON, utiliser le texte brut
                var error = new Error(text || 'Erreur ' + response.status);
                error.status = response.status;
                throw error;
            }
        });
    }
    
    // Pour les réponses OK, lire en texte d'abord pour debug
    return response.text().then(function(text) {
        console.log('Réponse brute (OK) :', text);
        try {
            return JSON.parse(text);
        } catch (e) {
            console.error('La réponse n\'est pas du JSON valide:', text);
            throw new Error('Le serveur a renvoyé une réponse invalide: ' + text.substring(0, 100));
        }
    });
}

function registerUser(fullname, email, password, confirmPassword) {
  return fetch("http://app.localhost:8080/api/auth/register", {
    method: "POST",
    headers: {
      "Content-Type": "application/json" // pour indiquer le type de donne a envoyer
    },
    body: JSON.stringify({ 
        full_name : fullname, 
        email: email, 
        password: password, 
        confirm_password: confirmPassword }) 
  })
    .then(handleResponse)
   // reponse http brute pas le corps
    .then(data => data);
}


function loginUser(email, password) {
  return fetch("http://app.localhost:8080/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include", // indispensable pour que le cookie refresh_token soit accepté/stocké
    body: JSON.stringify({ email, password })
  })
    .then(handleResponse)
      .then(data => {
      // AJOUT : On stocke le token immédiatement pour les appels suivants
      currentAccessToken = data.access_token; 
      return data;
    });
}


function refreshAccessToken() {
  return fetch("http://app.localhost:8080/api/auth/refresh", {
    method: "POST",
    credentials: "include"
  })
    .then(handleResponse);
}

function getCurrentUser(accessToken) {
  return fetch("http://app.localhost:8080/api/auth/me", {
    method: "GET",
    headers: {
      "Authorization": "Bearer " + accessToken // n'utilise pas le cookies, mais le header(convention)
    }
  })
    .then(handleResponse);
}

function logoutUser() {
  return fetch("http://app.localhost:8080/api/auth/logout", {
    method: "POST",
    credentials: "include"
  }).then(handleResponse);
}

function changePassword(oldPassword, newPassword) {
  return fetch("http://app.localhost:8080/api/auth/change-password", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + currentAccessToken
    },
    body: JSON.stringify({ 
      old_password: oldPassword, 
      new_password: newPassword 
    })
  }).then(handleResponse);
}

let currentAccessToken = null;

// Décode le "payload" (2e partie) d'un JWT, sans vérifier sa signature
// (on n'a pas besoin de vérifier : c'est le rôle du backend, ici on veut juste LIRE des infos, comme "exp")
function decodeJwt(token) {
  const payloadBase64Url = token.split('.')[1];
  const payloadBase64 = payloadBase64Url.replace(/-/g, '+').replace(/_/g, '/');
  const payloadJson = atob(payloadBase64); // atob = décode du base64 en texte
  return JSON.parse(payloadJson);
}

// Enveloppe un appel API : si le token est invalide/expiré (401), rafraîchit et réessaie une fois
function fetchWithAutoRefresh(apiCallFn) {
  return apiCallFn(currentAccessToken)
    .catch(error => {
      if (error.status === 401) {
        return refreshAccessToken().then(data => {
          currentAccessToken = data.access_token;
          return apiCallFn(currentAccessToken);
        });
      }
      throw error;
    });
}

// Point d'entrée commun à toute page qui a besoin de connaître l'utilisateur connecté.
// onSuccess(user, accessToken) est appelé si tout va bien.
// onFailure(error) est appelé si la session est invalide (à toi de rediriger vers login.html dedans).
function initUserSession(onSuccess, onFailure) {
  refreshAccessToken()
    .then(data => {
      currentAccessToken = data.access_token;
      return fetchWithAutoRefresh(getCurrentUser);
    })
    .then(user => {
      onSuccess(user, currentAccessToken);
    })
    .catch(error => {
      onFailure(error);
    });
}