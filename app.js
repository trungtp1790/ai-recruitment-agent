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

addMessage('Xin chào! Hãy mô tả công việc bạn muốn tìm, ví dụ: AI Engineer lương 20-30 triệu tại HCM.', 'bot');

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
    addMessage(payload.response || 'Không có phản hồi từ hệ thống.', 'bot');
  } catch (error) {
    addMessage(`Có lỗi xảy ra: ${error.message}`, 'bot');
  }
});
