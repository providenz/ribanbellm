import { describe, expect, it } from 'vitest';
import { readEvents } from './stream.js';

const responseOf = (...chunks) =>
  new Response(
    new ReadableStream({
      start(controller) {
        chunks.forEach((c) => controller.enqueue(typeof c === 'string' ? new TextEncoder().encode(c) : c));
        controller.close();
      },
    }),
  );

const collect = async (response) => {
  const events = [];
  await readEvents(response, (e) => events.push(e));
  return events;
};

describe('readEvents', () => {
  it('emits one event per line across chunk boundaries', async () => {
    const events = await collect(responseOf('{"type":"thin', 'king","speaker":"A"}\n{"type":"end"}'));
    expect(events).toEqual([{ type: 'thinking', speaker: 'A' }, { type: 'end' }]);
  });

  it('decodes accents split across chunks', async () => {
    const bytes = new TextEncoder().encode('{"type":"line","text":"Gérard"}\n');
    const cut = bytes.indexOf(0xc3) + 1; // inside the two bytes of "é"
    const events = await collect(responseOf(bytes.slice(0, cut), bytes.slice(cut)));
    expect(events[0].text).toBe('Gérard');
  });

  it('skips empty lines', async () => {
    const events = await collect(responseOf('{"type":"end"}\n\n'));
    expect(events).toEqual([{ type: 'end' }]);
  });

  it('rejects when the stream errors', async () => {
    const broken = new Response(new ReadableStream({ start(c) { c.error(new Error('aborted')); } }));
    await expect(readEvents(broken, () => {})).rejects.toThrow('aborted');
  });
});
