import { useCallback, useRef } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from 'react';

type Options = {
  containerRef?: RefObject<HTMLElement | null>;
};

const FOCUSABLE_SELECTOR = [
  'input:not([type="hidden"]):not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'button:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

const isVisible = (el: HTMLElement) => !!(el.offsetParent || el.getClientRects().length);

const isTextLikeInput = (el: HTMLElement) => {
  if (!(el instanceof HTMLInputElement)) return false;
  const t = (el.type || 'text').toLowerCase();
  return ['text', 'search', 'url', 'tel', 'email', 'password', 'number'].includes(t);
};

const shouldKeepHorizontalCaret = (e: ReactKeyboardEvent<HTMLElement>) => {
  if (!(e.target instanceof HTMLInputElement)) return false;
  if (!isTextLikeInput(e.target)) return false;
  const { selectionStart, selectionEnd, value } = e.target;
  if (selectionStart == null || selectionEnd == null) return true;

  if (e.key === 'ArrowLeft') return !(selectionStart === selectionEnd && selectionStart === 0);
  if (e.key === 'ArrowRight') return !(selectionStart === selectionEnd && selectionEnd === value.length);
  return false;
};

const findFocusRoot = (active: HTMLElement, fallback: HTMLElement | null) => {
  const modalRoot = active.closest('[role="dialog"], [aria-modal="true"], .modal, .modal-content');
  return (modalRoot as HTMLElement | null) ?? fallback;
};

export const useFocusNavigation = ({ containerRef }: Options = {}) => {
  const localRef = useRef<HTMLElement | null>(null);
  const ref = (containerRef ?? localRef) as RefObject<HTMLElement | null>;

  const onKeyDownCapture = useCallback((e: ReactKeyboardEvent<HTMLElement>) => {
    if ((e.nativeEvent as KeyboardEvent).isComposing) return;
    if (e.altKey || e.ctrlKey || e.metaKey) return;

    const direction = (e.key === 'Tab' || e.key === 'ArrowDown' || e.key === 'ArrowRight') ? 1
      : (e.key === 'ArrowUp' || e.key === 'ArrowLeft') ? -1
      : 0;
    if (!direction) return;

    if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && e.target instanceof HTMLInputElement && e.target.type === 'number') {
      e.preventDefault();
    }

    if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && shouldKeepHorizontalCaret(e)) return;

    const active = e.target as HTMLElement;
    const root = findFocusRoot(active, ref.current);
    if (!root) return;

    const focusables = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
      .filter((el) => !el.hasAttribute('disabled') && isVisible(el) && el.tabIndex >= 0 && !el.getAttribute('aria-hidden'));

    const currentIndex = focusables.indexOf(active);
    if (currentIndex < 0) return;

    const nextIndex = Math.max(0, Math.min(focusables.length - 1, currentIndex + direction));
    if (nextIndex === currentIndex) return;

    e.preventDefault();
    focusables[nextIndex].focus();
  }, [ref]);

  return { focusNavRef: ref, onFocusNavKeyDownCapture: onKeyDownCapture };
};
