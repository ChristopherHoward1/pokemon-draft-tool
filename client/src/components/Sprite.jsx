import { useEffect, useRef, useState } from "react";
import { spriteUrl } from "../api";

const RETRY_DELAYS = [1, 2, 4, 8, 30, 60];

function RetryingSprite({ path, alt, width, height, className, loading, fallback }) {
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);
  const timer = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  function onError() {
    setFailed(true);
    if (attempt >= RETRY_DELAYS.length) return;
    const delay = RETRY_DELAYS[attempt] * (0.75 + Math.random() * 0.5) * 1000;
    timer.current = setTimeout(() => {
      setAttempt(attempt + 1);
      setFailed(false);
    }, delay);
  }

  if (failed) return fallback ?? null;
  const src = spriteUrl(path) + (attempt ? `?retry=${attempt}` : "");
  return <img src={src} alt={alt} width={width} height={height} className={className} loading={loading} onError={onError} />;
}

export default function Sprite({ path, ...props }) {
  return <RetryingSprite key={path} path={path} {...props} />;
}
