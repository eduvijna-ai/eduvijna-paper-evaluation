export function useRouter() {
  return {
    push: () => undefined,
    replace: () => undefined,
    back: () => undefined,
  };
}

export function usePathname() {
  return "/";
}

export function useSearchParams() {
  return new URLSearchParams();
}
