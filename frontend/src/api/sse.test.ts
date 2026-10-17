import { SSEParser } from "./sse";

describe("SSEParser", () => {
  it("parses complete messages and buffers partial ones", () => {
    const parser = new SSEParser();
    expect(parser.push('event: meta\ndata: {"query_id":"q_1"}\n\nevent: tok')).toEqual([
      { event: "meta", data: '{"query_id":"q_1"}' },
    ]);
    expect(parser.push('en\ndata: {"text":"Hi"}\n\n')).toEqual([{ event: "token", data: '{"text":"Hi"}' }]);
  });

  it("handles CRLF, comments, multi-line data and default event names", () => {
    const parser = new SSEParser();
    expect(parser.push(": keep-alive\r\n\r\ndata: a\r\ndata: b\r\n\r\n")).toEqual([{ event: "message", data: "a\nb" }]);
  });
});
