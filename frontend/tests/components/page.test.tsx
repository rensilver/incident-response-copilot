import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import Page from "../../src/app/page";

test("the foundation page identifies its purpose and preview state", () => {
  render(<Page />);
  const main = screen.getByRole("main");
  expect(
    within(main).getByRole("heading", {
      level: 1,
      name: "Investigate an incident",
    }),
  ).toBeVisible();
  expect(within(main).getByText(/foundation preview/i)).toBeVisible();
  expect(within(main).queryByRole("button")).not.toBeInTheDocument();
});
