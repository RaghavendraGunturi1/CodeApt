// essays/static/essays/js/essay_editor.js
// essays/static/essays/js/essay_editor.js
(function() {
  // --- FULLSCREEN PROCTORING ---
  const overlay = document.getElementById('fullscreen-overlay');
  const essayContainer = document.getElementById('essay-container');
  function isFullscreen() {
    return document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement;
  }
  function showOverlay() {
    overlay.style.display = 'flex';
    essayContainer.style.filter = 'blur(4px)';
  }
  function hideOverlay() {
    overlay.style.display = 'none';
    essayContainer.style.filter = '';
  }
  function enterEssay() {
    const elem = document.documentElement;
    const requestFS = elem.requestFullscreen || elem.webkitRequestFullscreen || elem.mozRequestFullScreen || elem.msRequestFullscreen;
    if (requestFS) {
      requestFS.call(elem).then(() => {
        essayContainer.style.display = 'block';
        hideOverlay();
      }).catch(() => {
        alert('Full screen is required for this essay. Please allow it.');
      });
    }
  }
  window.returnToFullscreen = function() {
    enterEssay();
  };
  // Hide nav bar and show essay only in full screen
  function hideNavBar() {
    var nav = document.querySelector('nav.navbar, header, .navbar');
    if (nav) nav.style.display = 'none';
  }
  function showNavBar() {
    var nav = document.querySelector('nav.navbar, header, .navbar');
    if (nav) nav.style.display = '';
  }
  // Listen for fullscreen changes and focus/visibility
  function enforceProctoring() {
    if (isFullscreen() && document.visibilityState === 'visible' && document.hasFocus()) {
      hideOverlay();
      essayContainer.style.display = 'block';
      hideNavBar();
    } else {
      showOverlay();
      essayContainer.style.display = 'none';
      showNavBar();
    }
  }
  document.addEventListener('fullscreenchange', enforceProctoring);
  document.addEventListener('visibilitychange', enforceProctoring);
  window.addEventListener('blur', enforceProctoring);
  window.addEventListener('focus', enforceProctoring);
  // On load, force full screen
  window.addEventListener('DOMContentLoaded', function() {
    hideNavBar();
    setTimeout(enterEssay, 300);
    enforceProctoring();
  });


  let lastSavedContent = document.getElementById('essay-content').value;
  let lastSaveTime = 0;
  let autosaveInterval = 30000; // 30 sec
  let saveInProgress = false;
  let timerCount = document.getElementById('timer-count');
  let submitBtn = document.getElementById('submit-btn');
  let autosaveStatus = document.getElementById('autosave-status');
  let essayForm = document.getElementById('essay-form');
  let textarea = document.getElementById('essay-content');

  function updateCounters() {
    let text = textarea.value.trim();
    let words = text ? text.split(/\s+/).length : 0;
    let chars = text.length;
    let paras = text ? text.split(/\n+/).filter(p => p.trim().length > 0).length : 0;
    document.getElementById('word-count').textContent = words;
    document.getElementById('char-count').textContent = chars;
    document.getElementById('para-count').textContent = paras;
  }


  // Block copy, cut, paste for proctoring
  ['copy', 'cut', 'paste'].forEach(function(evt) {
    textarea.addEventListener(evt, function(e) {
      e.preventDefault();
      autosaveStatus.textContent = 'Copy, cut, and paste are disabled during this essay.';
    });
  });

  textarea.addEventListener('input', function() {
    updateCounters();
  });

  // Timer
  let timerSeconds = parseInt(timerCount.textContent);
  function tick() {
    if (timerSeconds > 0) {
      timerSeconds--;
      timerCount.textContent = timerSeconds;
      if (timerSeconds === 0) {
        submitBtn.disabled = true;
        autosaveStatus.textContent = 'Time expired. Essay will be auto-submitted.';
        // Optionally auto-submit
        essayForm.submit();
      }
    }
  }
  setInterval(tick, 1000);

  // Autosave
  function autosave() {
    if (saveInProgress) return;
    let content = textarea.value;
    if (content === lastSavedContent) return;
    let now = Date.now();
    if (now - lastSaveTime < 10000) return; // 10s min interval
    saveInProgress = true;
    autosaveStatus.textContent = 'Saving...';
    fetch(window.location.pathname.replace(/editor\/$/, 'save-draft/'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
      },
      body: JSON.stringify({content: content})
    })
    .then(resp => resp.json())
    .then(data => {
      if (data.success) {
        lastSavedContent = content;
        lastSaveTime = Date.now();
        autosaveStatus.textContent = 'Saved at ' + new Date(data.saved_at).toLocaleTimeString();
        document.getElementById('word-count').textContent = data.word_count;
        document.getElementById('char-count').textContent = data.character_count;
        document.getElementById('para-count').textContent = data.paragraph_count;
      } else {
        autosaveStatus.textContent = 'Autosave failed: ' + (data.error || 'Unknown error');
      }
    })
    .catch(() => {
      autosaveStatus.textContent = 'Network error during autosave.';
    })
    .finally(() => {
      saveInProgress = false;
    });
  }
  setInterval(autosave, autosaveInterval);

  // Debounced typing
  let typingTimer;
  textarea.addEventListener('input', function() {
    clearTimeout(typingTimer);
    typingTimer = setTimeout(autosave, 2000);
  });

  // Warn before leaving
  window.addEventListener('beforeunload', function(e) {
    if (textarea.value !== lastSavedContent) {
      e.preventDefault();
      e.returnValue = '';
    }
  });

  // Submit confirmation
  essayForm.addEventListener('submit', function(e) {
    if (!confirm('Are you sure you want to submit your essay? You cannot edit after submission.')) {
      e.preventDefault();
    }
  });

  updateCounters();
})();
