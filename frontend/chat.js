/**
 * chat.js — Madrasti Chat Thread Logic
 * Used by: chat.html
 */

/* ── Config & State ─────────────────────────────────── */
const API = (localStorage.getItem('api_base_url') || 'http://127.0.0.1:8000').replace(/\/$/, '');
const token = localStorage.getItem('auth_token');

// Auth guard
if (!token) { window.location.replace('index.html'); }

// Parse URL params
const params = new URLSearchParams(window.location.search);
const SESSION_ID   = parseInt(params.get('session'),  10) || 0;
const PARTNER_ID   = parseInt(params.get('partner'),  10) || 0;
const PARTNER_NAME = decodeURIComponent(params.get('name') || 'مستخدم');

// Validate required params
if (!SESSION_ID || !PARTNER_ID) {
  window.location.replace('messages.html');
}

// Current logged-in user id
let CURRENT_USER_ID = null;
try {
  const u = JSON.parse(localStorage.getItem('auth_user') || '{}');
  CURRENT_USER_ID = u.id || null;
} catch (_) {}

let messages         = [];     // [{id, sender_id, content, sent_at, edited?}]
let lastMessageId    = 0;
let pollTimer        = null;
let editingMessageId = null;   // null = send mode, number = edit mode
let menuMessageId    = null;   // message id for context menu
let partnerPublicId  = '';
const friendIds = new Set();
const outgoingFriendRequestIds = new Set();
const outgoingRequestIdByUserId = new Map();
const unreadChatCountBySessionId = new Map();
const lastChatTimestampBySessionId = new Map();

/* ── DOM refs ────────────────────────────────────────── */
const messagesArea   = document.getElementById('messagesArea');
const messagesContent= document.getElementById('messagesContent');
const loadingMsg     = document.getElementById('loadingMsg');
const msgInput       = document.getElementById('msgInput');
const sendBtn        = document.getElementById('sendBtn');
const partnerAvatar  = document.getElementById('partnerAvatar');
const editBar        = document.getElementById('editBar');
const cancelEditBtn  = document.getElementById('cancelEditBtn');
const bubbleMenu     = document.getElementById('bubbleMenu');
const menuEditBtn    = document.getElementById('menuEditBtn');
const menuDeleteBtn  = document.getElementById('menuDeleteBtn');
const menuCopyBtn    = document.getElementById('menuCopyBtn');
const menuCancelBtn  = document.getElementById('menuCancelBtn');
const toast          = document.getElementById('toast');
const threadMenuBtn  = document.getElementById('threadMenuBtn');
const threadMenu     = document.getElementById('threadMenu');
const threadMuteBtn  = document.getElementById('threadMuteBtn');
const threadDeleteBtn= document.getElementById('threadDeleteBtn');
const threadBlockBtn = document.getElementById('threadBlockBtn');
const attachBtn      = document.getElementById('attachBtn');
const attachMenu     = document.getElementById('attachMenu');
const attachImageBtn = document.getElementById('attachImageBtn');
const attachFileBtn  = document.getElementById('attachFileBtn');
const attachVoiceBtn = document.getElementById('attachVoiceBtn');
const imageInput     = document.getElementById('imageInput');
const fileInput      = document.getElementById('fileInput');
const confirmModal   = document.getElementById('confirmModal');
const confirmModalText = document.getElementById('confirmModalText');
const confirmModalCancelBtn = document.getElementById('confirmModalCancelBtn');
const confirmModalActionBtn = document.getElementById('confirmModalActionBtn');
const userProfileModal = document.getElementById('userProfileModal');
const closeProfileModalBtn = document.getElementById('closeProfileModalBtn');
const messageFromProfileBtn = document.getElementById('messageFromProfileBtn');
const addFriendFromProfileBtn = document.getElementById('addFriendFromProfileBtn');
const blockFromProfileBtn = document.getElementById('blockFromProfileBtn');
const removeFriendFromProfileBtn = document.getElementById('removeFriendFromProfileBtn');
let confirmResolver  = null;

/* ── Helpers ─────────────────────────────────────────── */
function apiFetch(path, opts = {}) {
  return fetch(API + path, {
    ...opts,
    headers: {
      'Authorization': 'Bearer ' + token,
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    }
  });
}

