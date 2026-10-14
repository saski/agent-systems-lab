/* Checkpoint Verification Module
 * Allows viewers to compare saved checkpoint files against current history.
 */
(() => {
  'use strict';

  class LabCheckpoint {
    constructor() {
      this.state = null;
      this.generation = 0;
      this.savedFile = null;
      this.savedData = null;
      this.verificationResult = null;
      this.message = null;
      this.requestVersion = 0;
      this.pendingAbort = null;
      this.hostBuilt = false;
    }

    render(state) {
      const prevGeneration = this.generation;
      this.state = state;
      this.generation = state.generation;

      if (this.generation !== prevGeneration) {
        this.clearAll();
      }

      const container = document.getElementById('learning-checkpoint');
      if (!container) return;

      if (!this.hostBuilt) {
        this.buildHost(container);
        this.hostBuilt = true;
      }

      this.updateUI();
    }

    reset() {
      this.savedFile = null;
      this.savedData = null;
      this.verificationResult = null;
      this.message = null;
      this.state = null;
      if (this.pendingAbort) {
        this.pendingAbort.abort();
        this.pendingAbort = null;
      }
      this.requestVersion++;
      const container = document.getElementById('learning-checkpoint');
      if (container) {
        container.replaceChildren();
        this.hostBuilt = false;
      }
    }

    clearAll() {
      if (this.pendingAbort) {
        this.pendingAbort.abort();
        this.pendingAbort = null;
      }
      this.requestVersion++;
      this.savedFile = null;
      this.savedData = null;
      this.verificationResult = null;
      this.message = null;
    }

    buildHost(container) {
      container.replaceChildren();

      const controls = document.createElement('div');
      controls.className = 'checkpoint-controls';

      const explanation = document.createElement('p');
      explanation.className = 'control-note';
      explanation.textContent = 'Each event has a linked digital fingerprint. A database owner can rewrite the chain. Keep a checkpoint outside this database to detect earlier changes.';
      controls.appendChild(explanation);

      const label = document.createElement('label');
      label.textContent = 'Saved checkpoint file';
      label.className = 'checkpoint-label';

      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'application/json';
      input.id = 'checkpoint-file-input';
      input.addEventListener('change', (e) => this.handleFileChange(e));

      label.appendChild(input);
      controls.appendChild(label);

      const compareBtn = document.createElement('button');
      compareBtn.textContent = 'Compare saved checkpoint';
      compareBtn.className = 'button';
      compareBtn.id = 'checkpoint-compare-btn';
      compareBtn.addEventListener('click', () => this.handleCompare());
      controls.appendChild(compareBtn);

      const clearBtn = document.createElement('button');
      clearBtn.textContent = 'Clear';
      clearBtn.className = 'button button-quiet';
      clearBtn.id = 'checkpoint-clear-btn';
      clearBtn.addEventListener('click', () => this.handleClear());
      controls.appendChild(clearBtn);

      const resultDiv = document.createElement('div');
      resultDiv.className = 'checkpoint-result';
      resultDiv.id = 'checkpoint-result';
      resultDiv.setAttribute('role', 'status');
      controls.appendChild(resultDiv);

      container.appendChild(controls);
    }

    handleFileChange(event) {
      this.clearAll();

      const file = event.target.files?.[0];
      if (!file) {
        this.savedFile = null;
        this.savedData = null;
        this.updateUI();
        return;
      }

      if (file.size > 16384) {
        this.showError('Choose a valid checkpoint JSON file (up to 16KB).');
        this.savedFile = null;
        this.savedData = null;
        event.target.value = '';
        return;
      }

      this.savedFile = file;
      this.showStatus('Reading checkpoint...');
      const currentVersion = this.requestVersion;

      const reader = new FileReader();
      reader.onload = (e) => {
        if (this.requestVersion !== currentVersion) return;

        try {
          const json = JSON.parse(e.target.result);
          if (!this.validateCheckpoint(json)) {
            this.showError('Choose a valid checkpoint JSON file (up to 16KB).');
            this.savedFile = null;
            this.savedData = null;
            const input = document.getElementById('checkpoint-file-input');
            if (input) input.value = '';
            return;
          }

          this.savedData = {
            checked: json.checked,
            head_hash: json.head_hash
          };

          this.message = null;
          this.updateUI();
        } catch {
          this.showError('Choose a valid checkpoint JSON file (up to 16KB).');
          this.savedFile = null;
          this.savedData = null;
          const input = document.getElementById('checkpoint-file-input');
          if (input) input.value = '';
        }
      };

      reader.onerror = () => {
        if (this.requestVersion !== currentVersion) return;
        this.showError('Choose a valid checkpoint JSON file (up to 16KB).');
        this.savedFile = null;
        this.savedData = null;
        const input = document.getElementById('checkpoint-file-input');
        if (input) input.value = '';
      };

      reader.readAsText(file);
    }

    validateCheckpoint(json) {
      if (typeof json !== 'object' || json === null) return false;
      if (json.valid !== true) return false;
      if (!Number.isSafeInteger(json.checked) || json.checked < 0) return false;
      if (typeof json.head_hash !== 'string') return false;
      if (!/^[0-9a-f]{64}$/i.test(json.head_hash)) return false;
      return true;
    }

    handleClear() {
      this.clearAll();
      const input = document.getElementById('checkpoint-file-input');
      if (input) input.value = '';
      this.updateUI();
    }

    async handleCompare() {
      if (!this.canCompare()) return;

      this.verificationResult = null;
      this.showStatus('Comparing...');

      const controller = new AbortController();
      this.pendingAbort = controller;
      const currentVersion = this.requestVersion;

      try {
        const response = await fetch('/history/verify', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${this.state.token}`
          },
          body: JSON.stringify({
            checked: this.savedData.checked,
            head_hash: this.savedData.head_hash
          }),
          cache: 'no-store',
          signal: controller.signal
        });

        if (this.requestVersion !== currentVersion) return;

        if (response.status === 401) {
          this.showError('Viewer access expired. Reconnect before comparing.');
          return;
        }

        if (!response.ok) {
          this.showError('Comparison unavailable. Try again when connected.');
          return;
        }

        const result = await response.json();

        if (this.requestVersion !== currentVersion) return;

        if (typeof result.valid !== 'boolean' ||
            !Number.isSafeInteger(result.checked) ||
            typeof result.head_hash !== 'string') {
          this.showError('Comparison unavailable. Try again when connected.');
          return;
        }

        this.verificationResult = result;
        this.message = null;
        this.updateUI();

      } catch (err) {
        if (this.requestVersion !== currentVersion) return;
        if (err.name === 'AbortError') return;
        this.showError('Comparison unavailable. Try again when connected.');
      } finally {
        if (this.requestVersion === currentVersion) {
          this.pendingAbort = null;
          this.updateUI();
        }
      }
    }

    canCompare() {
      return this.savedData &&
             this.state?.token &&
             this.state?.connected &&
             !this.state?.stale &&
             !this.pendingAbort;
    }

    updateUI() {
      const compareBtn = document.getElementById('checkpoint-compare-btn');
      const clearBtn = document.getElementById('checkpoint-clear-btn');
      const resultDiv = document.getElementById('checkpoint-result');

      if (!compareBtn || !clearBtn || !resultDiv) return;

      compareBtn.disabled = !this.canCompare();
      clearBtn.disabled = !this.savedFile;

      resultDiv.replaceChildren();

      if (this.message) {
        const msgEl = document.createElement('p');
        msgEl.className = this.message.kind === 'error' ? 'verification-error' : '';
        msgEl.textContent = this.message.text;
        resultDiv.appendChild(msgEl);
      }

      if (!this.verificationResult) return;

      const { valid } = this.verificationResult;
      const savedChecked = this.savedData.checked;
      const currentTotal = this.state?.integrity?.checked ?? 0;

      const resultText = document.createElement('p');

      if (valid) {
        resultText.textContent = `Saved checkpoint matches the history through event ${savedChecked}. Later events are checked too.`;
        resultText.className = 'verification-success';
      } else {
        resultText.textContent = 'History does not match this checkpoint. Investigate before trusting it.';
        resultText.className = 'verification-failure';
      }

      resultDiv.appendChild(resultText);

      if (this.state?.stale && valid) {
        const staleNotice = document.createElement('p');
        staleNotice.className = 'control-note';
        staleNotice.textContent = 'Result from last fresh connection. Current data is stale.';
        resultDiv.appendChild(staleNotice);
      }

      const details = document.createElement('p');
      details.className = 'control-note';
      details.textContent = `Saved at event ${savedChecked}. Current total: ${currentTotal}.`;
      resultDiv.appendChild(details);
    }

    showError(message) {
      this.message = { kind: 'error', text: message };
      this.updateUI();
    }

    showStatus(message) {
      this.message = { kind: 'status', text: message };
      this.updateUI();
    }
  }

  const instance = new LabCheckpoint();
  globalThis.LabCheckpoint = {
    render: (state) => instance.render(state),
    reset: () => instance.reset()
  };
})();
