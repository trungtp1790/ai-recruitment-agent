const chatWindow = document.getElementById('chat-window');
const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message-input');

const sessionId = `browser-${Math.random().toString(36).slice(2, 9)}`;

function addMessage(text, role) {
  const el = document.createElement('div');
  el.className = `message ${role}`;
  el.textContent = text;
  chatWindow.appendChild(el);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

addMessage('Hi! Describe your target role, for example: AI Engineer in Ho Chi Minh City with 20-30 million VND salary.', 'bot');

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;

  addMessage(message, 'user');
  messageInput.value = '';

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message }),
    });

    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }

    const payload = await response.json();
    addMessage(payload.response || 'No response returned from the system.', 'bot');
  } catch (error) {
    addMessage(`An error occurred: ${error.message}`, 'bot');
  }
});
