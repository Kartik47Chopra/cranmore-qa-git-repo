import React from "react";

export default function TreeLogo({ size = 20, className = "" }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      className={className}
      aria-label="Cranmore QA logo"
    >
      <defs>
        <radialGradient id="treeBg" cx="50%" cy="45%" r="55%">
          <stop offset="0%" stopColor="#E0F7FA" />
          <stop offset="100%" stopColor="#D7F9E9" />
        </radialGradient>
      </defs>
      {/* Background circle with radial gradient */}
      <circle cx="50" cy="50" r="48" fill="url(#treeBg)" />
      {/* Canopy — layered organic leaf shapes in shades of green */}
      <ellipse cx="50" cy="36" rx="26" ry="22" fill="#2B4621" />
      <ellipse cx="34" cy="40" rx="16" ry="14" fill="#3A5C2D" />
      <ellipse cx="66" cy="40" rx="16" ry="14" fill="#3A5C2D" />
      <ellipse cx="50" cy="28" rx="18" ry="14" fill="#4A6D3D" />
      <ellipse cx="40" cy="32" rx="10" ry="8" fill="#5A7D4D" />
      <ellipse cx="60" cy="32" rx="10" ry="8" fill="#5A7D4D" />
      <ellipse cx="50" cy="24" rx="8" ry="6" fill="#98A952" />
      {/* Trunk */}
      <path d="M48 52 L48 64 L52 64 L52 52 Z" fill="#000000" />
      {/* Trunk splits into two branches near base */}
      <path d="M48 64 Q42 66 38 70" stroke="#000000" strokeWidth="3" fill="none" strokeLinecap="round" />
      <path d="M52 64 Q58 66 62 70" stroke="#000000" strokeWidth="3" fill="none" strokeLinecap="round" />
      {/* Roots — symmetrical curved flowing network */}
      <path d="M50 64 Q50 70 50 74" stroke="#000000" strokeWidth="3" fill="none" strokeLinecap="round" />
      {/* Left roots */}
      <path d="M50 74 Q44 76 38 78" stroke="#000000" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      <path d="M50 74 Q56 76 62 78" stroke="#000000" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      <path d="M38 78 Q32 80 28 84" stroke="#000000" strokeWidth="2" fill="none" strokeLinecap="round" />
      <path d="M38 78 Q34 82 32 86" stroke="#000000" strokeWidth="2" fill="none" strokeLinecap="round" />
      <path d="M62 78 Q68 80 72 84" stroke="#000000" strokeWidth="2" fill="none" strokeLinecap="round" />
      <path d="M62 78 Q66 82 68 86" stroke="#000000" strokeWidth="2" fill="none" strokeLinecap="round" />
      <path d="M50 74 Q48 78 46 82" stroke="#000000" strokeWidth="2" fill="none" strokeLinecap="round" />
      <path d="M50 74 Q52 78 54 82" stroke="#000000" strokeWidth="2" fill="none" strokeLinecap="round" />
    </svg>
  );
}
