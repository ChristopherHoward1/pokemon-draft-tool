import { useState } from "react";

/**
 * Copy text to the clipboard with a graceful fallback, and flash a "copied"
 * flag for `resetMs` afterwards. Works in insecure contexts (plain-HTTP LAN
 * hosting) where navigator.clipboard is unavailable.
 */
export function useCopy(resetMs = 2000) {
  const [copied, setCopied] = useState(false);

  const copy = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } catch {
        /* give up silently; the source text is still visible to copy manually */
      }
      document.body.removeChild(ta);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), resetMs);
  };

  return { copied, copy };
}