function showToast(msg, duration = 3000) {
  toast.textContent = msg;
  toast.classList.add('show');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove('show'), duration);
}

function getSocialStateStorageKey() {
  return `madrasti_social_state_${CURRENT_USER_ID || 'guest'}`;
}

function savePersistedSocialState() {
  if (!CURRENT_USER_ID) return;
  let existingPayload = {};
  try {
    existingPayload = JSON.parse(localStorage.getItem(getSocialStateStorageKey()) || '{}') || {};
  } catch (_) {
    existingPayload = {};
  }
  const payload = {
    ...existingPayload,
    unreadChatCounts: Object.fromEntries(unreadChatCountBySessionId.entries()),
    lastChatTimestamps: Object.fromEntries(lastChatTimestampBySessionId.entries()),
  };
  localStorage.setItem(getSocialStateStorageKey(), JSON.stringify(payload));
}

function loadPersistedSocialState() {
  if (!CURRENT_USER_ID) return;
  try {
    const parsed = JSON.parse(localStorage.getItem(getSocialStateStorageKey()) || '{}') || {};
    unreadChatCountBySessionId.clear();
    Object.entries(parsed.unreadChatCounts || {}).forEach(([key, value]) => {
      const count = Number(value || 0);
      if (count > 0) unreadChatCountBySessionId.set(String(key), count);
    });
    lastChatTimestampBySessionId.clear();
    Object.entries(parsed.lastChatTimestamps || {}).forEach(([key, value]) => {
      if (value) lastChatTimestampBySessionId.set(String(key), String(value));
    });
  } catch (_) {
    unreadChatCountBySessionId.clear();
    lastChatTimestampBySessionId.clear();
  }
}

function markCurrentSessionAsRead() {
  unreadChatCountBySessionId.delete(String(SESSION_ID));
  savePersistedSocialState();
}

function formatPublicIdLabel(publicId) {
  const value = String(publicId || '').trim();
  return value ? `ID: ${value}` : 'ID: -';
}

function openConfirmModal(message, actionText = 'تأكيد الحذف') {
  if (!confirmModal) return Promise.resolve(false);
  if (confirmModalText) confirmModalText.textContent = message || 'هل أنت متأكد؟';
  if (confirmModalActionBtn) confirmModalActionBtn.textContent = actionText;
  confirmModal.classList.remove('hidden');
  return new Promise((resolve) => {
    confirmResolver = resolve;
  });
}

function closeConfirmModal(confirmed) {
  if (confirmModal) confirmModal.classList.add('hidden');
  if (confirmResolver) {
    const resolve = confirmResolver;
    confirmResolver = null;
    resolve(Boolean(confirmed));
  }
}

function getRoleLabelFromRaw(roleOrLabel) {
  const value = String(roleOrLabel || '').toLowerCase();
  if (value === 'admin') return 'إدارة المدرسة';
  if (value === 'principal') return 'مدير المدرسة';
  if (value === 'super_admin') return 'المسؤول الأعلى';
  if (value === 'guardian') return 'ولي أمر';
  return 'معلم';
}

function normalizeSpecialization(value) {
  const normalized = String(value || '').trim();
  if (!normalized || normalized === '-' || normalized === 'غير محدد') return '';
  return normalized;
}

function getRoleWithSpecialization(roleOrLabel, specialization) {
  const roleLabel = getRoleLabelFromRaw(roleOrLabel);
  const cleanSpecialization = normalizeSpecialization(specialization);
  return cleanSpecialization ? `${roleLabel} - ${cleanSpecialization}` : roleLabel;
}

async function refreshRelationshipState() {
  try {
    const [friendsResp, outgoingResp] = await Promise.all([
      apiFetch('/friends/list'),
      apiFetch('/friends/requests/outgoing'),
    ]);
    friendIds.clear();
    outgoingFriendRequestIds.clear();
    outgoingRequestIdByUserId.clear();
    if (friendsResp.ok) {
      const data = await friendsResp.json();
      (data.friends || []).forEach((item) => friendIds.add(String(item.user_id)));
    }
    if (outgoingResp.ok) {
      const data = await outgoingResp.json();
      (data || []).forEach((item) => {
        const key = String(item.user_id);
        outgoingFriendRequestIds.add(key);
        if (item.request_id != null) outgoingRequestIdByUserId.set(key, Number(item.request_id));
      });
    }
  } catch (_) {}
}

