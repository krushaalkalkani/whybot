// Minimal Server-Sent Events frame parser for fetch + ReadableStream.
// Frames look like: "event: <name>\ndata: <json>\n\n".

export interface SseFrame {
  event: string;
  data: string;
}

function parseFrame(raw: string): SseFrame | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line === "" || line.startsWith(":")) continue; // blank or comment
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") event = value;
    else if (field === "data") dataLines.push(value);
  }
  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join("\n") };
}

export interface SseParser {
  /** Add a decoded text chunk. Returns every frame completed by it. */
  feed(chunk: string): SseFrame[];
  /** Call at end of stream. Returns a trailing frame with no final blank line, if any. */
  flush(): SseFrame[];
}

export function createSseParser(): SseParser {
  let buffer = "";
  return {
    feed(chunk) {
      // Normalize after joining, so a CRLF split across chunks still works.
      buffer = (buffer + chunk).replace(/\r\n/g, "\n");
      const frames: SseFrame[] = [];
      let idx = buffer.indexOf("\n\n");
      while (idx !== -1) {
        const frame = parseFrame(buffer.slice(0, idx));
        buffer = buffer.slice(idx + 2);
        if (frame) frames.push(frame);
        idx = buffer.indexOf("\n\n");
      }
      return frames;
    },
    flush() {
      const rest = buffer.replace(/\r/g, "\n");
      buffer = "";
      const frame = parseFrame(rest);
      return frame ? [frame] : [];
    },
  };
}

/** Read a fetch Response body as SSE frames. */
export async function readSse(
  body: ReadableStream<Uint8Array>,
  onFrame: (frame: SseFrame) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const frame of parser.feed(decoder.decode(value, { stream: true }))) {
        onFrame(frame);
      }
    }
    for (const frame of parser.feed(decoder.decode())) onFrame(frame);
    for (const frame of parser.flush()) onFrame(frame);
  } finally {
    reader.releaseLock();
  }
}
