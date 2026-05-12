const chatWindow = document.getElementById('chat-window');
const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const suggestionChips = document.getElementById('suggestion-chips');

const STORAGE_KEY = 'ai-recruitment-session-id';
let sessionId = sessionStorage.getItem(STORAGE_KEY);
if (!sessionId) {
  sessionId = `browser-${Math.random().toString(36).slice(2, 10)}`;
  sessionStorage.setItem(STORAGE_KEY, sessionId);
}

function addMessage(text, role, options = {}) {
  const el = document.createElement('div');
  el.className = `message ${role}`;
  if (options.error) {
    el.classList.add('message-error');
  }
  el.textContent = text;
  chatWindow.appendChild(el);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function setSendingState(isSending) {
  sendButton.disabled = isSending;
  messageInput.disabled = isSending;
  const label = sendButton.querySelector('.send-label');
  if (label) {
    label.textContent = isSending ? 'Sending…' : 'Send';
  }
}

async function sendMessage(message) {
  const trimmed = message.trim();
  if (!trimmed) return;

  addMessage(trimmed, 'user');
  messageInput.value = '';
  setSendingState(true);

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message: trimmed }),
    });

    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }

    const payload = await response.json();
    addMessage(payload.response || 'No response returned from the system.', 'bot');
  } catch (error) {
    addMessage(`Something went wrong: ${error.message}`, 'bot', { error: true });
  } finally {
    setSendingState(false);
    messageInput.focus();
  }
}

addMessage(
  "Hi — I'm your recruitment agent for this demo. Ask in plain language for jobs (role, city, salary, experience), " +
    'send a follow-up to refine filters, or say e.g. “Compare AI Engineer and Data Scientist”.',
  'bot',
);

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;
  await sendMessage(message);
});

if (suggestionChips) {
  suggestionChips.addEventListener('click', (event) => {
    const chip = event.target.closest('.chip');
    if (!chip || chip.disabled) return;
    const text = chip.getAttribute('data-message');
    if (!text) return;
    messageInput.value = text;
    messageInput.focus();
    void sendMessage(text);
  });
}