function syncProfileActionButtons() {
  if (addFriendFromProfileBtn) {
    const isFriend = friendIds.has(String(PARTNER_ID));
    const isPending = outgoingFriendRequestIds.has(String(PARTNER_ID));
    addFriendFromProfileBtn.disabled = isFriend;
    addFriendFromProfileBtn.textContent = isFriend ? 'تمت الإضافة' : (isPending ? 'تم إرسال الطلب' : '➕ إضافة صديق');
  }
  if (removeFriendFromProfileBtn) {
    removeFriendFromProfileBtn.disabled = !friendIds.has(String(PARTNER_ID));
  }
}

function setProfileAvatar(imageData, fullName) {
  const avatar = document.getElementById('viewProfileAvatar');
  if (!avatar) return;
  const image = String(imageData || '').trim();
  if (image) {
    avatar.innerHTML = `<img src="${image}" alt="${escapeHtml(fullName || 'مستخدم')}">`;
    return;
  }
  avatar.textContent = (String(fullName || '؟').trim().charAt(0) || '👤');
}

async function openUserProfileModal(userId) {
  if (!userId || !userProfileModal) return;
  try {
    await refreshRelationshipState();
    const resp = await apiFetch(`/users/${encodeURIComponent(userId)}/profile`);
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || 'تعذر تحميل الملف الشخصي');

    document.getElementById('viewProfileName').textContent = data.full_name || '-';
    document.getElementById('viewProfileRole').textContent = getRoleWithSpecialization(data.role_label || 'teacher', data.specialization);
    document.getElementById('viewProfileId').textContent = `🆔 ${formatPublicIdLabel(data.public_id)}`;
    document.getElementById('viewProfileSchool').textContent = `🏫 ${data.school_name || '-'}`;
    document.getElementById('viewProfilePhone').textContent = `📞 ${data.phone || '-'}`;
    setProfileAvatar(data.profile_image, data.full_name || 'مستخدم');
    syncProfileActionButtons();

    userProfileModal.classList.remove('hidden');
  } catch (err) {
    showToast(err.message || 'تعذر تحميل الملف الشخصي');
  }
}

function closeUserProfileModal() {
  if (userProfileModal) userProfileModal.classList.add('hidden');
}

async function sendFriendRequestFromProfile() {
  const userKey = String(PARTNER_ID);
  if (outgoingFriendRequestIds.has(userKey)) {
    const requestId = outgoingRequestIdByUserId.get(userKey);
    if (!requestId) {
      showToast('تعذر العثور على طلب الصداقة لإلغائه');
      return;
    }
    const approved = await openConfirmModal('هل تريد إلغاء طلب الصداقة؟', 'إلغاء الطلب');
    if (!approved) return;
    try {
      const cancelResp = await apiFetch(`/friends/requests/${requestId}`, { method: 'DELETE' });
      const cancelData = await cancelResp.json().catch(() => ({}));
      if (!cancelResp.ok) throw new Error(cancelData.detail || 'فشل إلغاء طلب الصداقة');
      outgoingFriendRequestIds.delete(userKey);
      outgoingRequestIdByUserId.delete(userKey);
      syncProfileActionButtons();
      showToast('تم إلغاء طلب الصداقة');
    } catch (err) {
      showToast(err.message || 'تعذر إلغاء طلب الصداقة');
    }
    return;
  }

  try {
    const resp = await apiFetch('/friends/requests', {
      method: 'POST',
      body: JSON.stringify({ receiver_id: PARTNER_ID }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || 'فشل إرسال طلب الصداقة');
    outgoingFriendRequestIds.add(userKey);
    if (data.request_id) outgoingRequestIdByUserId.set(userKey, Number(data.request_id));
    syncProfileActionButtons();
    showToast('تم إرسال طلب الصداقة بنجاح');
  } catch (err) {
    showToast(err.message || 'تعذر إرسال طلب الصداقة');
  }
}

async function blockPartnerUser() {
  closeUserProfileModal();
  const approved = await openConfirmModal('هل تريد حظر هذا المستخدم؟', 'حظر');
  if (!approved) return;
  try {
    const resp = await apiFetch(`/users/${PARTNER_ID}/block`, { method: 'POST' });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || 'فشل حظر المستخدم');
    showToast('تم حظر المستخدم بنجاح');
    setTimeout(() => {
      window.location.href = 'messages.html';
    }, 500);
  } catch (err) {
    showToast(err.message || 'تعذر حظر المستخدم');
  }
}

async function removeFriendFromProfile() {
  if (!friendIds.has(String(PARTNER_ID))) return;
  closeUserProfileModal();
  const approved = await openConfirmModal('هل تريد إزالة هذا المستخدم من قائمة أصدقائك؟', 'إزالة صديق');
  if (!approved) return;
  try {
    const resp = await apiFetch(`/friends/${PARTNER_ID}`, { method: 'DELETE' });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || 'فشل إزالة الصديق');
    friendIds.delete(String(PARTNER_ID));
    syncProfileActionButtons();
    showToast('تمت إزالة الصديق بنجاح');
  } catch (err) {
    showToast(err.message || 'تعذر إزالة الصديق');
  }
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '<br>');
}

