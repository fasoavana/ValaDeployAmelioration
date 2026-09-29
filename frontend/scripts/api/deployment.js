// scripts/api/deployment.js

function getDeploymentHistory(projectId) {
    return fetchWithAutoRefresh(function(token) {
        const timestamp = new Date().getTime();
        return fetch(`http://app.localhost:8080/api/projects/${projectId}/deployments?t=${timestamp}`, {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + token,
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        }).then(handleResponse);
    });
}

function getDeploymentRunDetails(projectId, runId) {
    return fetchWithAutoRefresh(function(token) {
        return fetch(`http://app.localhost:8080/api/projects/${projectId}/deployments/${runId}`, {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + token
            }
        }).then(handleResponse);
    });
}

// Liste globale de tous les runs, tous projets confondus, pour l'utilisateur connecte.
// Necessite la route backend GET /api/deployments (voir routers/deployment.py).
function getAllDeployments() {
    return fetchWithAutoRefresh(function(token) {
        const timestamp = new Date().getTime();
        return fetch(`http://app.localhost:8080/api/deployments?t=${timestamp}`, {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + token,
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        }).then(handleResponse);
    });
}