// Delegation also covers controls replaced by normal or out-of-band swaps.
function restoreStatus(event) {
  // beforeSwap's elt may be the central error target, not the request source.
  const source = event.detail.requestConfig?.elt || event.detail.elt;
  const control = source?.closest('.status-control');
  control?.querySelectorAll('input[type="radio"]').forEach(function(input) {
    input.checked = input.defaultChecked;
  });
}

function showRequestError(message) {
  const error = document.getElementById('request-error');
  if (message) error.textContent = message;
  error.hidden = false;
  error.scrollIntoView({block: 'nearest'});
}

document.addEventListener('htmx:beforeRequest', function() {
  const error = document.getElementById('request-error');
  error.hidden = true;
  error.replaceChildren();
});

document.addEventListener('htmx:beforeSwap', function(event) {
  const detail = event.detail;
  if (detail.xhr.status < 400 || detail.xhr.status >= 600) return;
  restoreStatus(event);
  const response = new DOMParser().parseFromString(detail.serverResponse, 'text/html');
  if (!response.querySelector('#request-error-content')) {
    // Bare responses and proxy/debug pages must never replace editor content.
    detail.shouldSwap = false;
    showRequestError(document.getElementById('request-error').dataset.errorMessage);
  }
});

document.addEventListener('htmx:afterSwap', function(event) {
  if (event.detail.target.id === 'request-error') showRequestError();
});

document.addEventListener('htmx:sendError', function(event) {
  restoreStatus(event);
  showRequestError(document.getElementById('request-error').dataset.networkMessage);
});