function formatTime(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  return d.toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' });
}

function formatDateLabel(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  const now = new Date();
  const diffDays = Math.floor((now - d) / 86400000);
  if (diffDays === 0) return 'اليوم';
  if (diffDays === 1) return 'أمس';
  return d.toLocaleDateString('ar-SA', { weekday: 'long', day: 'numeric', month: 'long' });
}

function renderMessageContent(rawText) {
  const text = typeof rawText === 'string'
    ? rawText
    : (rawText && typeof rawText === 'object'
      ? String(rawText.content || rawText.text || '')
      : String(rawText || ''));
  if (!text.startsWith('ATTACHMENT|')) {
    return escapeHtml(text);
  }

  const parts = text.split('|');
  if (parts.length < 4) {
    return escapeHtml(text);
  }

  const type = parts[1];
  const fileName = parts[2] || 'attachment';
  const dataUrl = parts.slice(3).join('|');
  const safeName = escapeHtml(fileName);

  if (type === 'image') {
    return `<div class="attachment-block"><img src="${dataUrl}" alt="${safeName}" style="max-width:180px;border-radius:10px;display:block;"><a href="${dataUrl}" download="${safeName}" style="color:#bbdefb;display:block;margin-top:6px;">تنزيل الصورة: ${safeName}</a></div>`;
  }

  return `<a href="${dataUrl}" download="${safeName}" style="color:#bbdefb;">📎 تنزيل الملف: ${safeName}</a>`;
}

function isAtBottom() {
  return (messagesArea.scrollHeight - messagesArea.scrollTop - messagesArea.clientHeight) < 60;
}

function scrollToBottom(force = false) {
  if (force || isAtBottom()) {
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }
}

/* ── Header setup ────────────────────────────────────── */
document.getElementById('partnerName').textContent = PARTNER_NAME;
document.getElementById('backBtn').onclick  = () => window.location.href = 'messages.html';
partnerAvatar.onclick = () => openUserProfileModal(PARTNER_ID);
document.getElementById('partnerName').onclick = () => openUserProfileModal(PARTNER_ID);

/* ── Input handling ──────────────────────────────────── */
msgInput.addEventListener('input', () => {
  // Auto-resize
  msgInput.style.height = 'auto';
  msgInput.style.height = Math.min(msgInput.scrollHeight, 120) + 'px';
  // Enable/disable send button
  sendBtn.disabled = !msgInput.value.trim();
});

msgInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) handleSend();
  }
});

