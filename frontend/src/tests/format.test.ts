import { describe, expect, it } from "vitest";
import { NEXT_STATUSES, centsToMoney, money, toCents } from "../format";

describe("money helpers", () => {
  it("formats API decimal strings", () => {
    expect(money("8.50")).toBe("$8.50");
    expect(centsToMoney(1950)).toBe("$19.50");
  });
  it("converts to whole cents so sums don't drift", () => {
    expect(toCents("0.10") * 3).toBe(30);
    expect(toCents("10.50")).toBe(1050);
  });
});

describe("status flow (usability copy of the server rules)", () => {
  it("final states have no next steps", () => {
    expect(NEXT_STATUSES.delivered).toEqual([]);
    expect(NEXT_STATUSES.cancelled).toEqual([]);
  });
});
