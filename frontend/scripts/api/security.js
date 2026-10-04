// scripts/api/security.js
// Appel à l'API du rapport de sécurité d'un projet

function getSecurityList() {
    return fetchWithAutoRefresh(accessToken =>
        fetch(`http://app.localhost:8080/api/security`, {
            method: "GET",
            headers: { "Authorization": "Bearer " + accessToken }
        }).then(handleResponse)
    );
}

function getSecurityReport(slug) {
    return fetchWithAutoRefresh(accessToken =>
        fetch(`http://app.localhost:8080/api/security/${slug}`, {
            method: "GET",
            headers: {
                "Authorization": "Bearer " + accessToken
            }
        }).then(handleResponse)
    );
}

function getPendingSecurityConfirmation(projectId) {
  return fetchWithAutoRefresh(accessToken =>
    fetch(`http://app.localhost:8080/api/security/${projectId}/pending-confirmation`, {
      method: "GET",
      headers: { "Authorization": "Bearer " + accessToken }
    }).then(handleResponse)
  );
}

function confirmSecurityDeployment(projectId) {
  return fetchWithAutoRefresh(accessToken =>
    fetch(`http://app.localhost:8080/api/security/${projectId}/confirm`, {
      method: "POST",
      headers: { "Authorization": "Bearer " + accessToken }
    }).then(handleResponse)
  );
}

function rejectSecurityDeployment(projectId) {
  return fetchWithAutoRefresh(accessToken =>
    fetch(`http://app.localhost:8080/api/security/${projectId}/reject`, {
      method: "POST",
      headers: { "Authorization": "Bearer " + accessToken }
    }).then(handleResponse)
  );
}

// Continuous Vulnerability Monitoring

function getVulnerabilityScanHistory(projectId, componentId = null) {
  return fetchWithAutoRefresh(accessToken =>
    fetch(`http://app.localhost:8080/api/security/${projectId}/scans${componentId !== null ? '?component_id=' + encodeURIComponent(componentId) : ''}`, {
      method: "GET",
      headers: { "Authorization": "Bearer " + accessToken }
    }).then(handleResponse)
  );
}

function getVulnerabilityScanComparison(projectId, componentId = null) {
  return fetchWithAutoRefresh(accessToken =>
    fetch(`http://app.localhost:8080/api/security/${projectId}/scans/compare${componentId !== null ? '?component_id=' + encodeURIComponent(componentId) : ''}`, {
      method: "GET",
      headers: { "Authorization": "Bearer " + accessToken }
    }).then(handleResponse)
  );
}

function rescanSecurityProject(projectId, componentId = null) {
  return fetchWithAutoRefresh(accessToken =>
    fetch(`http://app.localhost:8080/api/security/${projectId}/rescan${componentId !== null ? '?component_id=' + encodeURIComponent(componentId) : ''}`, {
      method: "POST",
      headers: { "Authorization": "Bearer " + accessToken }
    }).then(handleResponse)
  );
}