sendBtn.onclick = handleSend;
cancelEditBtn.onclick = cancelEdit;
threadMenuBtn.onclick = (e) => {
  e.stopPropagation();
  threadMenu.classList.toggle('hidden');
  attachMenu.classList.add('hidden');
};
threadMuteBtn.onclick = async () => {
  threadMenu.classList.add('hidden');
  await toggleThreadMute();
};
threadDeleteBtn.onclick = async () => {
  threadMenu.classList.add('hidden');
  await deleteCurrentChat();
};
if (threadBlockBtn) {
  threadBlockBtn.onclick = async () => {
    threadMenu.classList.add('hidden');
    await blockPartnerUser();
  };
}
attachBtn.onclick = (e) => {
  e.stopPropagation();
  attachMenu.classList.toggle('hidden');
  threadMenu.classList.add('hidden');
};
attachImageBtn.onclick = () => {
  attachMenu.classList.add('hidden');
  imageInput.click();
};
attachFileBtn.onclick = () => {
  attachMenu.classList.add('hidden');
  fileInput.click();
};
attachVoiceBtn.onclick = () => {
  attachMenu.classList.add('hidden');
  showToast('خيار الرسالة الصوتية جاهز في القائمة وسيتم تفعيله لاحقًا');
};
if (confirmModalCancelBtn) confirmModalCancelBtn.onclick = () => closeConfirmModal(false);
if (confirmModalActionBtn) confirmModalActionBtn.onclick = () => closeConfirmModal(true);
if (closeProfileModalBtn) closeProfileModalBtn.onclick = () => closeUserProfileModal();
if (messageFromProfileBtn) messageFromProfileBtn.onclick = () => closeUserProfileModal();
if (addFriendFromProfileBtn) addFriendFromProfileBtn.onclick = () => sendFriendRequestFromProfile();
if (blockFromProfileBtn) blockFromProfileBtn.onclick = () => blockPartnerUser();
if (removeFriendFromProfileBtn) removeFriendFromProfileBtn.onclick = () => removeFriendFromProfile();
if (confirmModal) {
  confirmModal.addEventListener('click', (event) => {
    if (event.target === confirmModal) closeConfirmModal(false);
  });
}
if (userProfileModal) {
  userProfileModal.addEventListener('click', (event) => {
    if (event.target === userProfileModal) closeUserProfileModal();
  });
}
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && confirmModal && !confirmModal.classList.contains('hidden')) {
    closeConfirmModal(false);
    return;
  }
  if (event.key === 'Escape' && userProfileModal && !userProfileModal.classList.contains('hidden')) {
    closeUserProfileModal();
  }
});
imageInput.onchange = (event) => handleAttachmentSelected(event, 'image');
fileInput.onchange = (event) => handleAttachmentSelected(event, 'file');

/* ── Render messages ─────────────────────────────────── */
function renderMessages(msgs, append = false) {
  if (!append) messagesContent.innerHTML = '';

  let lastDateLabel = null;

  if (!append) {
    // Get existing date labels to avoid duplicates
    lastDateLabel = null;
  } else {
    // When appending, find the last date label we rendered
    const seps = messagesContent.querySelectorAll('.messages-date-sep');
    if (seps.length > 0) lastDateLabel = seps[seps.length - 1].dataset.date;
  }

  msgs.forEach(m => {
    const d = new Date(m.sent_at);
    const dateKey = d.toDateString();
    const dateLabel = formatDateLabel(m.sent_at);

    if (dateKey !== lastDateLabel) {
      const sep = document.createElement('div');
      sep.className = 'messages-date-sep';
      sep.dataset.date = dateKey;
      sep.innerHTML = `<span>${escapeHtml(dateLabel)}</span>`;
      messagesContent.appendChild(sep);
      lastDateLabel = dateKey;
    }

    const isSent = m.sender_id === CURRENT_USER_ID;
    const row = document.createElement('div');
    row.className = `bubble-row ${isSent ? 'sent' : 'recv'}`;
    row.dataset.msgId = m.id;

    const bubble = document.createElement('div');
    bubble.className = `bubble ${isSent ? 'sent' : 'recv'}`;
    bubble.innerHTML = `
      ${renderMessageContent(m.content)}
      ${m.edited ? '<span class="edited-badge"> (معدّل)</span>' : ''}
      <span class="bubble-time">${formatTime(m.sent_at)}</span>
    `;

    if (isSent) {
      bubble.addEventListener('click', (e) => { e.stopPropagation(); showBubbleMenu(m.id, e, true); });
      bubble.addEventListener('contextmenu', (e) => { e.preventDefault(); showBubbleMenu(m.id, e, true); });
    }

    row.appendChild(bubble);
    messagesContent.appendChild(row);
  });
}

