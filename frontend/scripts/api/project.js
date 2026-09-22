// scripts/api/project.js
// API pour les projets et les stacks - FONCTIONS GLOBALES

// Fallback robuste : utilise API_BASE_URL si défini, sinon l'origine actuelle
const VALA_API_URL = (typeof API_BASE_URL !== 'undefined') ? API_BASE_URL : window.location.origin;

function getProjects() {
    return fetchWithAutoRefresh(function(token) {
        return fetch(`${VALA_API_URL}/api/projects`, {
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(handleResponse);
    });
}

function createProject(projectData) {
    return fetchWithAutoRefresh(function(token) {
        return fetch(`${VALA_API_URL}/api/deploy`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify(projectData)
        }).then(handleResponse);
    });
}

function getDeployStatus(projectId) {
    return fetchWithAutoRefresh(function(token) {
        return fetch(`${VALA_API_URL}/api/deploy/${projectId}/status`, {
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(handleResponse);
    });
}

function getDashboardStats() {
    return fetchWithAutoRefresh(function(token) {
        return fetch(`${VALA_API_URL}/api/projects/dashboard/stats`, {
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(handleResponse);
    });
}

function deleteProject(projectId) {
    return fetchWithAutoRefresh(function(token) {
        return fetch(`${VALA_API_URL}/api/projects/${projectId}`, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(handleResponse);
    });
}

// ---------- STACKS ----------

function getStacks() {
    return fetchWithAutoRefresh(function(token) {
        return fetch(`${VALA_API_URL}/api/deploy/stacks`, {
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(handleResponse);
    });
}

function getStackDetail(projectId) {
    return fetchWithAutoRefresh(function(token) {
        return fetch(`${VALA_API_URL}/api/deploy/stack/${projectId}/status`, {
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(handleResponse);
    });
}

function deleteStack(projectId) {
    return fetchWithAutoRefresh(function(token) {
        return fetch(`${VALA_API_URL}/api/deploy/stack/${projectId}`, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(handleResponse);
    });
}

// ---------- ACTIONS (Start / Stop / Restart) ----------

function executeProjectAction(slug, action, componentId) {
    let url = `${VALA_API_URL}/api/projects/${slug}/action?action=${action}`;
    if (componentId) {
        url += `&component_id=${componentId}`;
    }

    return fetchWithAutoRefresh(function(token) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/json'
            }
        }).then(handleResponse);
    });
}

// --- METRICS & ENV VARS (Ajouter à la fin de project.js) ---

function getProjectMetrics(slug) {
    return fetchWithAutoRefresh(function(token) {
        return fetch(`${VALA_API_URL}/api/projects/${slug}/metrics`, {
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(handleResponse);
    });
}

function getProjectEnvVars(slug) {
    return fetchWithAutoRefresh(function(token) {
        return fetch(`${VALA_API_URL}/api/projects/${slug}/env-vars`, {
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(handleResponse);
    });
}