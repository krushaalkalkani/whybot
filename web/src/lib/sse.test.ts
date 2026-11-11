import { describe, expect, it } from "vitest";
import { createSseParser } from "./sse";

describe("createSseParser", () => {
  it("parses complete frames", () => {
    const p = createSseParser();
    const frames = p.feed('event: run\ndata: {"run_id":"r1","cached":false}\n\nevent: done\ndata: {}\n\n');
    expect(frames).toEqual([
      { event: "run", data: '{"run_id":"r1","cached":false}' },
      { event: "done", data: "{}" },
    ]);
  });

  it("handles frames split across chunks", () => {
    const p = createSseParser();
    expect(p.feed("event: st")).toEqual([]);
    expect(p.feed('ep\ndata: {"index"')).toEqual([]);
    expect(p.feed(":0}\n")).toEqual([]);
    expect(p.feed("\n")).toEqual([{ event: "step", data: '{"index":0}' }]);
  });

  it("handles CRLF, including a CRLF split across chunks", () => {
    const p = createSseParser();
    expect(p.feed("event: step\r\ndata: 1\r\n\r")).toEqual([]);
    expect(p.feed("\nevent: done\r\ndata: {}\r\n\r\n")).toEqual([
      { event: "step", data: "1" },
      { event: "done", data: "{}" },
    ]);
  });

  it("joins multi-line data, skips comments, defaults the event name", () => {
    const p = createSseParser();
    expect(p.feed(": keep-alive\n\ndata: a\ndata: b\n\n")).toEqual([
      { event: "message", data: "a\nb" },
    ]);
  });

  it("flushes a trailing frame with no final blank line", () => {
    const p = createSseParser();
    expect(p.feed("event: done\ndata: {}")).toEqual([]);
    expect(p.flush()).toEqual([{ event: "done", data: "{}" }]);
    expect(p.flush()).toEqual([]);
  });
});
