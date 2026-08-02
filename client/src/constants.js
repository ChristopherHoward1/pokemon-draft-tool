// Canonical Pokémon type colors — fixed, not a design choice.
// Mirrors engine/app usage exactly.
export const TYPE_COLORS = {
  normal: "#A8A878", fire: "#F08030", water: "#6890F0",
  electric: "#F8D030", grass: "#78C850", ice: "#98D8D8",
  fighting: "#C03028", poison: "#A040A0", ground: "#E0C068",
  flying: "#A890F0", psychic: "#F85888", bug: "#A8B820",
  rock: "#B8A038", ghost: "#705898", dragon: "#7038F8",
  dark: "#705848", steel: "#B8B8D0", fairy: "#EE99AC",
};

// Tier badge colors, grouped by cost band (mirrors the Streamlit app).
export const TIER_COLORS = {
  S: "#C62828",
  "A+": "#E65100", A: "#E65100", "A-": "#E65100",
  "B+": "#1565C0", B: "#1565C0", "B-": "#1565C0",
  "C+": "#546E7A", C: "#546E7A",
  D: "#455A64",
  Unranked: "#37474F",
};

export const TIER_ORDER = [
  "S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D", "Unranked",
];

export const FORMATS = [
  { key: "aaa", label: "AAA" },
  { key: "pokebilities", label: "Pokébilities" },
];
