"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SSEEvent } from "@/lib/types";

interface UseSSEOptions {
  onEvent?: (event: SSEEvent) => void;
  onError?: (error: string) => void;
  onComplete?: () => void;
}

export function useSSE(options: UseSSEOptions = {}) {
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const optionsRef = useRef(options);

  useEffect(() => {
    optionsRef.current = options;
  }, [options]);

  const startStream = useCallback(
    async (url: string, init?: RequestInit) => {
      // Abort any previous stream
      abortRef.current?.abort();

      const controller = new AbortController();
      abortRef.current = controller;
      setIsStreaming(true);

      try {
        const response = await fetch(url, {
          method: init?.method || "GET",
          body: init?.body,
          signal: controller.signal,
          headers: {
            Accept: "text/event-stream",
            ...(init?.headers || {}),
          },
        });

        if (!response.ok) {
          throw new Error(`Stream failed: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const chunk of lines) {
            const dataLine = chunk
              .split("\n")
              .find((l) => l.startsWith("data: "));
            if (!dataLine) continue;

            try {
              const event: SSEEvent = JSON.parse(dataLine.slice(6));
              optionsRef.current.onEvent?.(event);

              if (event.type === "session_complete" || event.type === "error") {
                if (event.type === "error") {
                  optionsRef.current.onError?.(event.message || "Unknown stream error");
                }
                break;
              }
            } catch {
              // Ignore parse errors for partial chunks
            }
          }
        }

        optionsRef.current.onComplete?.();
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          const msg = err instanceof Error ? err.message : "Stream failed";
          optionsRef.current.onError?.(msg);
        }
      } finally {
        setIsStreaming(false);
      }
    },
    []
  );

  const stopStream = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, []);

  return { isStreaming, startStream, stopStream };
}
