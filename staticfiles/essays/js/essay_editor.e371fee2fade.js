// essays/static/essays/js/essay_editor.js
// essays/static/essays/js/essay_editor.js
// essays/static/essays/js/essay_editor.js
(function() {
    // --- FULLSCREEN PROCTORING & STRICT ANTI-CHEAT ---
    const overlay = document.getElementById('fullscreen-overlay');
    const essayContainer = document.getElementById('essay-container');
    const startModal = document.getElementById('start-modal');
    const warningBadge = document.getElementById('warning-badge');
    const warningCountSpan = document.getElementById('warning-count');
    const MAX_WARNINGS = 2;
    let warningCount = 0;
    let isReloading = false;
    let isTransitioning = false;
    let timerInterval;
    let timeLeft = parseInt(document.getElementById('timer-count') ? document.getElementById('timer-count').textContent : ({{ topic.time_limit_minutes|default:30 }} * 60));

    function isFullscreen() {
        return document.fullscreenElement || document.webkitFullscreenElement || document.mozFullScreenElement || document.msFullscreenElement;
    }
    function showOverlay() {
        overlay.style.display = 'flex';
        essayContainer.style.filter = 'blur(10px)';
    }
    function hideOverlay() {
        overlay.style.display = 'none';
        essayContainer.style.filter = 'none';
    }
    function enterEssay() {
        isTransitioning = true;
        const elem = document.documentElement;
        const requestFS = elem.requestFullscreen || elem.webkitRequestFullscreen || elem.mozRequestFullScreen || elem.msRequestFullscreen;
        if (requestFS) {
            requestFS.call(elem).then(() => {
                startModal.style.display = 'none';
                essayContainer.style.display = 'block';
                hideOverlay();
                startEssayLogic();
                setTimeout(() => { isTransitioning = false; }, 1000);
            }).catch(() => {
                alert('Full screen is required for this essay. Please allow it.');
                isTransitioning = false;
            });
        }
    }
    window.enterEssay = enterEssay;
    window.returnToFullscreen = function() {
        enterEssay();
    };

    function startEssayLogic() {
        // UI Setup
        hideOverlay();
        // Timer
        timerInterval = setInterval(() => {
            timeLeft--;
            document.getElementById('timer').innerText = formatTime(timeLeft);
            if (timeLeft <= 0) finishEssay(true);
        }, 1000);
        document.getElementById('timer').innerText = formatTime(timeLeft);
    }

    function formatTime(seconds) {
        let m = Math.floor(seconds / 60);
        let s = seconds % 60;
        return `${m}:${s < 10 ? '0' : ''}${s}`;
    }

    // --- STRICT PROCTORING: Tab/Focus/Context Menu ---
    document.addEventListener('fullscreenchange', checkFullscreenStatus);
    document.addEventListener('webkitfullscreenchange', checkFullscreenStatus);
    document.addEventListener('mozfullscreenchange', checkFullscreenStatus);
    document.addEventListener('MSFullscreenChange', checkFullscreenStatus);

    function checkFullscreenStatus() {
        if (isTransitioning) return;
        if (!isFullscreen()) {
            showOverlay();
            essayContainer.style.display = 'none';
        } else {
            hideOverlay();
            essayContainer.style.display = 'block';
        }
    }

    setInterval(() => {
        if (essayContainer.style.display === 'block') {
            checkFullscreenStatus();
        }
    }, 500);

    document.addEventListener('visibilitychange', () => {
        if (document.hidden && !isReloading && essayContainer.style.display === 'block') {
            triggerWarning('Tab switching is prohibited!');
        }
    });
    window.addEventListener('blur', () => {
        if (!isReloading && essayContainer.style.display === 'block') {
            triggerWarning('Focus lost! Did you switch applications?');
        }
    });
    window.addEventListener('beforeunload', () => { isReloading = true; });
    document.addEventListener('contextmenu', e => {
        if (essayContainer.style.display === 'block') e.preventDefault();
    });

    function triggerWarning(reason) {
        warningCount++;
        warningBadge.style.display = 'inline-block';
        warningCountSpan.textContent = warningCount;
        alert(`WARNING ${warningCount}/${MAX_WARNINGS}: ${reason}`);
        if (warningCount > MAX_WARNINGS) {
            finishEssay(true);
        }
    }

    // --- AUTOSAVE, COUNTERS, SUBMISSION ---
    let lastSavedContent = document.getElementById('essay-content').value;
    let lastSaveTime = 0;
    let autosaveInterval = 30000; // 30 sec
    let saveInProgress = false;
    let autosaveStatus = document.getElementById('autosave-status');
    let essayForm = document.getElementById('essayForm');
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

    ['copy', 'cut', 'paste'].forEach(function(evt) {
        textarea.addEventListener(evt, function(e) {
            e.preventDefault();
            autosaveStatus.textContent = 'Copy, cut, and paste are disabled during this essay.';
        });
    });

    textarea.addEventListener('input', function() {
        updateCounters();
    });

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

    window.finishEssay = function(auto = false) {
        isReloading = true;
        clearInterval(timerInterval);
        if (auto) alert('Essay Auto-Submitted.');
        essayForm.submit();
    };

})();

  // --- AUTOSAVE, TIMER, COUNTERS ---
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
  let timerInterval = setInterval(tick, 1000);
  function tick() {
    if (timerSeconds > 0) {
      timerSeconds--;
      timerCount.textContent = timerSeconds;
      if (timerSeconds === 0) {
        submitBtn.disabled = true;
        autosaveStatus.textContent = 'Time expired. Essay will be auto-submitted.';
        essayForm.submit();
      }
    }
  }

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
