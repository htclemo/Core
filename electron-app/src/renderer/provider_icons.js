/* TheCore — provider icons (Electron renderer).
 *
 * The Python app draws these with QPainter; here they are inline SVG so they
 * stay crisp and follow the theme colours.
 *
 *   local    — a chip: the model runs on this machine
 *   cloud    — a cloud: the model runs somewhere else
 *   terminal — a prompt: OpenCode's own console
 */

const PROVIDER_ICONS = {
  local: `
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none"
         stroke="#3ddc84" stroke-width="1.7" stroke-linecap="round">
      <rect x="5.2" y="5.2" width="13.6" height="13.6" rx="2.4"></rect>
      <line x1="2.6" y1="9" x2="5.2" y2="9"></line>
      <line x1="2.6" y1="12" x2="5.2" y2="12"></line>
      <line x1="2.6" y1="15" x2="5.2" y2="15"></line>
      <line x1="18.8" y1="9" x2="21.4" y2="9"></line>
      <line x1="18.8" y1="12" x2="21.4" y2="12"></line>
      <line x1="18.8" y1="15" x2="21.4" y2="15"></line>
      <line x1="9" y1="2.6" x2="9" y2="5.2"></line>
      <line x1="12" y1="2.6" x2="12" y2="5.2"></line>
      <line x1="15" y1="2.6" x2="15" y2="5.2"></line>
      <line x1="9" y1="18.8" x2="9" y2="21.4"></line>
      <line x1="12" y1="18.8" x2="12" y2="21.4"></line>
      <line x1="15" y1="18.8" x2="15" y2="21.4"></line>
    </svg>`,
  cloud: `
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none"
         stroke="#4ade80" stroke-width="1.7" stroke-linecap="round"
         stroke-linejoin="round">
      <path d="M6.5 17.5a3.6 3.6 0 0 1 .5-7.1 4.8 4.8 0 0 1 9.1-1.2
               3.9 3.9 0 0 1 .9 7.7z"></path>
    </svg>`,
  terminal: `
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none"
         stroke="#f2c94c" stroke-width="1.7" stroke-linecap="round"
         stroke-linejoin="round">
      <rect x="3.4" y="5" width="17.2" height="14" rx="2.2"></rect>
      <polyline points="8 10 11.5 12 8 14"></polyline>
      <line x1="13" y1="15" x2="17" y2="15"></line>
    </svg>`,
};

function providerIcon(kind) {
  return PROVIDER_ICONS[kind] || "";
}

/* The capability icons: a wrench (tools), an eye (vision) and a brain
 * (reasoning), each in a softly lit round disc. */
const CAPABILITY_ICONS = {
  tools: `
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none"
         stroke="#3ddc84" stroke-width="1.5" stroke-linecap="round"
         stroke-linejoin="round">
      <line x1="7.2" y1="16.8" x2="13.4" y2="10.6"></line>
      <path d="M13.6 8.2l1.9 1.9 2.9-2.9-1.9-1.9"></path>
      <path d="M14.4 5.6a4 4 0 0 1 4.4 5.5"></path>
    </svg>`,
  vision: `
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none"
         stroke="#f2c94c" stroke-width="1.5" stroke-linecap="round"
         stroke-linejoin="round">
      <path d="M3.2 12c2.6-3.4 5.6-5 8.8-5s6.2 1.6 8.8 5c-2.6 3.4-5.6 5-8.8 5S5.8 15.4 3.2 12z"></path>
      <circle cx="12" cy="12" r="2.4"></circle>
    </svg>`,
  reasoning: `
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none"
         stroke="#4ade80" stroke-width="1.5" stroke-linecap="round"
         stroke-linejoin="round">
      <path d="M12 4.2c-3.4-1.6-6.6.6-6.6 3.9 0 1.4.2 2.4.2 3.4
               0 2.2-1 4.6 2.6 5.3 1.2.5 2.6.3 3.8-.4"></path>
      <path d="M12 4.2c3.4-1.6 6.6.6 6.6 3.9 0 1.4-.2 2.4-.2 3.4
               0 2.2 1 4.6-2.6 5.3-1.2.5-2.6.3-3.8-.4"></path>
      <line x1="12" y1="4.2" x2="12" y2="16.4"></line>
    </svg>`,
};

/** The coloured disc behind a capability icon. */
const CAPABILITY_DISCS = {
  tools: "rgba(77, 225, 255, 0.15)",
  vision: "rgba(255, 232, 31, 0.15)",
  reasoning: "rgba(57, 255, 20, 0.15)",
};

// The capability names — shown in the tooltip of the icons.
const CAPABILITY_LABELS = {
  tools: "Tool Use",
  vision: "Vision",
  reasoning: "Reasoning",
};

function capabilityIcon(kind) {
  return CAPABILITY_ICONS[kind] || "";
}

/** The four pillars of the app, as small line icons. */
const CORE_GLYPHS = {
  brain: `
    <svg viewBox="0 0 24 24" width="17" height="17" fill="none"
         stroke="#3ddc84" stroke-width="1.5" stroke-linecap="round"
         stroke-linejoin="round">
      <path d="M12 5.5c-2.6-2.2-6-.1-6 2.6 0 1.3.2 2.3.2 3.2 0 2-1 4.3 2.6 5
               .9.5 2 .3 3.2-.4"></path>
      <path d="M12 5.5c2.6-2.2 6-.1 6 2.6 0 1.3-.2 2.3-.2 3.2 0 2 1 4.3-2.6 5
               -.9.5-2 .3-3.2-.4"></path>
      <line x1="12" y1="5.5" x2="12" y2="15.5"></line>
    </svg>`,
  bolt: `
    <svg viewBox="0 0 24 24" width="17" height="17" fill="none"
         stroke="#3ddc84" stroke-width="1.5" stroke-linecap="round"
         stroke-linejoin="round">
      <path d="M13 2.5L5 13h5l-1 8.5 8-10.5h-5z"></path>
    </svg>`,
  bug: `
    <svg viewBox="0 0 24 24" width="17" height="17" fill="none"
         stroke="#3ddc84" stroke-width="1.5" stroke-linecap="round"
         stroke-linejoin="round">
      <ellipse cx="12" cy="13" rx="4" ry="5.5"></ellipse>
      <ellipse cx="12" cy="6.5" rx="3" ry="2.5"></ellipse>
      <line x1="5" y1="10" x2="8" y2="11"></line>
      <line x1="19" y1="10" x2="16" y2="11"></line>
      <line x1="5" y1="16" x2="8" y2="15"></line>
      <line x1="19" y1="16" x2="16" y2="15"></line>
    </svg>`,
  terminal: `
    <svg viewBox="0 0 24 24" width="17" height="17" fill="none"
         stroke="#3ddc84" stroke-width="1.5" stroke-linecap="round"
         stroke-linejoin="round">
      <rect x="3" y="5" width="18" height="14" rx="2.5"></rect>
      <polyline points="7 10 10 12.5 7 15"></polyline>
      <line x1="12.5" y1="15" x2="17" y2="15"></line>
    </svg>`,
};

function coreGlyph(kind) {
  return CORE_GLYPHS[kind] || "";
}
