// Reads a newline-delimited JSON response and calls onEvent for each object as it arrives.
export async function readEvents(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  const flush = (text) => {
    if (text.trim()) onEvent(JSON.parse(text));
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }); // stream mode keeps split multibyte chars
    const lines = buffer.split('\n');
    buffer = lines.pop();
    lines.forEach(flush);
  }
  flush(buffer + decoder.decode());
}
