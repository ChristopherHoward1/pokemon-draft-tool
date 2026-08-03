import { useCallback, useEffect, useRef, useState } from "react";
import { WS_URL } from "../api";

const MAX_RETRIES = 5;

/**
 * Live draft socket.
 *   const { state, lastPick, error, connectionStatus, sendPick, sendUndo } =
 *     useDraftSocket(sessionId, teamName);
 *
 * `state` is the most recent `state_update` payload. Reconnects automatically
 * with exponential backoff (5 attempts).
 */
export function useDraftSocket(sessionId, teamName) {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [lastPick, setLastPick] = useState(null); // {team, entry} of most recent pick
  const [connectionStatus, setConnectionStatus] = useState("connecting");

  const wsRef = useRef(null);
  const retriesRef = useRef(0);
  const closedRef = useRef(false);
  const timerRef = useRef(null);
  const prevTakenRef = useRef(new Set());

  const send = useCallback((msg) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    }
  }, []);

  const sendPick = useCallback(
    (pokemonName) => {
      setError(null);
      send({ type: "pick", pokemon_name: pokemonName });
    },
    [send]
  );

  const sendUndo = useCallback(() => {
    setError(null);
    send({ type: "undo" });
  }, [send]);

  useEffect(() => {
    if (!sessionId || !teamName) return undefined;
    closedRef.current = false;

    const connect = () => {
      setConnectionStatus(retriesRef.current === 0 ? "connecting" : "reconnecting");
      const url = `${WS_URL}/session/${sessionId}/draft?team_name=${encodeURIComponent(teamName)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        retriesRef.current = 0;
        setConnectionStatus("connected");
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        switch (msg.type) {
          case "state_update": {
            const next = msg.state;
            // Detect the newly-taken Pokémon to drive the pick-reveal flash.
            const nowTaken = new Set(
              next.pool.filter((e) => e.taken).map((e) => e.name)
            );
            const prev = prevTakenRef.current;
            const added = [...nowTaken].filter((n) => !prev.has(n));
            if (added.length === 1) {
              const entry = next.pool.find((e) => e.name === added[0]);
              // The team that just picked is the one before the current turn.
              setLastPick({ entry, at: Date.now() });
            }
            prevTakenRef.current = nowTaken;
            setState(next);
            break;
          }
          case "error":
            setError(msg.reason);
            break;
          case "player_connected":
          case "player_disconnected":
            // Presence — could surface a toast; ignored for now.
            break;
          default:
            break;
        }
      };

      ws.onclose = () => {
        if (closedRef.current) return;
        if (retriesRef.current < MAX_RETRIES) {
          const delay = Math.min(1000 * 2 ** retriesRef.current, 8000);
          retriesRef.current += 1;
          setConnectionStatus("reconnecting");
          timerRef.current = setTimeout(connect, delay);
        } else {
          setConnectionStatus("disconnected");
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      closedRef.current = true;
      clearTimeout(timerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [sessionId, teamName]);

  return { state, error, lastPick, connectionStatus, sendPick, sendUndo };
}
