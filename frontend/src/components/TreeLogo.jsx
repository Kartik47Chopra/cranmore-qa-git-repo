import React from "react";

export default function TreeLogo({ size = 20, className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      className={className}
      aria-label="Cranmore QA logo"
    >
      {/* Canopy - layered circles for a full deciduous tree */}
      <circle cx="32" cy="24" r="18" fill="#3a4d2c" />
      <circle cx="20" cy="28" r="12" fill="#4a5d3a" />
      <circle cx="44" cy="28" r="12" fill="#4a5d3a" />
      <circle cx="32" cy="18" r="10" fill="#5a6d4a" />
      {/* Trunk */}
      <rect x="29" y="38" width="6" height="18" rx="2" fill="#6d5b4a" />
      {/* Ground line */}
      <ellipse cx="32" cy="57" rx="14" ry="3" fill="#7d9658" opacity="0.5" />
    </svg>
  );
}
