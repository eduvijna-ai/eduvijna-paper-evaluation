import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { TopicPriorityCard } from "@/components/learning/LearningComponents";

describe("TopicPriorityCard", () => {
  it("renders priority topic with mastery and errors", () => {
    render(
      <TopicPriorityCard
        topic={{
          id: "tp-1",
          topic: "Similarity / BPT",
          priority: 1,
          reason: "Repeated method errors",
          mastery: 0.42,
          error_codes: ["METHOD", "CALCULATION"],
        }}
      />,
    );
    const card = screen.getByTestId("topic-priority-1");
    expect(card).toHaveTextContent("Similarity / BPT");
    expect(card).toHaveTextContent(/priority 1/i);
    expect(card).toHaveTextContent("42%");
  });
});