async function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('تعذر قراءة الملف'));
    reader.readAsDataURL(file);
  });
}

async function handleAttachmentSelected(event, type) {
  const file = event?.target?.files?.[0];
  if (!file) return;

  try {
    const dataUrl = await fileToDataUrl(file);
    const payload = `ATTACHMENT|${type}|${file.name}|${dataUrl}`;
    await sendNewMessage(payload);
  } catch (_) {
    showToast('تعذر تجهيز المرفق');
  } finally {
    event.target.value = '';
  }
}

/* ── Context menu ────────────────────────────────────── */
function showBubbleMenu(msgId, e, isSent) {
  menuMessageId = msgId;
  bubbleMenu.classList.remove('hidden');
  menuEditBtn.classList.toggle('hidden', !isSent);
  menuDeleteBtn.classList.toggle('hidden', !isSent);

  // Position the menu near cursor
  let x = e.clientX;
  let y = e.clientY;

  // Keep within viewport
  const mw = 150, mh = isSent ? 150 : 80;
  if (x + mw > window.innerWidth)  x = window.innerWidth - mw - 8;
  if (y + mh > window.innerHeight) y = y - mh - 8;

  bubbleMenu.style.left = x + 'px';
  bubbleMenu.style.top  = y + 'px';
}

function hideBubbleMenu() {
  bubbleMenu.classList.add('hidden');
  menuMessageId = null;
}

document.addEventListener('click', hideBubbleMenu);
document.addEventListener('click', (event) => {
  if (!threadMenu.contains(event.target) && !threadMenuBtn.contains(event.target)) {
    threadMenu.classList.add('hidden');
  }
  if (!attachMenu.contains(event.target) && !attachBtn.contains(event.target)) {
    attachMenu.classList.add('hidden');
  }
});

menuCancelBtn.onclick = hideBubbleMenu;

menuCopyBtn.onclick = () => {
  const msg = messages.find(m => m.id === menuMessageId);
  if (msg) {
    const plainText = typeof msg.content === 'string'
      ? msg.content
      : String(msg.content?.content || msg.content?.text || '');
    navigator.clipboard.writeText(plainText).then(() => showToast('تم نسخ الرسالة'));
  }
  hideBubbleMenu();
};

menuEditBtn.onclick = () => {
  const msg = messages.find(m => m.id === menuMessageId);
  if (msg) startEdit(msg);
  hideBubbleMenu();
};

menuDeleteBtn.onclick = () => {
  const id = menuMessageId;
  hideBubbleMenu();
  if (id) deleteMessage(id);
};

/* ── Edit mode ───────────────────────────────────────── */
function startEdit(msg) {
  editingMessageId = msg.id;
  msgInput.value = typeof msg.content === 'string'
    ? msg.content
    : String(msg.content?.content || msg.content?.text || '');
  msgInput.style.height = 'auto';
  msgInput.style.height = Math.min(msgInput.scrollHeight, 120) + 'px';
  sendBtn.disabled = false;
  editBar.classList.remove('hidden');
  msgInput.focus();
}

function cancelEdit() {
  editingMessageId = null;
  msgInput.value = '';
  msgInput.style.height = '';
  sendBtn.disabled = true;
  editBar.classList.add('hidden');
}

/* ── Send / Edit ─────────────────────────────────────── */
async function handleSend() {
  const content = msgInput.value.trim();
  if (!content) return;

  sendBtn.disabled = true;

  if (editingMessageId) {
    await sendEdit(editingMessageId, content);
  } else {
    await sendNewMessage(content);
  }
}

