import { Routes, Route, Navigate } from "react-router-dom";
import Setup from "./pages/Setup.jsx";
import Lobby from "./pages/Lobby.jsx";
import Draft from "./pages/Draft.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Setup />} />
      <Route path="/lobby/:code" element={<Lobby />} />
      <Route path="/draft/:code" element={<Draft />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
