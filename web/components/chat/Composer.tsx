"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";

type Props = {
  streaming: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  autoFocusKey: string | null;
};

const MAX_LENGTH = 1000;

export function Composer({ streaming, onSend, onStop, autoFocusKey }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  // Grow with the content up to a cap, then scroll inside.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  // Focus when switching conversations, so typing goes straight in. A null key
  // means don't: on phones, focusing would throw the keyboard over the page.
  useEffect(() => {
    if (autoFocusKey !== null) ref.current?.focus();
  }, [autoFocusKey]);

  const text = value.trim();
  const canSend = text.length > 0 && !streaming;

  function submit() {
    if (!canSend) return;
    onSend(text);
    setValue("");
  }

  return (
    <div className="px-3 pb-3 pt-2 sm:px-6 sm:pb-5">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-line bg-elevated p-2 shadow-sm transition-shadow focus-within:border-accent/40 focus-within:shadow-md"
      >
        <textarea
          ref={ref}
          rows={1}
          value={value}
          maxLength={MAX_LENGTH}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            // Enter sends, Shift+Enter adds a line. Ignore Enter while an IME
            // is composing, or Japanese and Chinese input would submit early.
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Ask anything about EU law…"
          aria-label="Message"
          className="scrollbar-thin max-h-[200px] min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-[15px] leading-6 outline-none placeholder:text-subtle"
        />
        {streaming ? (
          <button
            type="button"
            onClick={onStop}
            aria-label="Stop generating"
            title="Stop generating"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-fg text-bg transition-opacity hover:opacity-85"
          >
            <Square size={13} fill="currentColor" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send message"
            title="Send (Enter)"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-accent text-accent-fg transition-opacity hover:opacity-90 disabled:bg-fg/10 disabled:text-subtle"
          >
            <ArrowUp size={18} strokeWidth={2.25} />
          </button>
        )}
      </form>
      <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-subtle">
        Answers cite their sources. Check the cited passage before relying on it.
      </p>
    </div>
  );
}
