// Live chat sidebar: the conversations as they happen, like the chat next to a live video.

const MAX_MESSAGES = 200;
const STICK_DISTANCE_PX = 24; // closer than this to the bottom counts as "following the chat"

// "A ❤️ B" when A's feeling toward B rose, "A 😕 B" when it fell.
export function feelingNotes(feelings) {
  const names = Object.keys(feelings);
  return names.flatMap((name) => {
    const { before, after } = feelings[name];
    if (after === before) return [];
    const other = names.find((n) => n !== name);
    return [`${name} ${after > before ? '❤️' : '😕'} ${other}`];
  });
}

export function isNearBottom({ scrollHeight, scrollTop, clientHeight }) {
  return scrollHeight - scrollTop - clientHeight < STICK_DISTANCE_PX;
}

export class ChatLog {
  constructor(list) {
    this.list = list;
  }

  separator(text) {
    this.append('chat-separator', [text]);
  }

  line(name, color, emoji, text) {
    const who = document.createElement('span');
    who.className = 'chat-name';
    who.style.color = color;
    who.textContent = name;
    this.append('chat-line', [who, ` ${emoji ? `${emoji} ` : ''}${text}`]);
  }

  note(text) {
    this.append('chat-note', [text]);
  }

  append(className, parts) {
    const follow = isNearBottom(this.list);
    const item = document.createElement('li');
    item.className = className;
    item.append(...parts); // strings become text nodes, never HTML
    this.list.append(item);
    while (this.list.children.length > MAX_MESSAGES) this.list.firstElementChild.remove();
    if (follow) this.list.scrollTop = this.list.scrollHeight;
  }
}
