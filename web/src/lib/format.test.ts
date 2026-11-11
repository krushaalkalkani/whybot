import { describe, expect, it } from "vitest";
import {
  NOT_RUN,
  fmtDecimal,
  fmtInt,
  fmtMetric,
  fmtMs,
  fmtPercent,
  fmtSeconds,
  fmtText,
  fmtUsd,
} from "./format";

describe("formatters", () => {
  it('return "not run yet" for null, undefined and NaN', () => {
    expect(NOT_RUN).toBe("not run yet");
    for (const f of [fmtPercent, fmtSeconds, fmtUsd, fmtDecimal, fmtInt, fmtMs]) {
      expect(f(null)).toBe(NOT_RUN);
      expect(f(undefined)).toBe(NOT_RUN);
      expect(f(Number.NaN)).toBe(NOT_RUN);
    }
    expect(fmtText(null)).toBe(NOT_RUN);
    expect(fmtText("")).toBe(NOT_RUN);
    expect(fmtMetric("percent", null)).toBe(NOT_RUN);
    expect(fmtMetric("usd", undefined)).toBe(NOT_RUN);
  });

  it("format real values", () => {
    expect(fmtPercent(0.8333)).toBe("83.3%");
    expect(fmtPercent(0)).toBe("0.0%");
    expect(fmtSeconds(4.25)).toBe("4.3 s");
    expect(fmtUsd(0.01234)).toBe("$0.0123");
    expect(fmtDecimal(6.44)).toBe("6.4");
    expect(fmtDecimal(0.612, 3)).toBe("0.612");
    expect(fmtInt(12345)).toBe("12,345");
    expect(fmtMs(420)).toBe("420 ms");
    expect(fmtMs(3200)).toBe("3.2 s");
    expect(fmtMetric("count", 6.44)).toBe("6.4");
    expect(fmtMetric("seconds", 12)).toBe("12.0 s");
  });
});