async function sendNewMessage(content) {
  try {
    const resp = await apiFetch(`/chat/sessions/${SESSION_ID}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast(err.detail || 'فشل إرسال الرسالة');
      sendBtn.disabled = false;
      return;
    }
    const msg = await resp.json();
    msg.edited = false;

    // Clear input
    msgInput.value = '';
    msgInput.style.height = '';

    // Optimistic append
    messages.push(msg);
    lastMessageId = Math.max(lastMessageId, msg.id);
    renderMessages([msg], true);
    scrollToBottom(true);
  } catch (_) {
    showToast('تعذّر الإرسال — تحقق من الاتصال');
    sendBtn.disabled = false;
  }
}

async function sendEdit(messageId, content) {
  try {
    const resp = await apiFetch(`/chat/messages/${messageId}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast(err.detail || 'فشل التعديل');
      sendBtn.disabled = !msgInput.value.trim();
      return;
    }
    const updated = await resp.json();
    // Update messages array
    const idx = messages.findIndex(m => m.id === messageId);
    if (idx !== -1) {
      messages[idx].content = updated.content;
      messages[idx].edited  = true;
    }
    cancelEdit();
    // Re-render
    renderMessages(messages, false);
    scrollToBottom(false);
  } catch (_) {
    showToast('تعذّر التعديل — تحقق من الاتصال');
    sendBtn.disabled = !msgInput.value.trim();
  }
}

/* ── Delete message ──────────────────────────────────── */
async function deleteMessage(messageId) {
  const accepted = await openConfirmModal('هل تريد حذف هذه الرسالة نهائيًا من قاعدة البيانات؟');
  if (!accepted) return;
  try {
    const resp = await apiFetch(`/chat/messages/${messageId}`, { method: 'DELETE' });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      showToast(err.detail || 'فشل الحذف');
      return;
    }
    messages = messages.filter(m => m.id !== messageId);
    renderMessages(messages, false);
    showToast('تم حذف الرسالة نهائيًا بنجاح');
  } catch (_) {
    showToast('تعذّر الحذف');
  }
}

/* ── Load messages ───────────────────────────────────── */
async function loadAllMessages() {
  try {
    const resp = await apiFetch(`/chat/sessions/${SESSION_ID}/messages`);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      loadingMsg.innerHTML = `<p style="color:#ef5350;text-align:center;padding:20px">${err.detail || 'فشل تحميل الرسائل'}</p>`;
      return;
    }
    const data = await resp.json();
    messages = (data.messages || []).map(m => ({ ...m, edited: m.edited || false }));
    lastMessageId = messages.length > 0 ? messages[messages.length - 1].id : 0;
    const newestTimestamp = messages.length > 0 ? messages[messages.length - 1].sent_at : null;
    if (newestTimestamp) lastChatTimestampBySessionId.set(String(SESSION_ID), newestTimestamp);
    markCurrentSessionAsRead();
    savePersistedSocialState();
    loadingMsg.classList.add('hidden');
    renderMessages(messages, false);
    scrollToBottom(true);
  } catch (err) {
    loadingMsg.innerHTML = `<p style="color:#ef5350;text-align:center;padding:20px">خطأ في الاتصال بالخادم</p>`;
  }
}

/* ── Poll for new messages ───────────────────────────── */
async function pollMessages() {
  try {
    const resp = await apiFetch(`/chat/sessions/${SESSION_ID}/messages`);
    if (!resp.ok) return;
    const data = await resp.json();
    const incoming = (data.messages || []).map(m => ({ ...m, edited: m.edited || false }));

    if (incoming.length === 0) return;
    const maxId = incoming[incoming.length - 1].id;
    if (maxId <= lastMessageId) {
      // Check for edits/deletes
      const hasChanges = incoming.some(nm => {
        const old = messages.find(m => m.id === nm.id);
        return !old || old.content !== nm.content;
      }) || messages.length !== incoming.length;
      if (!hasChanges) return;
      messages = incoming;
      renderMessages(messages, false);
      scrollToBottom(false);
      return;
    }

    const newOnes = incoming.filter(m => m.id > lastMessageId);
    lastMessageId = maxId;
    messages.push(...newOnes);
    renderMessages(newOnes, true);
    scrollToBottom(false);
    const newestTimestamp = incoming[incoming.length - 1]?.sent_at;
    if (newestTimestamp) lastChatTimestampBySessionId.set(String(SESSION_ID), newestTimestamp);
    markCurrentSessionAsRead();
  } catch (_) {}
}

