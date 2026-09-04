import { createElement } from "react";

export default function Link({
  children,
  href,
  ...props
}: {
  children?: React.ReactNode;
  href: string;
} & Record<string, unknown>) {
  return createElement("a", { href, ...props }, children);
}
