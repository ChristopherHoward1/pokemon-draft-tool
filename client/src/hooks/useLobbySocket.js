import { useEffect, useRef, useState } from "react";
import { WS_URL } from "../api";

/**
 * Lobby presence socket. Returns live slot list + a `started` flag that flips
 * true when the host starts the draft (the caller then navigates to /draft).
 */
export function useLobbySocket(sessionId) {
  const [slots, setSlots] = useState([]);
  const [numTeams, setNumTeams] = useState(null);
  const [started, setStarted] = useState(false);
  const wsRef = useRef(null);
  const closedRef = useRef(false);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!sessionId) return undefined;
    closedRef.current = false;

    const connect = () => {
      const ws = new WebSocket(`${WS_URL}/session/${sessionId}/lobby`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "lobby_update") {
          setSlots(msg.slots);
          if (msg.num_teams != null) setNumTeams(msg.num_teams);
          if (msg.started) setStarted(true);
        } else if (msg.type === "draft_started") {
          setStarted(true);
        }
      };

      ws.onclose = () => {
        if (closedRef.current) return;
        timerRef.current = setTimeout(connect, 1500); // lobby is low-stakes; simple retry
      };
      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      closedRef.current = true;
      clearTimeout(timerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [sessionId]);

  return { slots, numTeams, started };
}