/* ── User status ─────────────────────────────────────── */
async function updatePartnerStatus() {
  try {
    const resp = await apiFetch(`/users/${PARTNER_ID}/status`);
    if (!resp.ok) return;
    const data = await resp.json();
    const el = document.getElementById('partnerStatus');
    if (data.online) {
      el.textContent = partnerPublicId ? `متصل الآن • ${formatPublicIdLabel(partnerPublicId)}` : 'متصل الآن';
      el.className = 'bar-user-status online';
    } else if (data.last_seen) {
      const d = new Date(data.last_seen);
      const lastSeenText = `آخر ظهور: ${d.toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' })}`;
      el.textContent = partnerPublicId ? `${lastSeenText} • ${formatPublicIdLabel(partnerPublicId)}` : lastSeenText;
      el.className = 'bar-user-status';
    } else {
      el.textContent = partnerPublicId ? `غير متصل • ${formatPublicIdLabel(partnerPublicId)}` : 'غير متصل';
      el.className = 'bar-user-status';
    }
  } catch (_) {}
}

async function heartbeat() {
  try { await apiFetch('/users/status/online', { method: 'POST' }); } catch (_) {}
}

async function loadPartnerProfile() {
  try {
    loadPersistedSocialState();
    const resp = await apiFetch(`/users/${PARTNER_ID}/profile`);
    if (!resp.ok) return;
    const data = await resp.json();
    if (data.full_name) {
      document.getElementById('partnerName').textContent = data.full_name;
    }
    partnerPublicId = String(data.public_id || '').trim();
    updatePartnerStatus();
    if (data.profile_image) {
      partnerAvatar.innerHTML = `<img src="${data.profile_image}" alt="${escapeHtml(data.full_name || PARTNER_NAME)}">`;
      return;
    }
    setPartnerAvatar();
  } catch (_) {
    setPartnerAvatar();
  }
}

async function toggleThreadMute() {
  try {
    const nextMuted = threadMuteBtn.dataset.muted === 'true' ? false : true;
    const resp = await apiFetch(`/chat/sessions/${SESSION_ID}/mute`, {
      method: 'POST',
      body: JSON.stringify({ is_muted: nextMuted }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || 'فشل تحديث الكتم');
    threadMuteBtn.dataset.muted = String(!!data.is_muted);
    threadMuteBtn.textContent = data.is_muted ? '🔔 إلغاء كتم الإشعارات' : '🔕 كتم الإشعارات';
    showToast(data.is_muted ? 'تم كتم إشعارات هذه الدردشة' : 'تم إلغاء كتم إشعارات هذه الدردشة');
  } catch (err) {
    showToast(err.message || 'تعذر تحديث الكتم');
  }
}

async function deleteCurrentChat() {
  const accepted = await openConfirmModal('هل تريد حذف جميع رسائل هذه الدردشة فقط مع إبقاء المحادثة موجودة؟', 'حذف الرسائل');
  if (!accepted) return;
  try {
    const resp = await apiFetch(`/chat/sessions/${SESSION_ID}`, { method: 'DELETE' });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || 'فشل حذف الدردشة');
    messages = [];
    lastMessageId = 0;
    messagesContent.innerHTML = '';
    markCurrentSessionAsRead();
    lastChatTimestampBySessionId.delete(String(SESSION_ID));
    savePersistedSocialState();
    showToast('تم حذف رسائل الدردشة مع إبقاء المحادثة');
  } catch (err) {
    showToast(err.message || 'تعذر حذف الدردشة');
  }
}

/* ── Partner avatar initial ──────────────────────────── */
function setPartnerAvatar() {
  const el = document.getElementById('partnerAvatar');
  el.textContent = PARTNER_NAME.charAt(0) || '؟';
}

/* ── Init ────────────────────────────────────────────── */
loadPartnerProfile();
refreshRelationshipState().then(() => syncProfileActionButtons());
loadAllMessages();
updatePartnerStatus();
heartbeat();

// Polling every 3 seconds
pollTimer = setInterval(pollMessages, 3000);
const statusTimer   = setInterval(updatePartnerStatus, 15000);
const heartbeatTimer= setInterval(heartbeat, 30000);

// Refresh on visibility change
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) {
    pollMessages();
    updatePartnerStatus();
    heartbeat();
  }
});

// Cleanup on unload
window.addEventListener('beforeunload', () => {
  clearInterval(pollTimer);
  clearInterval(statusTimer);
  clearInterval(heartbeatTimer);
});
