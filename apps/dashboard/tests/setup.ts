/**
 * Vitest setup global: añade los matchers de @testing-library/jest-dom
 * (`toBeInTheDocument`, `toHaveClass`, etc.) a `expect`. También
 * configura cleanup automático entre tests para evitar fugas de DOM.
 */
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

afterEach(() => {
  cleanup();
});
